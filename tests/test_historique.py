from types import SimpleNamespace

from app import historique
from app.libelles import libelle, etat


def u(contenu):
    return {"type": "user", "message": {"role": "user", "content": contenu}}


def a(*blocs):
    return {"type": "assistant", "message": {"role": "assistant", "content": list(blocs)}}


def test_un_echange_avec_etapes_et_reponse():
    items = historique.convertir([
        u("Résume le dossier"),
        a({"type": "text", "text": "Je regarde le dossier."}, {"type": "tool_use", "name": "Read", "input": {"file_path": "/x/plans.pdf"}}),
        u([{"type": "tool_result", "content": "…"}]),
        a({"type": "text", "text": "Il contient trois maquettes."}),
    ])
    assert items == [
        {"role": "moi", "texte": "Résume le dossier", "images": 0},
        {"role": "claude", "texte": "Il contient trois maquettes.",
         "etapes": [{"type": "pense", "texte": "Je regarde le dossier."}, {"type": "action", "texte": "Lit plans.pdf"}]},
    ], "les résultats d'outils ne sont pas des messages de l'utilisateur ; le dernier texte est la réponse"


def test_messages_systeme_masques_et_image_comptee():
    items = historique.convertir([
        u("<command-name>/clear</command-name>"),
        u([{"type": "image", "source": {}}, {"type": "text", "text": "Voilà mon inspiration"}]),
    ])
    assert items == [{"role": "moi", "texte": "Voilà mon inspiration", "images": 1}]


def test_conversations_internes_exclues_et_titre():
    sessions = [SimpleNamespace(session_id="1", custom_title=None, summary="Coiffeur", first_prompt=None, last_modified=5, cwd="/data/interne"),
                SimpleNamespace(session_id="2", custom_title="Pictos", summary="x", first_prompt=None, last_modified=4, cwd="/Users/alex")]
    liste = historique.conversations(lambda limit: sessions, exclus=["/data/interne"])
    assert liste == [{"id": "2", "titre": "Pictos", "maj": 4, "cwd": "/Users/alex"}]


def test_libelles_en_francais():
    assert libelle("Bash", {"command": "brew upgrade codex", "description": "Met à jour codex"}) == "Commande : Met à jour codex"
    assert libelle("Grep", {"pattern": "liège"}) == "Cherche « liège »"
    assert libelle("mcp__claude_ai_Google_Calendar__create_event", {}) == "Google Calendar : create event"
    assert etat("Bash") == "commande" and etat("Read") == "lit" and etat("Edit") == "ecrit"
