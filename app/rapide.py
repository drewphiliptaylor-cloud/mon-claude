"""Action rapide depuis l'accueil : Claude propose, l'utilisateur valide, puis seulement on crée.

1. `proposer()` : Claude (modèle léger, sans outils, sans CLAUDE.md) transforme la phrase
   de l'utilisateur en proposition structurée. Rien n'est créé.
2. L'utilisateur corrige les champs et clique « Ajouter ».
3. Tâche → écrite localement (app/taches.py). Rendez-vous → `creer_evenement()` : Claude
   avec SEULEMENT l'outil de création du connecteur Google Agenda.

La sortie de Claude est une donnée non fiable : elle est validée champ par champ.
"""
import re
import shutil
from datetime import date, timedelta
from typing import Optional

from claude_agent_sdk import (ClaudeAgentOptions, PermissionResultAllow, PermissionResultDeny, ResultMessage, SystemMessage,
                              query)

MODELE_RAPIDE = "haiku"
OUTIL_AGENDA = "mcp__claude_ai_Google_Calendar__create_event"
# Sans ça, hors d'une session Claude Code (service), les connecteurs Google sont encore « pending » au 1er tour.
ATTENDRE_CONNECTEURS = {"MCP_CONNECTION_NONBLOCKING": "false"}
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

SCHEMA = {
    "type": "object",
    "properties": {
        "genre": {"type": "string", "enum": ["agenda", "tache", "conversation"]},
        "titre": {"type": "string"},
        "dates_possibles": {"type": "array", "items": {"type": "string"}},
        "heure": {"type": "string"},
        "duree_minutes": {"type": "integer"},
        "section": {"type": "string", "enum": ["Pro", "Perso"]},
        "priorite": {"type": "string", "enum": ["haute", "moyenne", "basse"]},
        "question": {"type": "string"},
    },
    "required": ["genre", "titre", "dates_possibles", "heure", "duree_minutes", "section", "priorite", "question"],
    "additionalProperties": False,
}


def consignes(aujourd_hui: date) -> str:
    j = JOURS[aujourd_hui.weekday()]
    return f"""Tu transformes une demande courte de l'utilisateur en proposition structurée. Tu ne fais rien d'autre.
Aujourd'hui : {j} {aujourd_hui.isoformat()} (fuseau Europe/Paris).
- genre « agenda » : un rendez-vous, une réunion, un événement daté. « tache » : quelque chose à faire, à noter dans sa to-do.
  « conversation » : tout le reste (question ouverte, travail long, plusieurs étapes).
- titre : court, en français, majuscule initiale, sans la date ni l'heure (« rdv coiffeur » → « Coiffeur »).
- dates_possibles : dates au format AAAA-MM-JJ. Une seule si c'est clair. Si c'est ambigu, toutes les possibilités :
  par exemple « ce {j} » dit un {j} = aujourd'hui OU dans 7 jours. Vide si aucune date n'est dite.
- heure : HH:MM seulement si l'utilisateur la donne, sinon chaîne vide. N'invente jamais d'heure.
- duree_minutes : celle dite par l'utilisateur, sinon 60 pour un rendez-vous, 0 pour une tâche.
- section : « Pro » si c'est lié au travail (atelier, projets, réunions, devis, clients, fournisseurs), sinon « Perso ».
- priorite : « haute » si l'utilisateur dit urgent/important, sinon « moyenne ».
- question : en français, ce qui manque ou est ambigu pour créer l'élément (ex. « À quelle heure ? »). Vide si rien ne manque."""


_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HEURE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def valider(brut: dict, aujourd_hui: date) -> dict:
    """Nettoie la proposition de Claude ; tout champ douteux est vidé plutôt que deviné."""
    if not isinstance(brut, dict):
        return {"genre": "conversation", "titre": "", "dates_possibles": [], "heure": "", "duree_minutes": 0,
                "section": "Perso", "priorite": "moyenne", "question": ""}
    genre = brut.get("genre") if brut.get("genre") in ("agenda", "tache", "conversation") else "conversation"
    titre = " ".join(str(brut.get("titre", "")).split())[:120]
    dates = []
    for d in brut.get("dates_possibles") or []:
        if isinstance(d, str) and _DATE.match(d):
            try:
                dd = date.fromisoformat(d)
            except ValueError:
                continue
            if aujourd_hui - timedelta(days=1) <= dd <= aujourd_hui + timedelta(days=400) and d not in dates:
                dates.append(d)
    heure = str(brut.get("heure", ""))
    heure = heure if _HEURE.match(heure) else ""
    try:
        duree = int(brut.get("duree_minutes") or 0)
    except (TypeError, ValueError):
        duree = 0
    duree = max(0, min(duree, 24 * 60))
    if genre == "agenda" and duree == 0:
        duree = 60
    section = brut.get("section") if brut.get("section") in ("Pro", "Perso") else "Perso"
    priorite = brut.get("priorite") if brut.get("priorite") in ("haute", "moyenne", "basse") else "moyenne"
    question = " ".join(str(brut.get("question", "")).split())[:200]
    return {"genre": genre, "titre": titre, "dates_possibles": dates[:3], "heure": heure, "duree_minutes": duree,
            "section": section, "priorite": priorite, "question": question}


async def _refuser_tout(nom, entree, ctx):
    return PermissionResultDeny(message="Aucun outil pendant une proposition.")


async def proposer(texte: str, aujourd_hui: date, cwd: str, precision: str = "", precedente: Optional[dict] = None) -> dict:
    demande = texte if not precision else (
        f"Demande initiale : {texte}\nProposition actuelle : {precedente}\nPrécision de l'utilisateur : {precision}\n"
        "Mets à jour la proposition en tenant compte de la précision.")
    opts = ClaudeAgentOptions(model=MODELE_RAPIDE, tools=[], system_prompt=consignes(aujourd_hui), cwd=cwd,
                              cli_path=shutil.which("claude"), setting_sources=[], strict_mcp_config=True,
                              output_format={"type": "json_schema", "schema": SCHEMA}, max_turns=3,
                              can_use_tool=_refuser_tout)
    sortie = None
    async for m in query(prompt=demande, options=opts):
        if isinstance(m, ResultMessage):
            sortie = m.structured_output
    return valider(sortie, aujourd_hui)


def consigne_creation(p: dict) -> str:
    debut = f"{p['date']}T{p['heure']}:00"
    return (f"Crée exactement UN événement dans l'agenda principal (primary) de l'utilisateur avec l'outil create_event, puis "
            f"réponds seulement « OK » ou l'erreur. Titre : {p['titre']!r}. Début : {debut}, fuseau Europe/Paris. "
            f"Durée : {p['duree_minutes']} minutes. Aucune invitation, aucun autre champ.")


async def creer_evenement(p: dict, cwd: str, essai_a_blanc: bool = False) -> dict:
    """À n'appeler qu'après le clic « Ajouter » de l'utilisateur, et si l'écriture agenda a été validée.

    essai_a_blanc=True : Claude prépare l'appel mais il est refusé → rien n'est écrit (pour les tests).
    """
    autorises, demandes = [], []

    async def seulement_agenda(nom, entree, ctx):
        demandes.append({"outil": nom, "entree": entree})
        if nom == OUTIL_AGENDA and not autorises and not essai_a_blanc:
            autorises.append(nom)
            return PermissionResultAllow()
        return PermissionResultDeny(message="Essai à blanc : rien n'est créé." if essai_a_blanc
                                    else "Seule la création d'un événement est permise ici.")

    # tools=[] retirerait aussi le connecteur : on ne garde que l'outil de création (vérifié par test réel à blanc)
    opts = ClaudeAgentOptions(model=MODELE_RAPIDE, tools=[OUTIL_AGENDA], allowed_tools=[], cwd=cwd, cli_path=shutil.which("claude"),
                              setting_sources=["user"], max_turns=4, can_use_tool=seulement_agenda, env=ATTENDRE_CONNECTEURS)
    resultat, diagnostic = None, {}
    async for m in query(prompt=consigne_creation(p), options=opts):
        if isinstance(m, SystemMessage) and m.subtype == "init":
            outils = m.data.get("tools") or []
            diagnostic = {"outil_present": OUTIL_AGENDA in outils,
                          "connecteur": next((s.get("status") for s in m.data.get("mcp_servers") or []
                                              if "Calendar" in str(s.get("name"))), "absent")}
        if isinstance(m, ResultMessage):
            resultat = m
    ok = bool(resultat and not resultat.is_error and autorises)
    sortie = {"ok": ok, "message": ((resultat.result if resultat else None) or "Pas de réponse de Claude.")[:300],
              "diagnostic": diagnostic}
    if essai_a_blanc:
        sortie["demandes"] = demandes
    return sortie
