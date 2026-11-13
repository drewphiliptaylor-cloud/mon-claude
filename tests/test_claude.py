import asyncio

import pytest
from claude_agent_sdk import (AssistantMessage, PermissionResultAllow, PermissionResultDeny, RateLimitEvent,
                              ResultMessage, StreamEvent, SystemMessage, TextBlock, ToolUseBlock)
from claude_agent_sdk.types import RateLimitInfo

from app.claude import Conversation, Traducteur, message_utilisateur


def flux(evenement, parent=None):
    return StreamEvent(uuid="u", session_id="s", event=evenement, parent_tool_use_id=parent)


def test_init_donne_la_session_et_l_etat():
    evs = Traducteur().traduire(SystemMessage(subtype="init", data={"session_id": "abc", "slash_commands": ["to-do"],
                                                                     "plugins": [{"name": "sp", "path": "/p"}]}))
    assert evs == [{"type": "session", "id": "abc"}, {"type": "etat", "etat": "reflechit"},
                   {"type": "commandes", "noms": ["to-do"], "terminal": [], "plugins": [{"name": "sp", "path": "/p"}]}]


def test_texte_au_fil_de_l_eau():
    t = Traducteur()
    assert t.traduire(flux({"type": "content_block_start", "content_block": {"type": "text"}})) == [{"type": "etat", "etat": "ecrit"}]
    assert t.traduire(flux({"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Bon"}})) == [{"type": "texte", "delta": "Bon"}]


def test_texte_d_un_sous_agent_ignore():
    t = Traducteur()
    assert t.traduire(flux({"type": "content_block_delta", "delta": {"type": "text_delta", "text": "x"}}, parent="t1")) == []


def test_outil_donne_etat_puis_etape():
    t = Traducteur()
    assert t.traduire(flux({"type": "content_block_start", "content_block": {"type": "tool_use", "name": "Bash"}})) == [{"type": "etat", "etat": "commande"}]
    m = AssistantMessage(content=[TextBlock(text="Je lance."), ToolUseBlock(id="1", name="Bash", input={"command": "ls"})], model="m")
    assert t.traduire(m) == [{"type": "etape", "genre": "action", "texte": "Commande : ls"}], "seuls les outils deviennent des étapes"


def test_quota_et_fin():
    t = Traducteur()
    q = RateLimitEvent(rate_limit_info=RateLimitInfo(status="allowed", resets_at=1794533400, rate_limit_type="five_hour"), uuid="u", session_id="s")
    assert t.traduire(q) == [{"type": "quota", "statut": "allowed", "reinit": 1794533400, "genre": "five_hour", "utilisation": None}]
    r = ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1, session_id="s", total_cost_usd=0.1)
    assert t.traduire(r)[0] == {"type": "fin", "cout": 0.1, "erreur": False, "session": "s"}


def test_reponse_sans_flux_affichee_quand_meme():
    t = Traducteur()
    r = ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=True, num_turns=0, session_id="s",
                      result="Shell command permission check failed")
    assert t.traduire(r)[0] == {"type": "texte", "delta": "Shell command permission check failed"}, \
        "un skill refusé ne doit pas laisser une réponse vide"


def test_reponse_deja_affichee_pas_repetee():
    t = Traducteur()
    t.traduire(flux({"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Bonjour"}}))
    r = ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1, session_id="s", result="Bonjour")
    assert [e["type"] for e in t.traduire(r)] == ["fin", "etat"]


def test_descriptions_officielles_des_commandes():
    m = SystemMessage(subtype="commands_changed", data={"commands": [{"name": "to-do", "description": "Noter"}, {"bad": 1}]})
    assert Traducteur().traduire(m) == [{"type": "commandes_desc", "commandes": [{"nom": "to-do", "description": "Noter"}]}]


def test_message_avec_image():
    m = message_utilisateur("Regarde", [("image/png", "QUJD")])
    assert m["message"]["content"] == [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "QUJD"}},
        {"type": "text", "text": "Regarde"}]


async def test_autorisation_accordee_par_l_utilisateur():
    envoyes = []

    async def envoyer(ev):
        envoyes.append(ev)
    c = Conversation(envoyer, cwd="/tmp")
    tache = asyncio.create_task(c._autorisation("Bash", {"command": "brew upgrade codex"}, None))
    await asyncio.sleep(0.01)
    demande = [e for e in envoyes if e["type"] == "accord"][0]
    assert demande["detail"] == "brew upgrade codex"
    assert c.repondre_accord(demande["id"], True)
    assert isinstance(await tache, PermissionResultAllow)


async def test_page_fermee_refuse_la_demande_en_attente():
    async def envoyer(ev):
        pass
    c = Conversation(envoyer, cwd="/tmp")
    tache = asyncio.create_task(c._autorisation("Write", {"file_path": "/x"}, None))
    await asyncio.sleep(0.01)
    await c.fermer()
    assert isinstance(await tache, PermissionResultDeny), "une demande sans réponse doit être refusée"


async def test_reponse_a_une_demande_inconnue_ignoree():
    async def envoyer(ev):
        pass
    assert Conversation(envoyer, cwd="/tmp").repondre_accord("nexistepas", True) is False
