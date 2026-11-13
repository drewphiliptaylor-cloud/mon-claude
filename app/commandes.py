"""Commandes « / » proposées dans les conversations : skills de l'utilisateur, skills des plugins, commandes utiles.

La liste des noms vient de Claude Code lui-même (message d'initialisation d'une conversation),
les descriptions sont lues dans les fichiers SKILL.md. Avant la première conversation, on se
contente des skills trouvés sur le disque.
"""
import re
from pathlib import Path
from typing import Optional

# Commandes intégrées utiles hors terminal, avec une description en français.
INTEGREES = {
    "compact": "Résumer la conversation pour libérer de la place",
    "context": "Voir ce qui occupe la mémoire de la conversation",
    "init": "Créer un CLAUDE.md qui décrit le dossier de travail",
    "review": "Relire une demande de fusion (pull request)",
    "security-review": "Passer les changements en cours au crible de la sécurité",
    "code-review": "Relire le code modifié",
    "simplify": "Simplifier le code modifié",
    "usage": "Voir la consommation de ton forfait",
}
# ponytail: liste écrite à la main des commandes qui n'ont de sens que dans le terminal interactif.
# Plafond : une nouvelle commande de terminal apparaîtra jusqu'à ce qu'on l'ajoute ici.
# Upgrade : se fier uniquement à `terminal_slash_commands` si Claude Code la complète un jour.
TERMINAL = {"doctor", "color", "focus", "reload-plugins", "reload-skills", "config", "model", "fast", "effort", "output-style",
            "heapdump", "mcp", "agents", "list-agents", "rename", "clear", "autocompact", "auto-mode-setup", "import",
            "__remote-workflow", "workflow-launch-exec", "usage-credits", "extra-usage", "design-consent", "design-revoke",
            "team-onboarding", "advisor", "ultrareview", "insights", "goal", "loop", "schedule", "batch", "skill-doctor",
            "fewer-permission-prompts", "plugin-authoring", "run-skill-generator", "recap", "bye", "fermer-sessions"}
_NOM = re.compile(r"^[a-zA-Z0-9_:.-]{1,80}$")


def _frontmatter(chemin: Path) -> dict:
    try:
        texte = chemin.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    if not texte.startswith("---"):
        return {}
    fin = texte.find("\n---", 3)
    meta = {}
    for l in texte[3:fin if fin > 0 else len(texte)].splitlines():
        cle, sep, val = l.partition(":")
        if sep and cle.strip() in ("name", "description"):
            meta[cle.strip()] = val.strip().strip('"').strip("'")
    return meta


def _resume(description: str) -> str:
    d = re.sub(r"^Use (quand|when)\s+", "", description.strip(), flags=re.I)
    d = d.split(" — ")[0].split(". ")[0]
    return (d[:1].upper() + d[1:])[:140] if d else ""


def descriptions(dossier_claude: Path, plugins: Optional[list] = None) -> dict:
    sortie = {}
    for f in sorted((dossier_claude / "skills").glob("*/SKILL.md")):
        meta = _frontmatter(f)
        sortie[meta.get("name") or f.parent.name] = _resume(meta.get("description", ""))
    for f in sorted((dossier_claude / "commands").glob("*.md")):
        sortie[f.stem] = _resume(_frontmatter(f).get("description", ""))
    for p in plugins or []:
        racine = Path(str(p.get("path", "")))
        nom_plugin = str(p.get("name", ""))
        if not nom_plugin or not racine.is_dir():
            continue
        for f in sorted(racine.glob("skills/*/SKILL.md")):
            meta = _frontmatter(f)
            sortie[f"{nom_plugin}:{meta.get('name') or f.parent.name}"] = _resume(meta.get("description", ""))
    return sortie


def liste(noms: Optional[list], terminal: Optional[list], descr: dict) -> list:
    """Commandes à proposer : skills d'abord (ceux de l'utilisateur en tête), puis commandes intégrées utiles."""
    exclues = TERMINAL | set(terminal or [])
    candidats = list(noms) if noms else list(descr.keys()) + list(INTEGREES.keys())
    vus, sortie = set(), []
    for n in candidats:
        if not isinstance(n, str) or not _NOM.match(n) or n in exclues or n in vus or n.startswith("__"):
            continue
        vus.add(n)
        if n in INTEGREES:
            sortie.append({"nom": n, "description": INTEGREES[n], "genre": "commande"})
        elif n in descr:
            sortie.append({"nom": n, "description": descr[n], "genre": "skill"})
    ordre = {"skill": 0, "commande": 1}
    sortie.sort(key=lambda c: (ordre[c["genre"]], ":" in c["nom"], c["nom"]))
    return sortie
