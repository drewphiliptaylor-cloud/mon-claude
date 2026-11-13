"""Serveur local du dashboard : API + interface + WebSocket de conversation.

Lancer : .venv/bin/python -m app.serveur   (écoute sur 127.0.0.1 seulement)
"""
import asyncio
import base64
import os
import re
import tempfile
import time
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import claude_agent_sdk as sdk
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agenda, commandes, dictee, historique, memoire, projets, quota, rapide, taches, travaux
from .claude import Conversation
from .config import Config
from .securite import TAILLE_MAX_MESSAGE, requete_autorisee, type_image
from .store import Store

WIDGETS = {"agenda", "todo", "reprendre", "projets", "quota", "date"}
TAILLES = {"S", "M", "L", "XL"}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_UUID = re.compile(r"^[0-9a-f-]{36}$")
_IMAGE_ID = re.compile(r"^[0-9a-f]{32}\.(png|jpg|gif|webp)$")
QUOTA_CACHE = 180  # secondes : au-delà, le pourcentage est redemandé à Claude Code


def creer_app(cfg: Optional[Config] = None) -> FastAPI:
    cfg = cfg or Config()
    cfg.preparer()
    store = Store(cfg.base)
    app = FastAPI(title="Dashboard Claude", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.cfg, app.state.store = cfg, store

    # ---------- frontière : seules les pages du dashboard peuvent appeler le serveur ----------
    @app.middleware("http")
    async def garde(request: Request, suite):
        if not requete_autorisee(request.headers.get("host"), request.headers.get("origin"), cfg.port):
            return JSONResponse({"erreur": "Accès refusé."}, status_code=403)
        reponse = await suite(request)
        reponse.headers["X-Content-Type-Options"] = "nosniff"
        reponse.headers["Referrer-Policy"] = "no-referrer"
        reponse.headers["Cache-Control"] = "no-store"
        return reponse

    # ---------- interface ----------
    @app.get("/")
    async def accueil():
        return FileResponse(cfg.web / "index.html")

    app.mount("/web", StaticFiles(directory=str(cfg.web)), name="web")

    @app.get("/api/sante")
    async def sante():
        return {"ok": True}

    # ---------- réglages ----------
    @app.get("/api/reglages")
    async def lire_reglages():
        return {"disposition": store.get("disposition"), "teintes": store.get("teintes", []),
                "teinte_active": store.get("teinte_active", "ambre"), "menu_reduit": store.get("menu_reduit", False),
                "mode": store.get("mode", "auto"), "prenom": store.get("prenom", ""),
                "ical_configure": bool(store.get("ical_url")),
                "agenda_ecriture_validee": store.get("agenda_ecriture_validee", False)}

    @app.put("/api/reglages/{cle}")
    async def ecrire_reglage(cle: str, request: Request):
        valeur = (await request.json()).get("valeur")
        if cle == "disposition":
            if not (isinstance(valeur, list) and len(valeur) <= 20 and all(
                    isinstance(x, list) and len(x) == 2 and x[0] in WIDGETS and x[1] in TAILLES for x in valeur)):
                raise HTTPException(400, "Disposition invalide.")
        elif cle == "teintes":
            if not (isinstance(valeur, list) and len(valeur) <= 30 and all(
                    isinstance(t, dict) and isinstance(t.get("id"), str) and len(t["id"]) <= 40
                    and isinstance(t.get("nom"), str) and 0 < len(t["nom"]) <= 24
                    and _HEX.match(str(t.get("a", ""))) and _HEX.match(str(t.get("b", ""))) for t in valeur)):
                raise HTTPException(400, "Teintes invalides.")
            valeur = [{"id": t["id"], "nom": t["nom"], "a": t["a"], "b": t["b"]} for t in valeur]
        elif cle == "teinte_active":
            if not (isinstance(valeur, str) and len(valeur) <= 40):
                raise HTTPException(400, "Teinte invalide.")
        elif cle == "mode":
            if valeur not in ("auto", "sombre", "clair"):
                raise HTTPException(400, "Mode inconnu.")
        elif cle == "prenom":
            valeur = valeur.strip() if isinstance(valeur, str) else None
            if valeur is None or len(valeur) > 30 or any(not c.isprintable() for c in valeur):
                raise HTTPException(400, "Prénom invalide (30 caractères au plus).")
        elif cle in ("menu_reduit", "agenda_ecriture_validee"):
            if not isinstance(valeur, bool):
                raise HTTPException(400, "Valeur invalide.")
        else:
            raise HTTPException(404, "Réglage inconnu.")
        store.set(cle, valeur)
        return {"ok": True}

    class Ical(BaseModel):
        url: str

    @app.put("/api/agenda/lien")
    async def regler_ical(corps: Ical):
        try:
            url = agenda.verifier_url(corps.url)
            agenda.vider_cache()
            evs = await asyncio.to_thread(agenda.evenements, url)
        except agenda.AgendaErreur as e:
            raise HTTPException(400, str(e))
        store.set("ical_url", url)
        return {"ok": True, "nombre": len(evs)}

    @app.delete("/api/agenda/lien")
    async def oublier_ical():
        store.supprimer("ical_url")
        agenda.vider_cache()
        return {"ok": True}

    @app.get("/api/agenda")
    async def lire_agenda(jours: int = 3):
        url = store.get("ical_url")
        if not url:
            return {"configure": False, "evenements": []}
        jours = max(1, min(jours, 14))
        try:
            return {"configure": True, "evenements": await asyncio.to_thread(agenda.evenements, url, None, jours)}
        except agenda.AgendaErreur as e:
            return {"configure": True, "evenements": [], "erreur": str(e)}

    # ---------- tâches ----------
    class NouvelleTache(BaseModel):
        texte: str
        section: str = "Perso"
        priorite: str = "moyenne"

    @app.get("/api/taches")
    async def lire_taches():
        return taches.lire(cfg.taches, cfg.todo_ice)

    @app.post("/api/taches")
    async def ajouter_tache(t: NouvelleTache):
        try:
            return taches.ajouter(cfg.taches, t.texte, t.section, t.priorite)
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.patch("/api/taches/{id_}")
    async def basculer_tache(id_: str):
        try:
            return taches.basculer(cfg.taches, id_)
        except taches.TacheIntrouvable:
            raise HTTPException(409, "Cette tâche a changé ailleurs. La liste a été rechargée.")

    @app.delete("/api/taches/{id_}")
    async def supprimer_tache(id_: str):
        try:
            taches.supprimer(cfg.taches, id_)
        except taches.TacheIntrouvable:
            raise HTTPException(409, "Cette tâche a changé ailleurs. La liste a été rechargée.")
        return {"ok": True}

    # ---------- projets, historique, quota ----------
    @app.get("/api/projets")
    async def lire_projets():
        return {"projets": projets.projets_avec_notes(cfg.claude_md, cfg.vault)}

    @app.get("/api/conversations")
    async def lister_conversations():
        # conversations internes (action rapide), dossiers temporaires (tests) : pas des conversations de l'utilisateur
        exclus = [str(cfg.donnees), str(Path.home() / ".claude" / "jobs"), str(Path(tempfile.gettempdir()).resolve()),
                  "/private/var/folders", "/var/folders", "/tmp", "/private/tmp"]
        return {"conversations": await asyncio.to_thread(historique.conversations, sdk.list_sessions, exclus)}

    @app.get("/api/conversations/{session_id}")
    async def lire_conversation(session_id: str):
        if not _UUID.match(session_id):
            raise HTTPException(400, "Identifiant invalide.")
        info = await asyncio.to_thread(sdk.get_session_info, session_id)
        if info is None:
            raise HTTPException(404, "Conversation introuvable.")
        msgs = await asyncio.to_thread(historique.messages, sdk.get_session_messages, session_id)
        return {"id": session_id, "titre": info.custom_title or info.summary, "cwd": info.cwd, "messages": msgs}

    def noter_quota(ev: dict) -> None:
        store.set("quota", {**ev, "vu_le": int(datetime.now().timestamp())})

    def noter_commandes(ev: dict) -> None:
        if ev["type"] == "commandes":
            store.set("commandes_init", {k: ev[k] for k in ("noms", "terminal", "plugins")})
        else:  # descriptions officielles de Claude Code
            store.set("commandes_desc", {c["nom"]: str(c.get("description") or "") for c in ev["commandes"]
                                         if isinstance(c.get("nom"), str)})

    @app.get("/api/travaux")
    async def lire_travaux():
        liste = travaux.lister(cfg.travaux)
        # relier chaque travail à sa conversation (l'identifiant du travail est le début de celui de la session)
        sessions = await asyncio.to_thread(sdk.list_sessions, None, 200)
        for t in liste:
            t["session"] = next((s.session_id for s in sessions if s.session_id.startswith(t["id"])), None)
        return {"travaux": liste}

    @app.get("/api/galerie")
    async def lire_galerie():
        images = sorted(cfg.images.glob("*.*"), key=lambda f: f.stat().st_mtime, reverse=True)
        maquettes = sorted(cfg.maquettes.glob("*.html")) if cfg.maquettes.is_dir() else []
        return {"images": [{"url": f"/api/images/{f.name}", "le": int(f.stat().st_mtime)} for f in images[:200] if _IMAGE_ID.match(f.name)],
                "maquettes": [{"nom": f.stem, "url": f"/maquettes/{f.name}"} for f in maquettes]}

    if cfg.maquettes.is_dir():
        app.mount("/maquettes", StaticFiles(directory=str(cfg.maquettes)), name="maquettes")

    @app.get("/api/memoire")
    async def lire_memoire():
        return {"souvenirs": memoire.souvenirs(cfg.memoire)}

    @app.get("/api/dictee")
    async def etat_dictee():
        return dictee.etat()

    @app.post("/api/dictee")
    async def dicter(request: Request):
        try:
            longueur = int(request.headers.get("content-length", "0"))
        except ValueError:
            longueur = 0
        if longueur > dictee.TAILLE_MAX:
            raise HTTPException(413, "Enregistrement trop long (6 minutes maximum).")
        donnees = await request.body()
        try:
            return {"texte": await asyncio.to_thread(dictee.transcrire, donnees)}
        except dictee.DicteeErreur as e:
            raise HTTPException(400, str(e))

    @app.get("/api/commandes")
    async def lister_commandes():
        init = store.get("commandes_init") or {}
        descr = commandes.descriptions(cfg.claude_md.parent, init.get("plugins"))
        descr.update({n: commandes._resume(d) for n, d in (store.get("commandes_desc") or {}).items()})
        return {"commandes": commandes.liste(init.get("noms"), init.get("terminal"), descr)}

    usage = {"valeur": None, "le": 0.0, "verrou": asyncio.Lock()}

    async def pourcentages_usage() -> Optional[dict]:
        """`/usage` de Claude Code, gardé QUOTA_CACHE secondes ; un seul appel à la fois."""
        async with usage["verrou"]:
            if time.time() - usage["le"] >= QUOTA_CACHE:
                try:
                    texte = await asyncio.wait_for(quota.interroger(str(cfg.interne)), 30)
                    usage["valeur"] = quota.analyser_usage(texte) if texte else None
                except Exception as e:  # quota indisponible : le widget affiche l'état seul, rien ne casse
                    print(f"quota /usage indisponible : {e!r}", flush=True)
                    usage["valeur"] = None
                usage["le"] = time.time()
            return usage["valeur"]

    @app.get("/api/quota")
    async def lire_quota():
        # /usage d'abord : valeur à jour du compte. La status line ne sert que de secours, car chaque terminal
        # y écrit le chiffre de SA dernière requête (une session inactive y remet un chiffre ancien).
        pc = await pourcentages_usage() or quota.lire(cfg.donnees / "quota.json")
        return {"quota": store.get("quota"), "pourcentages": pc}

    # ---------- images ----------
    @app.post("/api/images")
    async def recevoir_image(fichier: UploadFile = File(...)):
        donnees = await fichier.read(10 * 1024 * 1024 + 1)
        genre = type_image(donnees)
        if genre is None:
            raise HTTPException(400, "Seules les images PNG, JPEG, GIF ou WebP de 10 Mo maximum sont acceptées.")
        nom = f"{uuid.uuid4().hex}.{genre[1]}"
        (cfg.images / nom).write_bytes(donnees)
        return {"id": nom, "url": f"/api/images/{nom}"}

    @app.get("/api/images/{nom}")
    async def servir_image(nom: str):
        if not _IMAGE_ID.match(nom) or not (cfg.images / nom).is_file():
            raise HTTPException(404, "Image introuvable.")
        return FileResponse(cfg.images / nom)

    # ---------- action rapide ----------
    class Demande(BaseModel):
        texte: str
        precision: str = ""
        precedente: Optional[dict] = None

    @app.post("/api/rapide/proposer")
    async def proposer(d: Demande):
        if not d.texte.strip() or len(d.texte) > 1000 or len(d.precision) > 1000:
            raise HTTPException(400, "Demande vide ou trop longue.")
        try:
            return await rapide.proposer(d.texte, date.today(), str(cfg.interne), d.precision, d.precedente)
        except Exception as e:
            raise HTTPException(502, f"Claude n'a pas pu répondre : {type(e).__name__}.")

    class Validation(BaseModel):
        genre: str
        titre: str
        date: str = ""
        heure: str = ""
        duree_minutes: int = 60
        section: str = "Perso"
        priorite: str = "moyenne"

    @app.post("/api/rapide/valider")
    async def valider(v: Validation):
        if v.genre == "tache":
            try:
                return {"ok": True, "tache": taches.ajouter(cfg.taches, v.titre, v.section, v.priorite)}
            except ValueError as e:
                raise HTTPException(400, str(e))
        if v.genre == "agenda":
            if not store.get("agenda_ecriture_validee", False):
                raise HTTPException(409, "L'ajout à l'agenda n'a pas encore été testé avec toi. Active-le dans les réglages.")
            propre = rapide.valider({"genre": "agenda", "titre": v.titre, "dates_possibles": [v.date], "heure": v.heure,
                                     "duree_minutes": v.duree_minutes}, date.today())
            if not propre["titre"] or not propre["dates_possibles"] or not propre["heure"]:
                raise HTTPException(400, "Il manque le titre, le jour ou l'heure.")
            r = await rapide.creer_evenement({"titre": propre["titre"], "date": propre["dates_possibles"][0],
                                              "heure": propre["heure"], "duree_minutes": propre["duree_minutes"]},
                                             str(cfg.interne))
            if r["ok"]:
                agenda.vider_cache()
            return r
        raise HTTPException(400, "Genre inconnu.")

    @app.post("/api/agenda/essai")
    async def essai_agenda():
        """Essai à blanc : Claude prépare la création d'un rendez-vous, l'appel est refusé, rien n'est écrit."""
        demain = date.fromordinal(date.today().toordinal() + 1).isoformat()
        r = await rapide.creer_evenement({"titre": "Essai dashboard (à blanc)", "date": demain, "heure": "10:00",
                                          "duree_minutes": 30}, str(cfg.interne), essai_a_blanc=True)
        pret = any(d["outil"] == rapide.OUTIL_AGENDA for d in r.get("demandes", []))
        return {"pret": pret, "diagnostic": r.get("diagnostic"), "message": r["message"]}

    # ---------- conversation en direct ----------
    @app.websocket("/ws/conversation")
    async def ws_conversation(ws: WebSocket):
        if not requete_autorisee(ws.headers.get("host"), ws.headers.get("origin"), cfg.port):
            await ws.close(code=4403)
            return
        await ws.accept()
        session_id = ws.query_params.get("session") or None
        if session_id and not _UUID.match(session_id):
            await ws.close(code=4400)
            return
        cwd = str(cfg.dossier_travail)
        nom_projet = ws.query_params.get("projet")
        if nom_projet and not session_id:
            # seuls les dossiers des projets du tableau sont acceptés : jamais un chemin envoyé par la page
            trouve = next((p for p in projets.projets_avec_notes(cfg.claude_md, cfg.vault) if p["nom"] == nom_projet and p["dossier"]), None)
            if trouve is None:
                await ws.close(code=4404)
                return
            cwd = trouve["dossier"]
        if session_id:
            info = await asyncio.to_thread(sdk.get_session_info, session_id)
            if info and info.cwd and os.path.isdir(info.cwd):
                cwd = info.cwd

        async def envoyer(ev: dict):
            try:
                await ws.send_json(ev)
            except Exception:
                pass

        conv = Conversation(envoyer, cwd=cwd, session_id=session_id, surveiller_quota=noter_quota,
                            noter_commandes=noter_commandes)
        taches_en_cours = set()
        try:
            while True:
                msg = await ws.receive_json()
                genre = msg.get("type")
                if genre == "message":
                    texte = str(msg.get("texte", ""))[:TAILLE_MAX_MESSAGE]
                    images = []
                    for nom in (msg.get("images") or [])[:10]:
                        if isinstance(nom, str) and _IMAGE_ID.match(nom) and (cfg.images / nom).is_file():
                            donnees = (cfg.images / nom).read_bytes()
                            images.append((type_image(donnees)[0], base64.b64encode(donnees).decode()))
                    if not texte.strip() and not images:
                        continue
                    t = asyncio.create_task(conv.tour(texte, images))
                    taches_en_cours.add(t)
                    t.add_done_callback(taches_en_cours.discard)
                elif genre == "accord":
                    conv.repondre_accord(str(msg.get("id", "")), bool(msg.get("ok")))
                elif genre == "interrompre":
                    await conv.interrompre()
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            await conv.fermer()
            for t in taches_en_cours:
                t.cancel()

    return app


def main():
    import uvicorn
    cfg = Config()
    uvicorn.run(creer_app(cfg), host="127.0.0.1", port=cfg.port, log_level="warning")


if __name__ == "__main__":
    main()
