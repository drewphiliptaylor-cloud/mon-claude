"""Dictée locale : un enregistrement WAV venu de la page est transcrit par whisper-cpp, sans Internet.

whisper-cli (Homebrew : brew install whisper-cpp) + modèle large-v3-turbo dans ~/.dashboard-claude/modeles.
Le texte revient dans la zone de saisie ; il n'est jamais envoyé à Claude automatiquement.
"""
import os
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

TAILLE_MAX = 12 * 1024 * 1024   # ~6 min en 16 kHz mono 16 bits
DUREE_MIN = 0.3                 # secondes
DELAI = 180                     # secondes de transcription au maximum


class DicteeErreur(Exception):
    """Message lisible par l'utilisateur."""


def binaire() -> str:
    return os.environ.get("DASHBOARD_WHISPER") or shutil.which("whisper-cli") or "/opt/homebrew/bin/whisper-cli"


def modele() -> Path:
    return Path(os.path.expanduser(os.environ.get("DASHBOARD_WHISPER_MODELE", "~/.dashboard-claude/modeles/ggml-large-v3-turbo-q5_0.bin")))


def etat() -> dict:
    b, m = binaire(), modele()
    if not (os.path.isfile(b) and os.access(b, os.X_OK)):
        return {"disponible": False, "raison": "whisper-cli introuvable (brew install whisper-cpp)."}
    if not m.is_file():
        return {"disponible": False, "raison": f"Modèle de transcription introuvable : {m}"}
    return {"disponible": True}


def valider_wav(donnees: bytes) -> float:
    """Vérifie un WAV PCM 16 bits mono 16 kHz ; renvoie sa durée en secondes."""
    if len(donnees) > TAILLE_MAX:
        raise DicteeErreur("Enregistrement trop long (6 minutes maximum).")
    if len(donnees) < 44 or donnees[:4] != b"RIFF" or donnees[8:12] != b"WAVE":
        raise DicteeErreur("Le fichier reçu n'est pas un enregistrement WAV.")
    pos, fmt, taille_donnees = 12, None, None
    while pos + 8 <= len(donnees):
        nom, taille = donnees[pos:pos + 4], struct.unpack("<I", donnees[pos + 4:pos + 8])[0]
        if nom == b"fmt ":
            fmt = struct.unpack("<HHIIHH", donnees[pos + 8:pos + 24])
        elif nom == b"data":
            taille_donnees = min(taille, len(donnees) - pos - 8)
            break
        pos += 8 + taille + (taille % 2)
    if fmt is None or taille_donnees is None:
        raise DicteeErreur("Enregistrement WAV incomplet.")
    format_audio, canaux, frequence, _, _, bits = fmt
    if (format_audio, canaux, frequence, bits) != (1, 1, 16000, 16):
        raise DicteeErreur("Format attendu : WAV PCM 16 bits, mono, 16 kHz.")
    duree = taille_donnees / (16000 * 2)
    if duree < DUREE_MIN:
        raise DicteeErreur("Enregistrement trop court : parle un peu plus longtemps.")
    return duree


def transcrire(donnees: bytes, langue: str = "fr") -> str:
    valider_wav(donnees)
    e = etat()
    if not e["disponible"]:
        raise DicteeErreur(e["raison"])
    with tempfile.TemporaryDirectory(prefix="dictee-") as d:
        chemin = Path(d) / "dictee.wav"
        chemin.write_bytes(donnees)
        try:
            r = subprocess.run([binaire(), "-m", str(modele()), "-l", langue, "-f", str(chemin), "-nt", "-np"],
                               capture_output=True, text=True, timeout=DELAI)
        except subprocess.TimeoutExpired as ex:
            raise DicteeErreur("La transcription a pris trop de temps.") from ex
    if r.returncode != 0:
        raise DicteeErreur("whisper n'a pas pu transcrire l'enregistrement.")
    return nettoyer(" ".join(l.strip() for l in r.stdout.splitlines() if l.strip()))


# Sur du silence, whisper « entend » des génériques de sous-titres : ce n'est pas ce que l'utilisateur a dit.
_HALLUCINATIONS = ("[blank_audio]", "[ silence ]", "(silence)", "sous-titrage société radio-canada",
                   "sous-titres réalisés par la communauté d'amara.org", "merci d'avoir regardé cette vidéo",
                   "sous-titrage st' 501", "sous-titrage st'501")


def nettoyer(texte: str) -> str:
    t = texte.strip()
    if t.lower().strip(" .!") in _HALLUCINATIONS or not t.strip(" .,!?-"):
        return ""
    return t
