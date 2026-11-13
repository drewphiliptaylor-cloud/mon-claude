"""Tâches simples de l'utilisateur dans un fichier Markdown lisible et modifiable à la main.

Format (`~/todo/taches.md`) :

    # Tâches
    ## Pro
    - [ ] Commander les plaques de liège !haute
    - [x] Choisir l'ambiance du dashboard
    ## Perso
    - [ ] Rappeler le menuisier !basse

Règles anti-perte : on relit toujours le fichier juste avant d'écrire, on ne touche
qu'à la ligne visée, toutes les autres lignes (même inconnues) sont conservées, et
l'écriture est atomique (fichier temporaire puis renommage).
"""
import hashlib
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Optional

SECTIONS = ("Pro", "Perso")
PRIORITES = ("haute", "moyenne", "basse")
_LIGNE = re.compile(r"^(\s*)- \[( |x|X)\] (.*?)\s*$")
_PRIO = re.compile(r"\s+!(haute|basse)$")
_TITRE_ICE = re.compile(r"^###\s+\[ICE\s+(\d+)\]\s+(.+?)(?:\s+—\s+ajouté.*)?$")
_verrou = threading.Lock()


class TacheIntrouvable(Exception):
    """La tâche a été modifiée ou supprimée ailleurs depuis le dernier affichage."""


def _id(section: str, texte_brut: str, rang: int) -> str:
    return hashlib.sha1(f"{section}\n{texte_brut}\n{rang}".encode()).hexdigest()[:12]


def _analyser(lignes: list) -> list:
    """Renvoie la liste des tâches avec leur numéro de ligne."""
    taches, section, vus = [], None, {}
    for i, ligne in enumerate(lignes):
        if ligne.startswith("## "):
            section = ligne[3:].strip()
            continue
        m = _LIGNE.match(ligne)
        if not m or section is None:
            continue
        brut = m.group(3)
        p = _PRIO.search(brut)
        priorite = p.group(1) if p else "moyenne"
        texte = _PRIO.sub("", brut).strip()
        cle = (section, brut)
        vus[cle] = vus.get(cle, -1) + 1
        taches.append({"id": _id(section, brut, vus[cle]), "section": section, "texte": texte,
                       "fait": m.group(2).lower() == "x", "priorite": priorite, "_ligne": i})
    return taches


def _lire_lignes(chemin: Path) -> list:
    if not chemin.exists():
        return ["# Tâches", "", "## Pro", "", "## Perso", ""]
    return chemin.read_text(encoding="utf-8").splitlines()


def _ecrire(chemin: Path, lignes: list) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(chemin.parent), prefix=".taches-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(lignes).rstrip("\n") + "\n")
        os.replace(tmp, chemin)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _publique(t: dict) -> dict:
    return {k: v for k, v in t.items() if not k.startswith("_")}


def lire(chemin: Path, todo_ice: Optional[Path] = None) -> dict:
    taches = [_publique(t) for t in _analyser(_lire_lignes(chemin))]
    ice = []
    if todo_ice and todo_ice.exists():
        for ligne in todo_ice.read_text(encoding="utf-8").splitlines():
            m = _TITRE_ICE.match(ligne.strip())
            if m:
                ice.append({"score": int(m.group(1)), "titre": m.group(2).strip()})
    return {"taches": taches, "ice": ice}


def ajouter(chemin: Path, texte: str, section: str = "Perso", priorite: str = "moyenne") -> dict:
    texte = " ".join(texte.split())
    if not texte:
        raise ValueError("La tâche est vide.")
    if len(texte) > 300:
        raise ValueError("La tâche dépasse 300 caractères.")
    if section not in SECTIONS:
        raise ValueError(f"Section inconnue : {section}")
    if priorite not in PRIORITES:
        raise ValueError(f"Priorité inconnue : {priorite}")
    brut = texte + ("" if priorite == "moyenne" else f" !{priorite}")
    with _verrou:
        lignes = _lire_lignes(chemin)
        titre = f"## {section}"
        if titre not in lignes:
            if lignes and lignes[-1].strip():
                lignes.append("")
            lignes += [titre, ""]
        debut = lignes.index(titre)
        # insérer après la dernière tâche de la section (ou juste sous le titre)
        pos = debut + 1
        for i in range(debut + 1, len(lignes)):
            if lignes[i].startswith("## "):
                break
            if _LIGNE.match(lignes[i]):
                pos = i + 1
        lignes.insert(pos, f"- [ ] {brut}")
        _ecrire(chemin, lignes)
        ajoutee = [t for t in _analyser(lignes) if t["_ligne"] == pos][0]
    return _publique(ajoutee)


def _trouver(lignes: list, id_: str) -> dict:
    for t in _analyser(lignes):
        if t["id"] == id_:
            return t
    raise TacheIntrouvable(id_)


def basculer(chemin: Path, id_: str) -> dict:
    with _verrou:
        lignes = _lire_lignes(chemin)
        t = _trouver(lignes, id_)
        i = t["_ligne"]
        lignes[i] = re.sub(r"- \[( |x|X)\]", "- [ ]" if t["fait"] else "- [x]", lignes[i], count=1)
        _ecrire(chemin, lignes)
        return _publique(_analyser(lignes)[[x["_ligne"] for x in _analyser(lignes)].index(i)])


def supprimer(chemin: Path, id_: str) -> None:
    with _verrou:
        lignes = _lire_lignes(chemin)
        t = _trouver(lignes, id_)
        del lignes[t["_ligne"]]
        _ecrire(chemin, lignes)
