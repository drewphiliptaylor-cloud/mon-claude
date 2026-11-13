import tempfile
from datetime import date

import pytest
from app import rapide

JEUDI = date(2026, 11, 12)


def test_proposition_propre_conservee():
    p = rapide.valider({"genre": "agenda", "titre": "Coiffeur", "dates_possibles": ["2026-11-12", "2026-11-19"],
                        "heure": "10:30", "duree_minutes": 45, "section": "Perso", "priorite": "moyenne",
                        "question": "Ce jeudi ou le suivant ?"}, JEUDI)
    assert p["dates_possibles"] == ["2026-11-12", "2026-11-19"] and p["heure"] == "10:30" and p["duree_minutes"] == 45


def test_champs_douteux_vides_plutot_que_devines():
    p = rapide.valider({"genre": "pirate", "titre": "x" * 500, "dates_possibles": ["demain", "2026-02-30", "1999-01-01"],
                        "heure": "25:00", "duree_minutes": "beaucoup", "section": "Vacances", "priorite": "!!"}, JEUDI)
    assert p["genre"] == "conversation", "un genre inconnu doit renvoyer vers une conversation"
    assert len(p["titre"]) == 120
    assert p["dates_possibles"] == [] and p["heure"] == "", "dates et heures invalides doivent être vidées"
    assert p["section"] == "Perso" and p["priorite"] == "moyenne"


def test_rendez_vous_sans_duree_dure_une_heure():
    assert rapide.valider({"genre": "agenda", "duree_minutes": 0}, JEUDI)["duree_minutes"] == 60


def test_sortie_absente_devient_conversation():
    assert rapide.valider(None, JEUDI)["genre"] == "conversation"


def test_consignes_donnent_le_jour_et_l_ambiguite():
    c = rapide.consignes(JEUDI)
    assert "jeudi 2026-11-12" in c and "« ce jeudi »" in c


def test_consigne_de_creation_precise():
    c = rapide.consigne_creation({"titre": "Coiffeur", "date": "2026-11-19", "heure": "10:30", "duree_minutes": 45})
    assert "2026-11-19T10:30:00" in c and "45 minutes" in c and "'Coiffeur'" in c


@pytest.mark.reel
async def test_reel_coiffeur_ce_jeudi():
    with tempfile.TemporaryDirectory() as d:
        p = await rapide.proposer("ajoute dans mon agenda le rdv coiffeur de ce jeudi", JEUDI, cwd=d)
    assert p["genre"] == "agenda", p
    assert p["titre"].lower().startswith("coiffeur"), p
    assert p["heure"] == "", "aucune heure n'a été donnée"
    assert "2026-11-19" in p["dates_possibles"], p
    assert p["question"], "il manque au moins l'heure"


@pytest.mark.reel
async def test_reel_creation_agenda_a_blanc_rien_n_est_ecrit():
    """Claude prépare bien l'appel au connecteur Google Agenda avec les bons champs ; l'appel est refusé."""
    with tempfile.TemporaryDirectory() as d:
        r = await rapide.creer_evenement({"titre": "Coiffeur", "date": "2026-11-19", "heure": "10:30", "duree_minutes": 45},
                                         cwd=d, essai_a_blanc=True)
    assert r["ok"] is False, "un essai à blanc ne doit jamais réussir"
    appels = [x for x in r["demandes"] if x["outil"] == rapide.OUTIL_AGENDA]
    assert appels, f"Claude doit demander l'outil create_event : {r}"
    entree = str(appels[0]["entree"])
    assert "Coiffeur" in entree and "2026-11-19" in entree and "10:30" in entree, entree


@pytest.mark.reel
async def test_reel_tache_simple():
    with tempfile.TemporaryDirectory() as d:
        p = await rapide.proposer("ajoute à ma to-do : rappeler le menuisier", JEUDI, cwd=d)
    assert p["genre"] == "tache" and "menuisier" in p["titre"].lower(), p
