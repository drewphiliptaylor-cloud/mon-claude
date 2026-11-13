"""Traduction des outils de Claude Code en phrases courtes pour l'utilisateur, et en état de l'orbe."""
import os


def _court(texte, n=70) -> str:
    texte = " ".join(str(texte or "").split())
    return texte if len(texte) <= n else texte[: n - 1] + "…"


def _fichier(entree: dict) -> str:
    chemin = entree.get("file_path") or entree.get("path") or entree.get("notebook_path") or ""
    return os.path.basename(str(chemin)) or "un fichier"


def libelle(nom: str, entree: dict) -> str:
    entree = entree if isinstance(entree, dict) else {}
    if nom == "Read":
        return f"Lit {_fichier(entree)}"
    if nom == "Write":
        return f"Écrit {_fichier(entree)}"
    if nom in ("Edit", "MultiEdit", "NotebookEdit"):
        return f"Modifie {_fichier(entree)}"
    if nom == "Bash":
        return f"Commande : {_court(entree.get('description') or entree.get('command'))}"
    if nom in ("Grep", "Glob"):
        return f"Cherche « {_court(entree.get('pattern'), 40)} »"
    if nom in ("WebFetch", "WebSearch"):
        return f"Consulte le web : {_court(entree.get('query') or entree.get('url'), 50)}"
    if nom in ("Task", "Agent"):
        return f"Délègue : {_court(entree.get('description'), 50)}"
    if nom == "Skill":
        return f"Utilise le skill {_court(entree.get('skill'), 40)}"
    if nom.startswith("mcp__"):
        parties = nom.split("__")
        service = parties[1].replace("claude_ai_", "").replace("_", " ") if len(parties) > 1 else nom
        action = parties[2] if len(parties) > 2 else ""
        return f"{service} : {action.replace('_', ' ')}".strip()
    return nom


def etat(nom: str) -> str:
    """État de l'orbe pendant l'utilisation de cet outil."""
    if nom in ("Read", "Grep", "Glob", "WebFetch", "WebSearch") or nom.startswith("mcp__"):
        return "lit"
    if nom in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        return "ecrit"
    if nom == "Bash":
        return "commande"
    return "reflechit"
