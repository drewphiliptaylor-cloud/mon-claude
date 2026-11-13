"""Projets de l'utilisateur : tableau « Mes projets actifs » du CLAUDE.md global + notes de session du vault.

Lecture seule : le dashboard ne modifie jamais ces fichiers.
"""
import re
from pathlib import Path

_SEP = re.compile(r"^\|\s*:?-{2,}")


def _cellules(ligne: str) -> list:
    return [c.strip() for c in ligne.strip().strip("|").split("|")]


def _nettoyer(texte: str) -> str:
    return texte.replace("`", "").replace("**", "").strip()


def projets(claude_md: Path) -> list:
    if not claude_md.exists():
        return []
    lignes = claude_md.read_text(encoding="utf-8").splitlines()
    try:
        debut = next(i for i, l in enumerate(lignes) if l.startswith("## ") and "projets" in l.lower())
    except StopIteration:
        return []
    sortie, entete = [], None
    for l in lignes[debut + 1:]:
        if l.startswith("## "):
            break
        if not l.strip().startswith("|"):
            continue
        if _SEP.match(l.strip()):
            continue
        cellules = _cellules(l)
        if entete is None:
            entete = cellules
            continue
        if len(cellules) < 3:
            continue
        nom, emplacement, etat = (_nettoyer(c) for c in cellules[:3])
        statut, _, detail = etat.partition("—")
        sortie.append({"nom": nom, "emplacement": emplacement, "statut": statut.strip(),
                       "detail": detail.strip().removeprefix("reste :").strip() if detail else ""})
    return sortie


def dossier(emplacement: str):
    """Premier chemin existant cité dans la colonne Emplacement (« `~/.claude/` + kit … » → ~/.claude)."""
    import os
    for mot in emplacement.replace("`", " ").split():
        if mot.startswith(("~/", "/")):
            chemin = Path(os.path.expanduser(mot)).resolve()
            if chemin.is_dir():
                return chemin
    return None


def _frontmatter(texte: str) -> dict:
    if not texte.startswith("---"):
        return {}
    fin = texte.find("\n---", 3)
    if fin < 0:
        return {}
    meta = {}
    for l in texte[3:fin].splitlines():
        cle, sep, val = l.partition(":")
        if sep:
            meta[cle.strip()] = val.strip().strip('"')
    return meta


def notes_recentes(vault: Path, n: int = 20) -> list:
    dossier = vault / "06_Claude" / "sessions"
    if not dossier.is_dir():
        return []
    sortie = []
    for f in sorted(dossier.glob("*.md"), reverse=True)[:n]:
        if f.name.lower() == "readme.md":
            continue
        texte = f.read_text(encoding="utf-8", errors="replace")
        meta = _frontmatter(texte)
        titre = next((l[2:].strip() for l in texte.splitlines() if l.startswith("# ")), f.stem)
        titre = titre.split("—", 1)[1].strip() if "—" in titre else titre
        projets_note = [p.strip() for p in meta.get("projets", "").strip("[]").split(",") if p.strip()]
        sortie.append({"fichier": f.name, "titre": titre, "date": meta.get("date", ""), "heure": meta.get("heure", ""),
                       "statut": meta.get("statut", ""), "projets": projets_note})
    return sortie


def projets_avec_notes(claude_md: Path, vault: Path) -> list:
    notes = notes_recentes(vault, 60)
    sortie = []
    for p in projets(claude_md):
        derniere = next((x for x in notes if p["nom"] in x["projets"]), None)
        d = dossier(p["emplacement"])
        sortie.append({**p, "derniere_note": derniere, "dossier": str(d) if d else None})
    return sortie
