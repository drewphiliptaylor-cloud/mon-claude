"""Historique des conversations Claude Code (les mêmes que `claude --resume`)."""
from pathlib import Path
from typing import Callable, Optional

from .libelles import libelle

_BRUIT = ("<command-", "<local-command", "<system-reminder", "Caveat:", "<task-notification")


def _blocs(message: dict) -> list:
    contenu = (message or {}).get("content")
    if isinstance(contenu, str):
        return [{"type": "text", "text": contenu}]
    return contenu if isinstance(contenu, list) else []


def _texte_utile(t: str) -> str:
    t = (t or "").strip()
    return "" if not t or t.startswith(_BRUIT) else t


def convertir(messages: list) -> list:
    """Messages bruts (dict avec 'type' et 'message') → éléments d'affichage.

    {"role": "moi", "texte", "images"} ou {"role": "claude", "texte", "etapes": [{"type", "texte"}]}.
    Dans un tour de Claude, les textes intermédiaires deviennent des étapes « pense »,
    le dernier texte est la réponse.
    """
    sortie, tour = [], None

    def fermer():
        nonlocal tour
        if tour is not None:
            textes = tour.pop("_textes")
            tour["texte"] = textes[-1] if textes else ""
            for i in range(len(tour["etapes"]) - 1, -1, -1):  # la réponse finale n'est pas une étape
                if tour["etapes"][i] == {"type": "pense", "texte": tour["texte"]}:
                    del tour["etapes"][i]
                    break
            if tour["texte"] or tour["etapes"]:
                sortie.append(tour)
            tour = None

    for m in messages:
        blocs = _blocs(m.get("message"))
        if m.get("type") == "user":
            textes = [_texte_utile(b.get("text", "")) for b in blocs if b.get("type") == "text"]
            textes = [t for t in textes if t]
            images = sum(1 for b in blocs if b.get("type") == "image")
            if not textes and not images:
                continue  # résultat d'outil ou message système : pas un message de l'utilisateur
            fermer()
            sortie.append({"role": "moi", "texte": "\n\n".join(textes), "images": images})
        elif m.get("type") == "assistant":
            if tour is None:
                tour = {"role": "claude", "etapes": [], "_textes": []}
            for b in blocs:
                if b.get("type") == "text" and b.get("text", "").strip():
                    tour["etapes"].append({"type": "pense", "texte": b["text"].strip()})
                    tour["_textes"].append(b["text"].strip())
                elif b.get("type") == "tool_use":
                    tour["etapes"].append({"type": "action", "texte": libelle(b.get("name", ""), b.get("input") or {})})
    fermer()
    return sortie


def _exclue(cwd: Optional[str], exclus: list) -> bool:
    if not cwd:
        return False
    return any(str(cwd).startswith(str(e)) for e in exclus)


def conversations(lister: Callable, exclus: list, limite: int = 30) -> list:
    """`lister` = claude_agent_sdk.list_sessions (injecté pour les tests)."""
    sortie = []
    for s in lister(limit=limite * 3):
        if _exclue(s.cwd, exclus):
            continue
        sortie.append({"id": s.session_id, "titre": s.custom_title or s.summary or s.first_prompt or "Sans titre",
                       "maj": s.last_modified, "cwd": s.cwd or ""})
        if len(sortie) >= limite:
            break
    return sortie


def messages(lire: Callable, session_id: str) -> list:
    """`lire` = claude_agent_sdk.get_session_messages (injecté pour les tests)."""
    bruts = [{"type": m.type, "message": m.message} for m in lire(session_id)]
    return convertir(bruts)
