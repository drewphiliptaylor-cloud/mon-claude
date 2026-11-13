"""Réglages persistants (disposition des widgets, teintes, lien iCal…) dans SQLite, en JSON."""
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, chemin: Path):
        chemin.parent.mkdir(parents=True, exist_ok=True)
        self._verrou = threading.Lock()
        self._cx = sqlite3.connect(str(chemin), check_same_thread=False)
        self._cx.execute("PRAGMA journal_mode=WAL")
        self._cx.execute("CREATE TABLE IF NOT EXISTS reglages (cle TEXT PRIMARY KEY, valeur TEXT NOT NULL)")
        self._cx.commit()

    def get(self, cle: str, defaut: Any = None) -> Any:
        with self._verrou:
            ligne = self._cx.execute("SELECT valeur FROM reglages WHERE cle = ?", (cle,)).fetchone()
        if ligne is None:
            return defaut
        try:
            return json.loads(ligne[0])
        except ValueError:
            return defaut

    def set(self, cle: str, valeur: Any) -> None:
        texte = json.dumps(valeur, ensure_ascii=False)
        with self._verrou:
            self._cx.execute("INSERT INTO reglages (cle, valeur) VALUES (?, ?) "
                             "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur", (cle, texte))
            self._cx.commit()

    def supprimer(self, cle: str) -> None:
        with self._verrou:
            self._cx.execute("DELETE FROM reglages WHERE cle = ?", (cle,))
            self._cx.commit()
