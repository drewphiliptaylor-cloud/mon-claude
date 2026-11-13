from app import projets

CLAUDE_MD = """# Mémoire
## Mes projets actifs (lire le CLAUDE.md local AVANT de travailler)
Texte d'intro.

| Projet | Emplacement | État (au 2026-11-12) |
|---|---|---|
| Config_Claude_Code | `~/.claude/` + kit | en cours — reste : Fusion 360, NAS, sandbox |
| Dashboard_Claude | `~/dashboard-claude/` | en pause — cahier des charges à écrire |
| Boucle_Voix | `~/boucle-voix/` | validé — rien en attente |

## Autre section
| pas | un | projet |
"""

NOTE = """---
type: session
date: 2026-11-12
heure: "21:39"
projets: [Dashboard_Claude]
statut: en_cours
---

# Session 2026-11-12 21h39 — Cadrage UX/UI du Dashboard Claude
"""


def test_lit_le_tableau_des_projets(tmp_path):
    f = tmp_path / "CLAUDE.md"
    f.write_text(CLAUDE_MD, encoding="utf-8")
    p = projets.projets(f)
    assert [x["nom"] for x in p] == ["Config_Claude_Code", "Dashboard_Claude", "Boucle_Voix"], "seul le tableau des projets doit être lu"
    assert p[0]["statut"] == "en cours" and p[0]["detail"] == "Fusion 360, NAS, sandbox"
    assert p[1]["emplacement"] == "~/dashboard-claude/"


def test_dossier_du_projet_premier_chemin_existant(tmp_path):
    (tmp_path / "proj").mkdir()
    assert projets.dossier(f"`{tmp_path}/inexistant/` + kit `{tmp_path}/proj/`") == (tmp_path / "proj").resolve()
    assert projets.dossier("quelque part") is None


def test_claude_md_absent_ou_sans_tableau(tmp_path):
    assert projets.projets(tmp_path / "absent.md") == []
    f = tmp_path / "vide.md"
    f.write_text("# Rien\n", encoding="utf-8")
    assert projets.projets(f) == []


def test_notes_de_session_et_rattachement(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(CLAUDE_MD, encoding="utf-8")
    d = tmp_path / "vault" / "06_Claude" / "sessions"
    d.mkdir(parents=True)
    (d / "2026-11-12_21h39_dashboard.md").write_text(NOTE, encoding="utf-8")
    (d / "README.md").write_text("# lisez-moi", encoding="utf-8")
    notes = projets.notes_recentes(tmp_path / "vault")
    assert notes == [{"fichier": "2026-11-12_21h39_dashboard.md", "titre": "Cadrage UX/UI du Dashboard Claude",
                      "date": "2026-11-12", "heure": "21:39", "statut": "en_cours", "projets": ["Dashboard_Claude"]}]
    p = projets.projets_avec_notes(tmp_path / "CLAUDE.md", tmp_path / "vault")
    assert p[1]["derniere_note"]["titre"] == "Cadrage UX/UI du Dashboard Claude"
    assert p[0]["derniere_note"] is None
