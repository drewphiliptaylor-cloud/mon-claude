"""Réglages du dashboard : tous les chemins sont configurables par variable d'environnement.

Portabilité : rien ici n'est propre au Mac, pour pouvoir migrer un jour l'hébergement.
"""
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def _dossier_projet(chemin: Path) -> str:
    """Nom du dossier que Claude Code donne à un répertoire : /Users/alex → -Users-alex."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(chemin))


def _chemin(var: str, defaut: str) -> Path:
    return Path(os.path.expanduser(os.environ.get(var, defaut))).resolve()


@dataclass
class Config:
    port: int = field(default_factory=lambda: int(os.environ.get("DASHBOARD_PORT", "8765")))
    # Hors du dossier du code : survit aux mises à jour, jamais envoyé sur GitHub (contient le lien iCal secret).
    donnees: Path = field(default_factory=lambda: _chemin("DASHBOARD_DATA", "~/.dashboard-claude"))
    taches: Path = field(default_factory=lambda: _chemin("DASHBOARD_TACHES", "~/todo/taches.md"))
    todo_ice: Path = field(default_factory=lambda: _chemin("DASHBOARD_TODO_ICE", "~/todo/todo.md"))
    vault: Path = field(default_factory=lambda: _chemin("DASHBOARD_VAULT", "~/Documents/Vault"))
    claude_md: Path = field(default_factory=lambda: _chemin("DASHBOARD_CLAUDE_MD", "~/.claude/CLAUDE.md"))
    dossier_travail: Path = field(default_factory=lambda: _chemin("DASHBOARD_DOSSIER", "~"))
    memoire: Path = field(default_factory=lambda: _chemin("DASHBOARD_MEMOIRE", f"~/.claude/projects/{_dossier_projet(Path.home())}/memory"))
    travaux: Path = field(default_factory=lambda: _chemin("DASHBOARD_TRAVAUX", "~/.claude/jobs"))
    maquettes: Path = RACINE / "maquettes"
    web: Path = RACINE / "web"

    @property
    def base(self) -> Path:
        return self.donnees / "dashboard.db"

    @property
    def images(self) -> Path:
        return self.donnees / "images"

    @property
    def interne(self) -> Path:
        """Dossier de travail des appels internes (action rapide) : exclu de l'historique."""
        return self.donnees / "interne"

    def preparer(self) -> None:
        for d in (self.donnees, self.images, self.interne):
            d.mkdir(parents=True, exist_ok=True)
