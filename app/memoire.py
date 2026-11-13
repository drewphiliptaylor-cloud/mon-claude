"""« Ce que je retiens » : la mémoire de Claude sur l'utilisateur, lue en clair (lecture seule).

Source : le dossier mémoire de Claude Code (~/.claude/projects/<dossier>/memory/*.md).
"""
import re
from pathlib import Path

TYPES = {"user": "Qui tu es", "feedback": "Comment travailler avec toi", "project": "Projets en cours", "reference": "Références"}


def _decouper(texte: str) -> tuple:
    if not texte.startswith("---"):
        return {}, texte
    fin = texte.find("\n---", 3)
    if fin < 0:
        return {}, texte
    meta = {}
    for l in texte[3:fin].splitlines():
        m = re.match(r"^\s*(name|description|type)\s*:\s*(.*)$", l)
        if m:
            meta[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return meta, texte[fin + 4:].lstrip("\n")


def souvenirs(dossier: Path) -> list:
    if not dossier.is_dir():
        return []
    sortie = []
    for f in sorted(dossier.glob("*.md")):
        if f.name == "MEMORY.md" or f.is_symlink():
            continue
        meta, corps = _decouper(f.read_text(encoding="utf-8", errors="replace"))
        genre = meta.get("type", "")
        sortie.append({"fichier": f.name, "nom": meta.get("name") or f.stem, "description": meta.get("description", ""),
                       "type": genre, "rubrique": TYPES.get(genre, "Autres"), "texte": corps.strip()[:8000],
                       "modifie": int(f.stat().st_mtime)})
    ordre = list(TYPES.values()) + ["Autres"]
    sortie.sort(key=lambda s: (ordre.index(s["rubrique"]), -s["modifie"]))
    return sortie
