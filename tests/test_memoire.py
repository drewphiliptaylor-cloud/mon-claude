from app import memoire


def test_souvenirs_lus_ranges_par_rubrique(tmp_path):
    (tmp_path / "MEMORY.md").write_text("- index", encoding="utf-8")
    (tmp_path / "handy.md").write_text("---\nname: dicte-avec-handy\ndescription: Dicte avec Handy\nmetadata:\n  type: user\n---\n\nAlex dicte **parfois**.\n", encoding="utf-8")
    (tmp_path / "regle.md").write_text("---\nname: demander\ndescription: Demander avant\ntype: feedback\n---\nToujours demander.\n", encoding="utf-8")
    (tmp_path / "libre.md").write_text("Pas d'en-tête.\n", encoding="utf-8")
    s = memoire.souvenirs(tmp_path)
    assert [x["nom"] for x in s] == ["dicte-avec-handy", "demander", "libre"], "l'index MEMORY.md n'est pas un souvenir"
    assert s[0]["rubrique"] == "Qui tu es" and s[0]["texte"] == "Alex dicte **parfois**."
    assert s[1]["rubrique"] == "Comment travailler avec toi"
    assert s[2]["rubrique"] == "Autres"


def test_dossier_absent(tmp_path):
    assert memoire.souvenirs(tmp_path / "absent") == []
