from app import commandes


def skill(dossier, nom, description):
    (dossier / nom).mkdir(parents=True)
    (dossier / nom / "SKILL.md").write_text(f"---\nname: {nom}\ndescription: {description}\n---\n# {nom}\n", encoding="utf-8")


def test_descriptions_des_skills_utilisateur_et_des_plugins(tmp_path):
    skill(tmp_path / "claude" / "skills", "to-do", "Use quand l'utilisateur verse une idée dans sa file — capture, notation")
    skill(tmp_path / "plugin" / "skills", "brainstorming", "You MUST use this before any creative work. More text")
    d = commandes.descriptions(tmp_path / "claude", [{"name": "superpowers", "path": str(tmp_path / "plugin")}])
    assert d["to-do"] == "L'utilisateur verse une idée dans sa file", d
    assert d["superpowers:brainstorming"] == "You MUST use this before any creative work"


def test_liste_filtre_le_terminal_et_trie(tmp_path):
    descr = {"to-do": "Noter une idée", "superpowers:brainstorming": "Avant tout travail créatif", "session-note": "Archiver"}
    noms = ["superpowers:brainstorming", "doctor", "compact", "to-do", "session-note", "config", "inconnue", "x; rm -rf /"]
    l = commandes.liste(noms, ["doctor"], descr)
    assert [c["nom"] for c in l] == ["session-note", "to-do", "superpowers:brainstorming", "compact"], \
        "skills de l'utilisateur d'abord, puis plugins, puis commandes ; terminal, inconnues et noms bizarres exclus"
    assert l[-1]["description"].startswith("Résumer")


def test_sans_conversation_on_propose_les_skills_du_disque():
    l = commandes.liste(None, None, {"to-do": "Noter une idée"})
    assert {"nom": "to-do", "description": "Noter une idée", "genre": "skill"} in l
    assert any(c["nom"] == "compact" for c in l)
