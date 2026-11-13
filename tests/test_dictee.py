import shutil
import struct
import subprocess
from pathlib import Path

import pytest
from app import dictee


def wav(frequence=16000, canaux=1, bits=16, secondes=1.0, donnees=None):
    if donnees is None:
        donnees = b"\x00\x00" * int(frequence * secondes) * canaux
    octets_par_s = frequence * canaux * bits // 8
    fmt = struct.pack("<HHIIHH", 1, canaux, frequence, octets_par_s, canaux * bits // 8, bits)
    return (b"RIFF" + struct.pack("<I", 36 + len(donnees)) + b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt
            + b"data" + struct.pack("<I", len(donnees)) + donnees)


def test_wav_conforme_accepte():
    assert dictee.valider_wav(wav(secondes=2)) == pytest.approx(2.0)


@pytest.mark.parametrize("contenu, motif", [
    (b"<html>", "pas un enregistrement"),
    (wav(frequence=44100), "16 kHz"),
    (wav(canaux=2), "mono"),
    (wav(secondes=0.1), "trop court"),
])
def test_fichiers_non_conformes_refuses(contenu, motif):
    with pytest.raises(dictee.DicteeErreur, match=motif):
        dictee.valider_wav(contenu)


@pytest.mark.parametrize("brut", ["Sous-titrage Société Radio-Canada", "[BLANK_AUDIO]", " . ", "Merci d'avoir regardé cette vidéo !"])
def test_hallucinations_sur_silence_ignorees(brut):
    assert dictee.nettoyer(brut) == "", "du silence ne doit pas devenir un faux texte"


def test_vraie_phrase_conservee():
    assert dictee.nettoyer(" Appelle le fournisseur. ") == "Appelle le fournisseur."


def test_trop_long_refuse():
    with pytest.raises(dictee.DicteeErreur, match="trop long"):
        dictee.valider_wav(b"RIFF" + b"\x00" * (dictee.TAILLE_MAX + 1))


def test_whisper_absent_message_clair(monkeypatch, tmp_path):
    monkeypatch.setenv("DASHBOARD_WHISPER", str(tmp_path / "absent"))
    assert dictee.etat() == {"disponible": False, "raison": "whisper-cli introuvable (brew install whisper-cpp)."}
    with pytest.raises(dictee.DicteeErreur, match="introuvable"):
        dictee.transcrire(wav(secondes=1))


@pytest.mark.reel
@pytest.mark.skipif(not shutil.which("say") or not dictee.etat()["disponible"], reason="say ou whisper absent")
def test_reel_transcription_d_une_voix_de_synthese(tmp_path):
    aiff, sortie = tmp_path / "v.aiff", tmp_path / "v.wav"
    subprocess.run(["say", "-v", "Thomas", "-o", str(aiff), "Bonjour Claude, ajoute une tâche à ma liste."], check=True)
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(aiff), str(sortie)], check=True)
    texte = dictee.transcrire(sortie.read_bytes()).lower()
    assert "bonjour" in texte and "tâche" in texte, texte
