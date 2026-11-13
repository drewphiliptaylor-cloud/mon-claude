"""Pont entre le dashboard et Claude Code (Claude Agent SDK, abonnement de l'utilisateur).

Un objet `Conversation` par conversation ouverte dans l'interface. Il envoie à la page
des événements simples (dict) :

    session {id}                 identifiant Claude Code (pour reprendre plus tard)
    etat {etat}                  reflechit · lit · commande · ecrit · attend · pret
    etape {genre, texte}         action réelle de Claude (« Lit plans.pdf »)
    texte {delta}                morceau de réponse, au fil de l'eau
    accord {id, texte, detail}   Claude demande l'autorisation d'utiliser un outil
    accord_fini {id, ok}
    quota {statut, reinit, genre}
    fin {cout, erreur, session}
    erreur {message}

Note : les blocs de réflexion arrivent vides (contenu non transmis par Claude Code) ;
on n'affiche donc jamais de « pensées » inventées, seulement l'état et les actions réelles.
"""
import asyncio
import shutil
import uuid
from typing import Awaitable, Callable, Optional

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, PermissionResultAllow,
                              PermissionResultDeny, RateLimitEvent, ResultMessage, StreamEvent, SystemMessage,
                              ToolUseBlock)

from .libelles import etat as etat_outil, libelle

DELAI_ACCORD = 600  # secondes avant de refuser une demande restée sans réponse
# Modes de Claude Code proposés (Maj+Tab dans le terminal). « bypassPermissions » est exclu exprès :
# il ferait tout sans jamais demander, ce qui contredit « rien sans validation ».
MODES = ("default", "acceptEdits", "plan", "auto")

Envoyer = Callable[[dict], Awaitable[None]]


class Traducteur:
    """Messages du SDK → événements d'interface. Sans effet de bord : testable seul."""

    def __init__(self):
        self.texte_vu = False  # du texte est-il arrivé au fil de l'eau pendant ce tour ?
        self.modele = None     # modèle qui a réellement répondu (le mode Plan peut en changer)

    def traduire(self, m) -> list:
        if isinstance(m, SystemMessage) and m.subtype == "commands_changed":
            return [{"type": "commandes_desc", "commandes": [
                {"nom": c.get("name"), "description": c.get("description", "")}
                for c in m.data.get("commands") or [] if isinstance(c, dict) and c.get("name")]}]
        if isinstance(m, SystemMessage):
            if m.subtype == "init":
                return [{"type": "session", "id": m.data.get("session_id")}, {"type": "etat", "etat": "reflechit"},
                        {"type": "commandes", "noms": m.data.get("slash_commands") or [],
                         "terminal": m.data.get("terminal_slash_commands") or [],
                         "plugins": [{"name": p.get("name"), "path": p.get("path")} for p in m.data.get("plugins") or []
                                     if isinstance(p, dict)]}]
            return []
        if isinstance(m, StreamEvent):
            if getattr(m, "parent_tool_use_id", None):
                return []  # texte d'un sous-agent : pas la réponse principale
            ev = m.event or {}
            t = ev.get("type")
            if t == "content_block_start":
                bloc = ev.get("content_block") or {}
                genre = bloc.get("type")
                if genre == "thinking":
                    return [{"type": "etat", "etat": "reflechit"}]
                if genre == "text":
                    return [{"type": "etat", "etat": "ecrit"}]
                if genre == "tool_use":
                    return [{"type": "etat", "etat": etat_outil(bloc.get("name", ""))}]
            if t == "content_block_delta":
                d = ev.get("delta") or {}
                if d.get("type") == "text_delta" and d.get("text"):
                    self.texte_vu = True
                    return [{"type": "texte", "delta": d["text"]}]
            return []
        if isinstance(m, AssistantMessage):
            if getattr(m, "parent_tool_use_id", None):
                return []
            if getattr(m, "model", None) and m.model != "<synthetic>":
                self.modele = m.model
            return [{"type": "etape", "genre": "action", "texte": libelle(b.name, b.input or {})}
                    for b in m.content if isinstance(b, ToolUseBlock)]
        if isinstance(m, RateLimitEvent):
            i = m.rate_limit_info
            return [{"type": "quota", "statut": i.status, "reinit": i.resets_at, "genre": i.rate_limit_type,
                     "utilisation": i.utilization}]
        if isinstance(m, ResultMessage):
            evs = []
            # Réponse sans flux (message « synthétique » de Claude Code, ex. un skill refusé) : on l'affiche quand même.
            if not self.texte_vu and m.result:
                evs.append({"type": "texte", "delta": m.result})
            self.texte_vu = False
            modele, self.modele = self.modele, None
            return evs + [{"type": "fin", "cout": m.total_cost_usd, "erreur": bool(m.is_error), "session": m.session_id,
                           "modele": modele},
                          {"type": "etat", "etat": "pret"}]
        return []


def message_utilisateur(texte: str, images: list) -> dict:
    """Message au format du flux d'entrée de Claude Code. images = [(type MIME, base64)]."""
    contenu = [{"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}} for mime, b64 in images]
    if texte:
        contenu.append({"type": "text", "text": texte})
    return {"type": "user", "message": {"role": "user", "content": contenu}, "parent_tool_use_id": None}


class Conversation:
    """Une conversation vit indépendamment de la page : quitter la page ne coupe pas la réponse en cours.

    La page s'y « attache » (attacher) et s'en « détache » (detacher). Pendant un tour, chaque événement est
    aussi gardé dans un journal, rejoué à la page qui revient en cours de route.
    """

    def __init__(self, envoyer: Optional[Envoyer], cwd: str, session_id: Optional[str] = None,
                 surveiller_quota: Optional[Callable[[dict], None]] = None,
                 noter_commandes: Optional[Callable[[dict], None]] = None,
                 noter_session: Optional[Callable[["Conversation"], None]] = None):
        self._page: Optional[Envoyer] = envoyer
        self._noter_session = noter_session
        self.journal: list = []      # événements du tour en cours (pour une page qui revient)
        self.modele: Optional[str] = None   # None = modèle par défaut de Claude Code
        self.mode = "default"
        self._commandes = noter_commandes
        self._cwd = cwd
        self.session_id = session_id
        self._quota = surveiller_quota
        self._client: Optional[ClaudeSDKClient] = None
        self._accords: dict = {}
        self._traducteur = Traducteur()
        self.occupe = False
        self.ferme = False
        self._copie = False          # reprendre dans une copie (la conversation tourne ailleurs)
        self._stderr: list = []      # dernières lignes d'erreur de Claude Code, pour des messages lisibles

    def _options(self) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(cwd=self._cwd, cli_path=shutil.which("claude"), include_partial_messages=True,
                                  setting_sources=["user", "project", "local"], can_use_tool=self._autorisation,
                                  resume=self.session_id, fork_session=self._copie,
                                  model=self.modele, permission_mode=self.mode,
                                  stderr=self._noter_stderr,
                                  env={"MCP_CONNECTION_NONBLOCKING": "false"})  # connecteurs Google prêts dès le 1er message

    # ---------- page attachée ----------
    async def _envoyer(self, ev: dict) -> None:
        if self.occupe:
            self.journal.append(ev)
        page = self._page
        if page is not None:
            await page(ev)

    def attacher(self, envoyer: Envoyer) -> None:
        self._page = envoyer

    def detacher(self) -> None:
        self._page = None

    @property
    def attachee(self) -> bool:
        return self._page is not None

    def etat_pour_page(self) -> dict:
        return {"type": "reprise", "occupe": self.occupe, "modele": self.modele or "default", "mode": self.mode}

    # ---------- modèle et mode ----------
    async def regler(self, modele: Optional[str] = None, mode: Optional[str] = None) -> None:
        """Change le modèle et/ou le mode ; s'applique tout de suite si Claude Code est déjà lancé."""
        if mode is not None:
            if mode not in MODES:
                raise ValueError("Mode inconnu.")
            self.mode = mode
            if self._client is not None:
                await self._client.set_permission_mode(mode)
        if modele is not None:
            self.modele = None if modele == "default" else modele
            if self._client is not None:
                await self._client.set_model(self.modele)
        await self._envoyer({"type": "reglages_conv", "modele": self.modele or "default", "mode": self.mode})

    def _noter_stderr(self, ligne: str) -> None:
        if ligne.strip():
            self._stderr = (self._stderr + [ligne.strip()])[-20:]

    def _cause(self) -> str:
        """Dernière ligne d'erreur utile de Claude Code (plutôt que « Check stderr output »)."""
        return next((l for l in reversed(self._stderr) if l.lower().startswith("error")), self._stderr[-1] if self._stderr else "")

    async def _autorisation(self, nom: str, entree: dict, _ctx):
        id_ = uuid.uuid4().hex[:10]
        futur = asyncio.get_running_loop().create_future()
        self._accords[id_] = futur
        detail = (entree or {}).get("command") or (entree or {}).get("file_path") or (entree or {}).get("plan") or ""
        await self._envoyer({"type": "accord", "id": id_, "outil": nom, "texte": libelle(nom, entree or {}),
                             "detail": str(detail)[:4000 if nom == "ExitPlanMode" else 500]})
        await self._envoyer({"type": "etat", "etat": "attend"})
        try:
            ok = await asyncio.wait_for(futur, DELAI_ACCORD)
        except asyncio.TimeoutError:
            ok = False
        finally:
            self._accords.pop(id_, None)
        if ok and nom == "ExitPlanMode":
            # Plan accepté : Claude Code sort du mode Plan ; on l'affiche (« Demander » est son mode de sortie).
            self.mode = "default"
            await self._envoyer({"type": "reglages_conv", "modele": self.modele or "default", "mode": self.mode})
        await self._envoyer({"type": "accord_fini", "id": id_, "ok": ok})
        await self._envoyer({"type": "etat", "etat": etat_outil(nom) if ok else "reflechit"})
        if ok:
            return PermissionResultAllow()
        return PermissionResultDeny(message="L'utilisateur a refusé cette action depuis le dashboard.")

    def repondre_accord(self, id_: str, ok: bool) -> bool:
        futur = self._accords.get(id_)
        if futur is None or futur.done():
            return False
        futur.set_result(bool(ok))
        return True

    async def tour(self, texte: str, images: Optional[list] = None, bulle: Optional[dict] = None) -> None:
        """bulle : ce que la page affiche du message (texte, images) — rejoué si la page revient en cours de route."""
        if self.occupe:
            await self._envoyer({"type": "erreur", "message": "Claude répond déjà. Attends la fin ou interromps."})
            return
        self.occupe = True
        self.journal = [{"type": "moi", "texte": texte, "images": (bulle or {}).get("images", [])}]
        try:
            for essai in (1, 2):
                self._stderr = []
                try:
                    await self._un_tour(texte, images)
                    break
                except Exception as e:
                    await self._fermer_client()
                    tourne_ailleurs = "running in the background" in " ".join(self._stderr)
                    if essai == 1 and tourne_ailleurs and self.session_id and not self._copie:
                        # La conversation tourne encore dans un terminal : on ne la vole pas, on continue dans une copie.
                        self._copie = True
                        await self._envoyer({"type": "info", "message": "Cette conversation tourne encore en arrière-plan "
                                             "(dans le terminal). Je continue ici dans une copie : l'original n'est pas touché."})
                        continue
                    cause = self._cause() or f"{type(e).__name__}: {e}"
                    await self._envoyer({"type": "erreur", "message": f"Claude Code a rencontré un problème : {cause}"[:500]})
                    await self._envoyer({"type": "etat", "etat": "pret"})
                    break
        finally:
            self.occupe = False
            self.journal = []
            if self._page is None:
                await self.fermer()  # personne ne regarde : la réponse est enregistrée par Claude Code, on libère

    async def _un_tour(self, texte: str, images: Optional[list]) -> None:
        if self._client is None:
            self._client = ClaudeSDKClient(options=self._options())
            await self._client.connect()
        if images:
            msg = message_utilisateur(texte, images)

            async def flux():
                yield msg
            await self._client.query(flux())
        else:
            await self._client.query(texte)
        notif_tache = False
        async for m in self._client.receive_messages():
            if type(m).__name__ == "TaskNotificationMessage":
                notif_tache = True  # tâche de fond héritée (ex. copie d'une session de terminal)
                continue
            if isinstance(m, ResultMessage) and notif_tache and m.num_turns == 0 and not m.is_error:
                # ce « résultat » clôt la notification de tâche, pas notre message : on attend la vraie réponse
                notif_tache = False
                continue
            for ev in self._traducteur.traduire(m):
                if ev["type"] == "session" and ev.get("id"):
                    self.session_id = ev["id"]
                    self._copie = False  # la copie a maintenant son propre identifiant : on la reprend normalement
                    if self._noter_session:
                        self._noter_session(self)
                if ev["type"] == "quota" and self._quota:
                    self._quota(ev)
                if ev["type"] in ("commandes", "commandes_desc"):
                    if self._commandes:
                        self._commandes(ev)
                    continue  # information pour le serveur, pas pour la page
                await self._envoyer(ev)
            if isinstance(m, ResultMessage):
                break  # fin de la réponse à ce message

    async def interrompre(self) -> None:
        if self._client is not None and self.occupe:
            await self._client.interrupt()

    async def _fermer_client(self) -> None:
        c, self._client = self._client, None
        if c is not None:
            try:
                await c.disconnect()
            except Exception:
                pass

    async def fermer(self) -> None:
        self.ferme = True
        for futur in list(self._accords.values()):
            if not futur.done():
                futur.set_result(False)  # conversation libérée : on refuse proprement
        await self._fermer_client()
        if self._noter_session:
            self._noter_session(self)


async def liste_modeles(cwd: str) -> list:
    """Modèles que Claude Code propose à ce compte (comme le sélecteur /model du terminal)."""
    client = ClaudeSDKClient(options=ClaudeAgentOptions(cwd=cwd, cli_path=shutil.which("claude"), setting_sources=[],
                                                        extra_args={"no-session-persistence": None}))
    await client.connect()
    try:
        info = await client.get_server_info() or {}
    finally:
        await client.disconnect()
    sortie = []
    for m in info.get("models") or []:
        if isinstance(m, dict) and isinstance(m.get("value"), str):
            nom = "Par défaut" if m["value"] == "default" else str(m.get("displayName") or m["value"])
            sortie.append({"valeur": m["value"], "nom": nom, "description": str(m.get("description") or "")})
    return sortie or [{"valeur": "default", "nom": "Par défaut", "description": ""}]
