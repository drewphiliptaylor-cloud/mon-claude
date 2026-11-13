from app.securite import requete_autorisee, type_image, TAILLE_MAX_IMAGE
from app.store import Store


def test_hote_et_origine_locales_acceptees():
    assert requete_autorisee("127.0.0.1:8765", None, 8765)
    assert requete_autorisee("localhost:8765", "http://localhost:8765", 8765)


def test_autre_site_refuse():
    assert not requete_autorisee("127.0.0.1:8765", "https://evil.example", 8765)


def test_hote_piege_refuse():
    assert not requete_autorisee("evil.example:8765", None, 8765)
    assert not requete_autorisee(None, None, 8765)
    assert not requete_autorisee("127.0.0.1:9999", None, 8765)


def test_images_reconnues_par_signature():
    assert type_image(b"\x89PNG\r\n\x1a\n" + b"0" * 10) == ("image/png", "png")
    assert type_image(b"\xff\xd8\xff\xe0" + b"0" * 10) == ("image/jpeg", "jpg")
    assert type_image(b"RIFF1234WEBPVP8 ") == ("image/webp", "webp")


def test_faux_fichier_et_trop_gros_refuses():
    assert type_image(b"<html>pas une image</html>") is None
    assert type_image(b"") is None
    assert type_image(b"\x89PNG\r\n\x1a\n" + b"0" * TAILLE_MAX_IMAGE) is None


def test_store_aller_retour(tmp_path):
    s = Store(tmp_path / "t.db")
    assert s.get("absent", 42) == 42
    s.set("teinte", {"a": "#e5a00d", "nom": "Ambre é"})
    assert Store(tmp_path / "t.db").get("teinte") == {"a": "#e5a00d", "nom": "Ambre é"}
    s.set("teinte", [1, 2])
    assert s.get("teinte") == [1, 2]
    s.supprimer("teinte")
    assert s.get("teinte") is None


def test_dossier_memoire_calcule_pour_chaque_utilisateur():
    from pathlib import Path
    from app.config import _dossier_projet
    assert _dossier_projet(Path("/Users/alex")) == "-Users-alex"
    assert _dossier_projet(Path("/Users/jean.dupont")) == "-Users-jean-dupont"
