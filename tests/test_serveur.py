import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.serveur import creer_app

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def client(tmp_path):
    cfg = Config(port=8765, donnees=tmp_path / "data", taches=tmp_path / "taches.md", todo_ice=tmp_path / "todo.md",
                 vault=tmp_path / "vault", claude_md=tmp_path / "CLAUDE.md", dossier_travail=tmp_path)
    return TestClient(creer_app(cfg), base_url="http://127.0.0.1:8765")


def test_page_d_accueil_servie(client):
    assert client.get("/").status_code == 200


def test_autre_site_refuse(client):
    r = client.get("/api/sante", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403, "une page d'un autre site ne doit pas pouvoir appeler le serveur"


def test_nom_d_hote_piege_refuse(tmp_path):
    cfg = Config(port=8765, donnees=tmp_path / "d")
    r = TestClient(creer_app(cfg), base_url="http://evil.example:8765").get("/api/sante")
    assert r.status_code == 403


def test_disposition_valide_enregistree_et_invalide_refusee(client):
    assert client.put("/api/reglages/disposition", json={"valeur": [["agenda", "L"], ["quota", "S"]]}).status_code == 200
    assert client.get("/api/reglages").json()["disposition"] == [["agenda", "L"], ["quota", "S"]]
    assert client.put("/api/reglages/disposition", json={"valeur": [["virus", "L"]]}).status_code == 400


def test_teinte_avec_couleur_invalide_refusee(client):
    bonne = [{"id": "t1", "nom": "Forêt", "a": "#3fb37f", "b": "#f2a7c3"}]
    assert client.put("/api/reglages/teintes", json={"valeur": bonne}).status_code == 200
    mauvaise = [{"id": "t1", "nom": "x", "a": "red;}</style>", "b": "#ffffff"}]
    assert client.put("/api/reglages/teintes", json={"valeur": mauvaise}).status_code == 400


def test_mode_clair_enregistre_et_mode_inconnu_refuse(client):
    assert client.get("/api/reglages").json()["mode"] == "auto", "par défaut le dashboard suit le Mac"
    assert client.put("/api/reglages/mode", json={"valeur": "clair"}).status_code == 200
    assert client.get("/api/reglages").json()["mode"] == "clair"
    assert client.put("/api/reglages/mode", json={"valeur": "rose"}).status_code == 400


def test_dictee_refuse_un_faux_enregistrement(client):
    r = client.post("/api/dictee", content=b"<script>", headers={"Content-Type": "audio/wav"})
    assert r.status_code == 400 and "WAV" in r.json()["detail"]


def test_reglage_inconnu_refuse(client):
    assert client.put("/api/reglages/ical_url", json={"valeur": "https://x"}).status_code == 404, \
        "le lien iCal ne s'écrit que par la route dédiée qui le vérifie"


def test_taches_aller_retour(client):
    t = client.post("/api/taches", json={"texte": "Rappeler le menuisier", "section": "Perso"}).json()
    assert client.patch(f"/api/taches/{t['id']}").json()["fait"] is True
    assert client.patch("/api/taches/inconnue").status_code == 409


def test_image_acceptee_et_faux_fichier_refuse(client):
    r = client.post("/api/images", files={"fichier": ("a.png", PNG, "image/png")})
    assert r.status_code == 200
    assert client.get(r.json()["url"]).status_code == 200
    faux = client.post("/api/images", files={"fichier": ("a.png", b"<script>", "image/png")})
    assert faux.status_code == 400, "un fichier qui n'est pas une image doit être refusé"


def test_chemin_d_image_piege_refuse(client):
    assert client.get("/api/images/..%2F..%2Fetc%2Fpasswd").status_code == 404


def test_action_rapide_tache_ecrit_dans_le_fichier(client, tmp_path):
    r = client.post("/api/rapide/valider", json={"genre": "tache", "titre": "Rappeler le menuisier", "section": "Perso"})
    assert r.status_code == 200
    assert "- [ ] Rappeler le menuisier" in (tmp_path / "taches.md").read_text(encoding="utf-8")


def test_ajout_agenda_inerte_tant_que_non_valide(client):
    r = client.post("/api/rapide/valider", json={"genre": "agenda", "titre": "Coiffeur", "date": "2026-11-19", "heure": "10:30"})
    assert r.status_code == 409, "aucune écriture dans l'agenda avant validation par l'utilisateur"


def test_agenda_non_configure(client):
    assert client.get("/api/agenda").json() == {"configure": False, "evenements": []}


def test_lien_ical_de_partage_refuse(client):
    r = client.put("/api/agenda/lien", json={"url": "https://calendar.google.com/calendar/u/0?cid=abc"})
    assert r.status_code == 400 and "adresse secrète" in r.json()["detail"]


def test_websocket_projet_inconnu_refuse(client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/conversation?projet=../../etc", headers={"Origin": "http://127.0.0.1:8765"}) as ws:
            ws.receive_json()


def test_websocket_d_un_autre_site_refuse(client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/conversation", headers={"Origin": "https://evil.example"}) as ws:
            ws.receive_json()


def test_quota_sans_terminal_passe_par_usage(client, monkeypatch):
    from app import quota
    appels = []

    async def faux_usage(cwd):
        appels.append(cwd)
        return "Current session: 12% used\nCurrent week (all models): 34% used"
    monkeypatch.setattr(quota, "interroger", faux_usage)
    pc = client.get("/api/quota").json()["pourcentages"]
    assert pc["cinq_heures"] == {"pourcentage": 12} and pc["sept_jours"] == {"pourcentage": 34}
    client.get("/api/quota")
    assert len(appels) == 1, "le résultat doit être gardé quelques minutes, pas redemandé à chaque affichage"
    assert appels[0].endswith("interne"), "l'appel interne ne doit pas apparaître dans l'historique"


def test_quota_usage_en_panne_ne_casse_rien(client, monkeypatch):
    from app import quota

    async def en_panne(cwd):
        raise RuntimeError("claude introuvable")
    monkeypatch.setattr(quota, "interroger", en_panne)
    r = client.get("/api/quota")
    assert r.status_code == 200 and r.json()["pourcentages"] is None


def test_prenom_enregistre_et_valide(client):
    assert client.get("/api/reglages").json()["prenom"] == ""
    assert client.put("/api/reglages/prenom", json={"valeur": "  Alex "}).status_code == 200
    assert client.get("/api/reglages").json()["prenom"] == "Alex"
    for mauvais in ["x" * 31, "A\nB", 12, None]:
        assert client.put("/api/reglages/prenom", json={"valeur": mauvais}).status_code == 400, mauvais


def test_reglage_de_conversation_valide(client):
    with client.websocket_connect("ws://127.0.0.1:8765/ws/conversation", headers={"Origin": "http://127.0.0.1:8765"}) as ws:
        assert ws.receive_json() == {"type": "reprise", "occupe": False, "modele": "default", "mode": "default"}
        ws.send_json({"type": "regler", "mode": "acceptEdits", "modele": "opus"})
        assert ws.receive_json() == {"type": "reglages_conv", "modele": "opus", "mode": "acceptEdits"}
        ws.send_json({"type": "regler", "modele": "../../etc"})
        assert ws.receive_json()["type"] == "erreur"
        ws.send_json({"type": "regler", "mode": "bypassPermissions"})
        assert ws.receive_json() == {"type": "erreur", "message": "Mode inconnu."}
