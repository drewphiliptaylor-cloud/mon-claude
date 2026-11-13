import json

from app import quota

MAINTENANT = 1_794_527_200


def ecrire(tmp_path, contenu):
    f = tmp_path / "quota.json"
    f.write_text(json.dumps(contenu), encoding="utf-8")
    return f


def test_lit_les_deux_fenetres(tmp_path):
    f = ecrire(tmp_path, {"five_hour": {"used_percentage": 68.4, "resets_at": MAINTENANT + 3600},
                          "seven_day": {"used_percentage": 17, "resets_at": MAINTENANT + 86400}, "vu_le": MAINTENANT - 30})
    assert quota.lire(f, MAINTENANT) == {"cinq_heures": {"pourcentage": 68, "reinit": MAINTENANT + 3600},
                                         "sept_jours": {"pourcentage": 17, "reinit": MAINTENANT + 86400}, "vu_le": MAINTENANT - 30}


def test_valeur_perimee_ignoree(tmp_path):
    f = ecrire(tmp_path, {"five_hour": {"used_percentage": 50}, "vu_le": MAINTENANT - 7 * 3600})
    assert quota.lire(f, MAINTENANT) is None, "une valeur de plus de 6 h ne doit pas s'afficher comme actuelle"


def test_fenetre_deja_remise_a_zero(tmp_path):
    f = ecrire(tmp_path, {"five_hour": {"used_percentage": 90, "resets_at": MAINTENANT - 10}, "vu_le": MAINTENANT - 60})
    assert quota.lire(f, MAINTENANT)["cinq_heures"] == {"pourcentage": 0}


def test_fichier_absent_ou_corrompu(tmp_path):
    assert quota.lire(tmp_path / "absent.json", MAINTENANT) is None
    (tmp_path / "x.json").write_text("{pas du json", encoding="utf-8")
    assert quota.lire(tmp_path / "x.json", MAINTENANT) is None


def test_pourcentage_absurde_rejete(tmp_path):
    f = ecrire(tmp_path, {"five_hour": {"used_percentage": 250}, "seven_day": {"used_percentage": "beaucoup"}, "vu_le": MAINTENANT})
    assert quota.lire(f, MAINTENANT) is None


# ---------- /usage (sans terminal) ----------
USAGE = """You are currently using your subscription to power your Claude Code usage

Current session: 42% used · resets Nov 13 at 1:50pm (Europe/Paris)
Current week (all models): 31% used · resets Nov 14 at 10pm (Europe/Paris)
Current week (Fable): 0% used · resets Nov 14 at 10pm (Europe/Paris)
"""
LE_13_NOV = 1_794_566_743  # 13/11/2026 vers 11 h 45, heure de Paris


def test_usage_lu_comme_la_status_line():
    # mêmes horodatages de remise à zéro que ceux écrits par la status line le même jour
    assert quota.analyser_usage(USAGE, LE_13_NOV) == {
        "cinq_heures": {"pourcentage": 42, "reinit": 1_794_574_200},
        "sept_jours": {"pourcentage": 31, "reinit": 1_794_690_000}, "vu_le": LE_13_NOV}


def test_usage_semaine_fable_ignoree():
    seul = "Current week (Fable): 80% used · resets Nov 14 at 10pm (Europe/Paris)"
    assert quota.analyser_usage(seul, LE_13_NOV) is None, "le quota d'un seul modèle n'est pas le quota global"


def test_usage_texte_inconnu_ou_vide():
    assert quota.analyser_usage("", LE_13_NOV) is None
    assert quota.analyser_usage("Unknown command: /usage", LE_13_NOV) is None
    assert quota.analyser_usage("Current session: 250% used", LE_13_NOV) is None


def test_usage_sans_heure_de_remise_a_zero():
    r = quota.analyser_usage("Current session: 7% used\nCurrent week (all models): 3% used · resets soon", LE_13_NOV)
    assert r["cinq_heures"] == {"pourcentage": 7} and r["sept_jours"] == {"pourcentage": 3}


def test_usage_remise_a_zero_apres_le_nouvel_an():
    le_30_dec = 1_798_610_400  # 30/12/2026
    r = quota.analyser_usage("Current week (all models): 5% used · resets Jan 2 at 9am (Europe/Paris)", le_30_dec)
    assert r["sept_jours"]["reinit"] > le_30_dec
