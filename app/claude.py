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

Envoyer = Callable[[dict], Awaitable[None]]


class Traducteur:
    """Messages du SDK → événements d'interface. Sans effet de bord : testable seul."""

    def __init__(self):
        self.texte_vu = False  # du texte est-il arrivé au fil de l'eau pendant ce tour ?

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
            return evs + [{"type": "fin", "cout": m.total_cost_usd, "erreur": bool(m.is_error), "session": m.session_id},
                          {"type": "etat", "etat": "pret"}]
        return []


def message_utilisateur(texte: str, images: list) -> dict:
    """Message au format du flux d'entrée de Claude Code. images = [(type MIME, base64)]."""
    contenu = [{"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}} for mime, b64 in images]
    if texte:
        contenu.append({"type": "text", "text": texte})
    return {"type": "user", "message": {"role": "user", "content": contenu}, "parent_tool_use_id": None}


class Conversation:
    def __init__(self, envoyer: Envoyer, cwd: str, session_id: Optional[str] = None,
                 surveiller_quota: Optional[Callable[[dict], None]] = None,
                 noter_commandes: Optional[Callable[[dict], None]] = None):
        self._envoyer = envoyer
        self._commandes = noter_commandes
        self._cwd = cwd
        self.session_id = session_id
        self._quota = surveiller_quota
        self._client: Optional[ClaudeSDKClient] = None
        self._accords: dict = {}
        self._traducteur = Traducteur()
        self.occupe = False
        self._copie = False          # reprendre dans une copie (la conversation tourne ailleurs)
        self._stderr: list = []      # dernières lignes d'erreur de Claude Code, pour des messages lisibles

    def _options(self) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(cwd=self._cwd, cli_path=shutil.which("claude"), include_partial_messages=True,
                                  setting_sources=["user", "project", "local"], can_use_tool=self._autorisation,
                                  resume=self.session_id, fork_session=self._copie,
                                  stderr=self._noter_stderr,
                                  env={"MCP_CONNECTION_NONBLOCKING": "false"})  # connecteurs Google prêts dès le 1er message

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
        detail = (entree or {}).get("command") or (entree or {}).get("file_path") or ""
        await self._envoyer({"type": "accord", "id": id_, "outil": nom, "texte": libelle(nom, entree or {}),
                             "detail": str(detail)[:500]})
        await self._envoyer({"type": "etat", "etat": "attend"})
        try:
            ok = await asyncio.wait_for(futur, DELAI_ACCORD)
        except asyncio.TimeoutError:
            ok = False
        finally:
            self._accords.pop(id_, None)
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

    async def tour(self, texte: str, images: Optional[list] = None) -> None:
        if self.occupe:
            await self._envoyer({"type": "erreur", "message": "Claude répond déjà. Attends la fin ou interromps."})
            return
        self.occupe = True
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
        for futur in list(self._accords.values()):
            if not futur.done():
                futur.set_result(False)  # page fermée : on refuse proprement
        await self._fermer_client()
