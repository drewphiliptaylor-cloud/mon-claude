"""« Travaux en cours » : les sessions Claude Code qui tournent en arrière-plan (lecture seule).

Source : ~/.claude/jobs/<id>/state.json, écrit par Claude Code pour chaque travail de fond.
"""
import json
from pathlib import Path

ETATS = {"working": "En cours", "blocked": "Attend ta réponse", "done": "Terminé", "failed": "Échoué", "stopped": "Arrêté"}
ORDRE = {"working": 0, "blocked": 1}


def _texte(v, n=300) -> str:
    return " ".join(str(v).split())[:n] if isinstance(v, (str, int, float)) else ""


def lister(dossier: Path, limite: int = 20) -> list:
    if not dossier.is_dir():
        return []
    sortie = []
    for f in dossier.glob("*/state.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            maj = int(f.stat().st_mtime)
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        etat = _texte(d.get("state"), 20)
        besoin = d.get("needs")
        sortie.append({"id": f.parent.name[:40], "etat": etat, "libelle": ETATS.get(etat, etat or "Inconnu"),
                       "detail": _texte(d.get("detail")), "besoin": _texte(besoin) if besoin else "", "maj": maj})
    sortie.sort(key=lambda t: (ORDRE.get(t["etat"], 2), -t["maj"]))
    return sortie[:limite]
