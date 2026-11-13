import pytest
from app import taches

EXEMPLE = """# Tâches
Une note libre que l'utilisateur a écrite à la main.

## Pro
- [ ] Commander les plaques de liège !haute
- [x] Choisir l'ambiance
## Perso
- [ ] Rappeler le menuisier !basse
"""


@pytest.fixture
def fichier(tmp_path):
    f = tmp_path / "taches.md"
    f.write_text(EXEMPLE, encoding="utf-8")
    return f


def test_lit_sections_priorites_et_etat(fichier):
    t = taches.lire(fichier)["taches"]
    assert [(x["section"], x["texte"], x["priorite"], x["fait"]) for x in t] == [
        ("Pro", "Commander les plaques de liège", "haute", False),
        ("Pro", "Choisir l'ambiance", "moyenne", True),
        ("Perso", "Rappeler le menuisier", "basse", False),
    ], "les trois tâches doivent être lues avec section, priorité et état"


def test_fichier_absent_donne_une_liste_vide(tmp_path):
    assert taches.lire(tmp_path / "absent.md")["taches"] == []


def test_ajout_dans_la_bonne_section_sans_perdre_les_lignes_libres(fichier):
    nouvelle = taches.ajouter(fichier, "Préparer l'atelier", "Pro", "haute")
    texte = fichier.read_text(encoding="utf-8")
    assert "Une note libre que l'utilisateur a écrite à la main." in texte, "une ligne libre a été perdue"
    assert "- [ ] Préparer l'atelier !haute\n## Perso" in texte, "la tâche doit aller à la fin de la section Pro"
    assert nouvelle["texte"] == "Préparer l'atelier" and nouvelle["section"] == "Pro"


def test_ajout_cree_le_fichier_et_la_section(tmp_path):
    f = tmp_path / "sous" / "taches.md"
    taches.ajouter(f, "Coiffeur", "Perso")
    assert [x["texte"] for x in taches.lire(f)["taches"]] == ["Coiffeur"]


def test_ajout_refuse_vide_trop_long_et_section_inconnue(fichier):
    for args in (("   ", "Pro"), ("x" * 301, "Pro"), ("ok", "Vacances")):
        with pytest.raises(ValueError):
            taches.ajouter(fichier, *args)
    with pytest.raises(ValueError):
        taches.ajouter(fichier, "ok", "Pro", "urgente")


def test_basculer_coche_puis_decoche_et_garde_le_meme_id(fichier):
    t = taches.lire(fichier)["taches"][0]
    cochee = taches.basculer(fichier, t["id"])
    assert cochee["fait"] is True and cochee["id"] == t["id"], "l'id doit rester stable quand on coche"
    assert taches.basculer(fichier, t["id"])["fait"] is False


def test_modification_a_la_main_entre_deux_actions_est_respectee(fichier):
    t = taches.lire(fichier)["taches"][2]
    # L'utilisateur ajoute une ligne à la main pendant que le dashboard est ouvert
    fichier.write_text(fichier.read_text(encoding="utf-8") + "- [ ] Ajoutée à la main\n", encoding="utf-8")
    taches.basculer(fichier, t["id"])
    texte = fichier.read_text(encoding="utf-8")
    assert "- [ ] Ajoutée à la main" in texte, "la ligne ajoutée à la main a été écrasée"
    assert "- [x] Rappeler le menuisier !basse" in texte


def test_tache_disparue_signalee(fichier):
    t = taches.lire(fichier)["taches"][0]
    fichier.write_text("# Tâches\n## Pro\n", encoding="utf-8")
    with pytest.raises(taches.TacheIntrouvable):
        taches.basculer(fichier, t["id"])


def test_supprimer_ne_retire_que_la_ligne_visee(fichier):
    t = taches.lire(fichier)["taches"][1]
    taches.supprimer(fichier, t["id"])
    restantes = [x["texte"] for x in taches.lire(fichier)["taches"]]
    assert restantes == ["Commander les plaques de liège", "Rappeler le menuisier"]


def test_fiches_ice_lues_en_lecture_seule(fichier, tmp_path):
    ice = tmp_path / "todo.md"
    ice.write_text("## File\n### [ICE 60] Brancher le NAS  — ajouté 2026-11-12\n**Objectif** : …\n", encoding="utf-8")
    assert taches.lire(fichier, ice)["ice"] == [{"score": 60, "titre": "Brancher le NAS"}]
