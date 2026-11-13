import json
import os

from app import travaux


def job(dossier, ident, contenu, quand):
    (dossier / ident).mkdir(parents=True)
    f = dossier / ident / "state.json"
    f.write_text(contenu if isinstance(contenu, str) else json.dumps(contenu), encoding="utf-8")
    os.utime(f, (quand, quand))


def test_travaux_tries_en_cours_puis_bloques_puis_termines(tmp_path):
    job(tmp_path, "aaa", {"state": "done", "detail": "Fini"}, 300)
    job(tmp_path, "bbb", {"state": "blocked", "detail": "Question", "needs": "Préviens-moi quand le zip est là"}, 100)
    job(tmp_path, "ccc", {"state": "working", "detail": "Mode clair"}, 50)
    job(tmp_path, "ddd", "{pas du json", 400)
    l = travaux.lister(tmp_path)
    assert [t["id"] for t in l] == ["ccc", "bbb", "aaa"], "un fichier illisible est ignoré, les travaux actifs d'abord"
    assert l[1]["libelle"] == "Attend ta réponse" and l[1]["besoin"].startswith("Préviens-moi")


def test_dossier_absent(tmp_path):
    assert travaux.lister(tmp_path / "absent") == []
