"""Pilote Chrome sans interface (protocole DevTools) pour exercer le vrai parcours dans la vraie page.

Usage : python tests/navigateur.py <scénario> <dossier de sortie>
Scénarios : accueil, conversation, rapide, taches, teintes, reduit
Nécessite le serveur lancé sur 127.0.0.1:8765. Le scénario « conversation » consomme du quota Claude.
"""
import asyncio
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BASE = os.environ.get("DASHBOARD_TEST_URL", "http://127.0.0.1:8765/")


class Page:
    def __init__(self, ws):
        self.ws, self.n, self.erreurs = ws, 0, []

    async def cmd(self, methode, **params):
        self.n += 1
        mon_id = self.n
        await self.ws.send(json.dumps({"id": mon_id, "method": methode, "params": params}))
        while True:
            m = json.loads(await self.ws.recv())
            if m.get("method") == "Runtime.exceptionThrown":
                self.erreurs.append(m["params"]["exceptionDetails"].get("exception", {}).get("description", "?")[:300])
            if m.get("method") == "Runtime.consoleAPICalled" and m["params"]["type"] == "error":
                self.erreurs.append(" ".join(str(a.get("value", a.get("description", ""))) for a in m["params"]["args"])[:300])
            if m.get("id") == mon_id:
                return m.get("result", {})

    async def js(self, code):
        r = await self.cmd("Runtime.evaluate", expression=code, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description", str(r)))
        return r.get("result", {}).get("value")

    async def attendre(self, condition, delai=30):
        fin = time.time() + delai
        while time.time() < fin:
            if await self.js(f"!!({condition})"):  # un élément DOM revient comme {} : on force un booléen
                return True
            await asyncio.sleep(0.3)
        raise TimeoutError(condition)

    async def clic_reel(self, selecteur):
        """Vrai clic souris (geste de l'utilisateur), nécessaire pour l'audio et le micro."""
        r = await self.js(f"(() => {{ const b = document.querySelector('{selecteur}').getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; }})()")
        for genre in ("mousePressed", "mouseReleased"):
            await self.cmd("Input.dispatchMouseEvent", type=genre, x=r[0], y=r[1], button="left", clickCount=1)

    async def capture(self, chemin):
        r = await self.cmd("Page.captureScreenshot", format="png")
        with open(chemin, "wb") as f:
            f.write(base64.b64decode(r["data"]))

    async def aller(self, url):
        await self.cmd("Page.navigate", url=url)
        await asyncio.sleep(1.5)


async def ouvrir(largeur=1400, hauteur=1000):
    port = 9333
    profil = tempfile.mkdtemp()
    micro = []
    if os.environ.get("DICTEE_WAV"):  # faux micro qui « parle » le contenu de ce fichier
        micro = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                 f"--use-file-for-fake-audio-capture={os.environ['DICTEE_WAV']}"]
    try:  # un Chrome de test resté ouvert servirait d'anciens fichiers : on refuse plutôt que de tester du périmé
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=1)
        raise RuntimeError(f"Un Chrome de test tourne déjà sur le port {port} : pkill -f remote-debugging-port={port}")
    except OSError:
        pass
    p = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--remote-debugging-port={port}", f"--user-data-dir={profil}",
                          f"--window-size={largeur},{hauteur}", *micro, "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cible = None
    for _ in range(100):
        try:
            cibles = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
            cible = next(c for c in cibles if c["type"] == "page")
            break
        except Exception:
            time.sleep(0.2)
    if cible is None:
        p.terminate()  # sinon ce Chrome resterait ouvert et fausserait les essais suivants
        raise RuntimeError("Chrome de test n'a pas démarré à temps.")
    ws = await websockets.connect(cible["webSocketDebuggerUrl"], max_size=50_000_000)
    page = Page(ws)
    await page.cmd("Runtime.enable")
    await page.cmd("Page.enable")
    return p, page


async def principal(scenario, sortie):
    os.makedirs(sortie, exist_ok=True)
    chrome, page = await ouvrir()
    rapport = {}
    try:
        await page.aller(BASE + "#/accueil")
        await page.attendre("document.querySelectorAll('.w').length > 0 && !document.body.innerText.includes('Chargement…')")
        if scenario == "accueil":
            rapport["widgets"] = await page.js("[...document.querySelectorAll('.w')].map(w => w.getAttribute('aria-label'))")
            q = "document.querySelector('.w[aria-label^=\"Quota\"]')"
            await page.attendre(f"!{q} || !{q}.innerText.includes('Lecture du quota')", 45)
            rapport["quota"] = await page.js(f"{q}?.innerText")
            await page.capture(f"{sortie}/accueil.png")
        elif scenario == "reduit":
            await page.js("document.getElementById('replier').click()")
            await asyncio.sleep(0.5)
            rapport["reduit"] = await page.js("document.getElementById('menu').classList.contains('reduit')")
            await page.capture(f"{sortie}/menu-reduit.png")
            await page.js("document.getElementById('replier').click()")  # remettre comme avant
        elif scenario == "rapide":
            await page.js("{ const c=document.getElementById('demande'); c.value='ajoute à ma to-do : tester le dashboard demain'; c.dispatchEvent(new Event('input')); c.form.requestSubmit() }")
            await page.attendre("document.querySelector('.prop .champs')", 60)
            rapport["titre_propose"] = await page.js("document.querySelector('.prop .champs input').value")
            await page.capture(f"{sortie}/rapide-proposition.png")
            await page.js("[...document.querySelectorAll('.prop .bouton.prim')][0].click()")
            await page.attendre("document.querySelector('.prop.ok')", 20)
            rapport["confirmation"] = await page.js("document.querySelector('.prop.ok').innerText")
            await page.capture(f"{sortie}/rapide-ok.png")
            await page.js("[...document.querySelectorAll('.prop.ok .bouton')].find(b => b.textContent.includes('Annuler')).click()")
            await asyncio.sleep(1)
            rapport["apres_annulation"] = await page.js("document.querySelector('.w[aria-label^=\"À faire\"]').innerText")
            # demande ambiguë d'agenda : proposition seulement, l'ajout reste inerte
            await page.js("{ const c=document.getElementById('demande'); c.value='ajoute dans mon agenda le rdv coiffeur de ce vendredi'; c.dispatchEvent(new Event('input')); c.form.requestSubmit() }")
            await page.attendre("document.querySelector('.prop .champs')", 60)
            rapport["agenda_question"] = await page.js("document.querySelector('.prop .question').textContent")
            rapport["agenda_bouton_inerte"] = await page.js("document.querySelector('.prop .bouton.prim').disabled")
            await page.capture(f"{sortie}/rapide-agenda.png")
        elif scenario == "teintes":
            await page.js("document.querySelector('.teinte-btn').click()")
            await page.js("[...document.querySelectorAll('.choisir')].find(b => b.textContent.includes('Menthe')).click()")
            await asyncio.sleep(0.5)
            rapport["couleur"] = await page.js("getComputedStyle(document.documentElement).getPropertyValue('--ambre').trim()")
            await page.capture(f"{sortie}/teinte-menthe.png")
            await page.js("[...document.querySelectorAll('.choisir')].find(b => b.textContent.includes('Ambre')).click()")
        elif scenario == "travaux_galerie":
            await page.aller(BASE + "#/travaux")
            await page.attendre("!document.body.innerText.includes('Chargement…')", 30)
            rapport["travaux"] = await page.js("[...document.querySelectorAll('.liste-conv > *')].map(x => x.innerText.split('\\n').slice(0, 2).join(' | ')).slice(0, 4)")
            rapport["travail_actif_non_cliquable"] = await page.js("[...document.querySelectorAll('.liste-conv > a .etat-working')].length === 0")
            await page.capture(f"{sortie}/travaux.png")
            await page.aller(BASE + "#/galerie")
            await page.attendre("!document.body.innerText.includes('Chargement…')", 15)
            rapport["images"] = await page.js("document.querySelectorAll('.galerie-images img').length")
            rapport["maquettes"] = await page.js("document.querySelectorAll('.liste-conv a').length")
            rapport["maquette_servie"] = await page.js("fetch(document.querySelector('.liste-conv a').href).then(r => r.status)")
            await page.capture(f"{sortie}/galerie.png")
        elif scenario == "outils":
            await page.aller(BASE + "#/outils")
            await page.attendre("document.querySelector('.outil')", 15)
            rapport["tuiles"] = await page.js("document.querySelectorAll('.outil').length")
            await page.capture(f"{sortie}/outils.png")
            await page.js("[...document.querySelectorAll('.outil')].find(t => t.querySelector('b').textContent === '/to-do').querySelector('button').click()")
            await asyncio.sleep(1.5)
            rapport["conversation_preparee"] = await page.js("location.hash + ' | ' + document.getElementById('texte').value")
            await page.js("Object.keys(localStorage).filter(k => k.startsWith('brouillon:')).forEach(k => localStorage.removeItem(k))")
            await page.aller(BASE + "#/memoire")
            await page.attendre("document.querySelector('.souvenir')", 15)
            rapport["souvenirs"] = await page.js("document.querySelectorAll('.souvenir').length")
            await page.js("document.querySelector('.souvenir-tete').click()")
            await asyncio.sleep(0.3)
            rapport["souvenir_deplie"] = await page.js("!document.querySelector('.souvenir .reponse').hidden")
            await page.capture(f"{sortie}/memoire.png")
            await page.aller(BASE + "#/antiseche")
            await asyncio.sleep(0.8)
            rapport["gestes"] = await page.js("document.querySelectorAll('.gestes dt').length")
            await page.capture(f"{sortie}/antiseche.png")
        elif scenario == "brouillons":
            ecrire = "{ const z=document.querySelector('%s'); z.value='%s'; z.dispatchEvent(new Event('input')); }"
            await page.js(ecrire % ("#demande", "rdv dentiste mardi"))
            await page.aller(BASE + "#/agenda")
            await page.aller(BASE + "#/accueil")
            await asyncio.sleep(1)
            rapport["accueil_apres_agenda"] = await page.js("document.getElementById('demande').value")
            await page.aller(BASE + "#/nouvelle")
            await asyncio.sleep(1.5)
            await page.js(ecrire % ("#texte", "Peux-tu préparer la liste du matériel pour"))
            await page.aller(BASE + "#/agenda")
            await page.aller(BASE + "#/nouvelle")
            await asyncio.sleep(1.5)
            rapport["nouvelle_apres_agenda"] = await page.js("document.getElementById('texte').value")
            await page.cmd("Page.reload")
            await asyncio.sleep(2.5)
            rapport["nouvelle_apres_rechargement"] = await page.js("document.getElementById('texte').value")
            # une conversation existante a son propre brouillon
            ident = await page.js("fetch('/api/conversations').then(r => r.json()).then(d => d.conversations[0].id)")
            await page.aller(BASE + f"#/conversation/{ident}")
            await asyncio.sleep(2)
            rapport["conversation_vide_au_depart"] = await page.js("document.getElementById('texte').value === ''")
            await page.js(ecrire % ("#texte", "suite de la discussion"))
            await page.aller(BASE + "#/accueil")
            await page.aller(BASE + f"#/conversation/{ident}")
            await asyncio.sleep(2)
            rapport["conversation_apres_retour"] = await page.js("document.getElementById('texte').value")
            await page.capture(f"{sortie}/brouillon-conversation.png")
            # nettoyage : vider les brouillons de test
            await page.js("Object.keys(localStorage).filter(k => k.startsWith('brouillon:')).forEach(k => localStorage.removeItem(k))")
        elif scenario == "micro_brut":
            rapport["amplitude"] = await page.js("""(async () => {
              const f = await navigator.mediaDevices.getUserMedia({audio: true});
              const ctx = new AudioContext(); const s = ctx.createMediaStreamSource(f); const p = ctx.createScriptProcessor(4096, 1, 1);
              let max = 0, n = 0; p.onaudioprocess = e => { n++; for (const x of e.inputBuffer.getChannelData(0)) max = Math.max(max, Math.abs(x)); };
              s.connect(p); p.connect(ctx.destination);
              await new Promise(r => setTimeout(r, 3000));
              return {max, blocs: n, etat: ctx.state, freq: ctx.sampleRate};
            })()""")
        elif scenario == "dictee":
            # Chrome sans interface ne lit pas le faux micro : on remplace le micro par la lecture du fichier voix.
            voix = base64.b64encode(open(os.environ["DICTEE_WAV"], "rb").read()).decode()
            faux_micro = """(() => { const f0 = window.fetch; window.fetch = async (...a) => { const r = await f0(...a); if (String(a[0]).includes("/api/dictee")) window.__dictee = r.status + " " + await r.clone().text(); return r; };
              navigator.mediaDevices.getUserMedia = async () => {
              const ctx = new AudioContext(); const octets = Uint8Array.from(atob('%s'), c => c.charCodeAt(0));
              await ctx.resume(); const son = await ctx.decodeAudioData(octets.buffer); const src = ctx.createBufferSource(); src.buffer = son;
              const dest = ctx.createMediaStreamDestination(); src.connect(dest); src.start(); return dest.stream; }; })()""" % voix
            for ou, zone in (("accueil", "#demande"), ("nouvelle", "#texte")):
                await page.aller(BASE + f"#/{ou}")
                await asyncio.sleep(1.5)
                await page.js(faux_micro)
                await page.clic_reel(".rond.micro")
                await page.attendre("document.querySelector('.rond.micro.enregistre')", 10)
                await page.capture(f"{sortie}/dictee-{ou}-enregistre.png")
                await asyncio.sleep(5)
                await page.clic_reel(".rond.micro")
                await page.attendre(f"document.querySelector('{zone}').value.length > 3", 120)
                rapport[f"texte_{ou}"] = await page.js(f"document.querySelector('{zone}').value")
                rapport[f"rien_envoye_{ou}"] = await page.js("!document.querySelector('.bulle-moi') && !document.querySelector('.prop')")
                await page.capture(f"{sortie}/dictee-{ou}-texte.png")
        elif scenario == "commandes":
            await page.aller(BASE + "#/nouvelle")
            await page.attendre("document.querySelector('.etat-conv').innerText.includes('Prêt')", 15)
            await page.js("{ const t=document.getElementById('texte'); t.focus(); t.value='/stat'; t.dispatchEvent(new Event('input')); }")
            await page.attendre("!document.getElementById('menu-commandes').hidden", 10)
            rapport["options"] = await page.js("[...document.querySelectorAll('.option-commande b')].map(b => b.textContent)")
            await page.capture(f"{sortie}/commandes-menu.png")
            # Entrée choisit la commande au lieu d'envoyer le message
            await page.js("document.getElementById('texte').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}))")
            await asyncio.sleep(0.3)
            rapport["texte_apres_entree"] = await page.js("document.getElementById('texte').value")
            rapport["menu_ferme"] = await page.js("document.getElementById('menu-commandes').hidden")
            rapport["rien_envoye"] = await page.js("!document.querySelector('.bulle-moi')")
            await page.js("{ const t=document.getElementById('texte'); t.value='/'; t.dispatchEvent(new Event('input')); }")
            await asyncio.sleep(0.3)
            await page.js("document.getElementById('texte').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
            rapport["echap_ferme"] = await page.js("document.getElementById('menu-commandes').hidden")
            if os.environ.get("AVEC_CLAUDE"):
                await page.js("{ const t=document.getElementById('texte'); t.value='/statusline-aide'; t.dispatchEvent(new Event('input')); document.getElementById('menu-commandes').hidden = true; t.form.requestSubmit(); }")
                await page.attendre("document.querySelector('.etat-conv').innerText.includes('Prêt') && document.querySelector('.reponse') && !document.querySelector('.curseur')", 180)
                rapport["reponse_skill"] = (await page.js("[...document.querySelectorAll('.reponse')].pop().innerText"))[:300]
                await page.capture(f"{sortie}/commandes-skill.png")
        elif scenario == "modes":
            for m in ("clair", "sombre"):
                await page.js(f"document.querySelector('.choix-mode button[data-mode={m}]').click()")
                await asyncio.sleep(0.6)
                rapport[m] = await page.js("getComputedStyle(document.body).backgroundColor + ' / texte ' + getComputedStyle(document.body).color")
                await page.capture(f"{sortie}/mode-{m}.png")
            await page.js("document.querySelector('.choix-mode button[data-mode=clair]').click()")
            await asyncio.sleep(0.5)
            await page.aller(BASE + "#/nouvelle")
            await asyncio.sleep(1)
            rapport["persiste_apres_rechargement"] = await page.js("document.documentElement.dataset.mode")
            await page.capture(f"{sortie}/mode-clair-conversation.png")
            await page.aller(BASE + "#/reglages")
            await asyncio.sleep(1)
            await page.capture(f"{sortie}/mode-clair-reglages.png")
        elif scenario == "pages":
            for nom in ("agenda", "projets", "historique", "reglages"):
                await page.aller(BASE + f"#/{nom}")
                await page.attendre("!document.body.innerText.includes('Chargement…')", 20)
                await page.capture(f"{sortie}/page-{nom}.png")
            await page.aller(BASE + "#/nouvelle/Dashboard_Claude")
            await page.attendre("document.querySelector('.etat-conv').innerText.includes('Prêt')", 15)
            rapport["dossier_choisi"] = await page.js("document.querySelector('select.choix-dossier').selectedOptions[0].textContent")
            await page.capture(f"{sortie}/nouvelle-projet.png")
        elif scenario == "taches":
            await page.aller(BASE + "#/taches")
            await page.attendre("document.querySelector('.ligne-form')")
            await page.capture(f"{sortie}/taches.png")
        elif scenario == "accord":
            # Demande qui exige une autorisation : le script clique TOUJOURS « Refuser ».
            await page.aller(BASE + "#/nouvelle")
            await page.attendre("document.querySelector('.etat-conv').innerText.includes('Prêt')", 15)
            await page.js("{ const t=document.getElementById('texte'); t.value='Crée le fichier essai-dashboard.txt dans le dossier courant avec la commande Bash `touch essai-dashboard.txt`.'; t.dispatchEvent(new Event('input')); t.form.requestSubmit() }")
            await page.attendre("document.querySelector('.accord .btns')", 120)
            rapport["carte"] = await page.js("document.querySelector('.accord').innerText")
            rapport["etat_pendant"] = await page.js("document.querySelector('.etat-conv').innerText")
            await page.capture(f"{sortie}/accord-demande.png")
            await page.js("[...document.querySelectorAll('.accord .bouton')].find(b => b.textContent === 'Refuser').click()")
            await page.attendre("document.querySelector('.etat-conv').innerText.includes('Prêt') && !document.querySelector('.curseur')", 180)
            rapport["carte_apres"] = await page.js("document.querySelector('.accord b').textContent")
            rapport["fichier_cree"] = os.path.exists(os.path.expanduser("~/essai-dashboard.txt"))
            await page.capture(f"{sortie}/accord-refuse.png")
        elif scenario == "conversation":
            await page.aller(BASE + "#/nouvelle")
            await page.attendre("document.querySelector('.etat-conv').innerText.includes('Prêt')", 15)
            # Question sans outil : aucune autorisation n'est donnée à la place de l'utilisateur.
            await page.js("const t=document.getElementById('texte'); t.value=\"Sans utiliser d'outil, explique en deux phrases ce qu'est un widget sur macOS, avec un mot en gras et une petite liste de deux exemples.\"; t.dispatchEvent(new Event('input')); t.form.requestSubmit()")
            await asyncio.sleep(3)
            await page.capture(f"{sortie}/conversation-pendant.png")
            await page.attendre("document.querySelector('.accord .btns') || document.querySelector('.reponse:not(.curseur)')", 120)
            rapport["demande_accord"] = await page.js("!!document.querySelector('.accord')")
            if rapport["demande_accord"]:
                await page.js("[...document.querySelectorAll('.accord .bouton')].find(b => b.textContent === 'Refuser').click()")
            await page.attendre("document.querySelector('.etat-conv').innerText.includes('Prêt') && !document.querySelector('.curseur')", 180)
            rapport["reponse"] = await page.js("[...document.querySelectorAll('.reponse')].pop().innerText")
            rapport["etapes"] = await page.js("[...document.querySelectorAll('.pensee button span')].pop()?.textContent")
            rapport["url"] = await page.js("location.hash")
            await page.capture(f"{sortie}/conversation-fin.png")
        elif scenario == "notifications":
            # Autorisation accordée comme si l'utilisateur avait cliqué « Autoriser » ; Notification espionnée pour compter les envois.
            await page.cmd("Browser.grantPermissions", permissions=["notifications"], origin=BASE.rstrip("/"))
            await page.aller(BASE + "#/reglages")
            await page.attendre("document.getElementById('notif')", 10)
            await page.js("document.getElementById('notif').click()")
            await page.attendre("document.getElementById('notif').checked", 5)
            rapport["etat_reglage"] = await page.js("document.getElementById('notif').closest('section').innerText")
            await page.capture(f"{sortie}/reglage-notifications.png")
            await page.js("window.__notifs = []; window.Notification = class extends Notification { constructor(t, o) { super(t, o); window.__notifs.push([t, o.body, o.icon]); } }")
            await page.js("[...document.querySelectorAll('section.reglage .bouton')].find(b => b.textContent === 'Essayer').click()")
            rapport["essai"] = await page.js("window.__notifs.slice()")
            await page.aller(BASE + "#/nouvelle")  # même document : l'espion reste en place
            await page.attendre("document.querySelector('.etat-conv').innerText.includes('Prêt')", 15)
            await page.js("document.hasFocus = () => false")  # L'utilisateur regarde une autre fenêtre
            await page.js("{ const t=document.getElementById('texte'); t.value='Réponds seulement : bonjour.'; t.dispatchEvent(new Event('input')); t.form.requestSubmit() }")
            await page.attendre("document.querySelector('.etat-conv').innerText.includes('Prêt') && document.querySelector('.reponse:not(.curseur)')", 120)
            await asyncio.sleep(0.5)
            rapport["apres_reponse"] = await page.js("window.__notifs.slice(1)")
            rapport["icone_servie"] = await page.js("fetch('/web/icone-192.png').then(r => r.ok && r.headers.get('content-type'))")
        elif scenario == "quitter":
            # Bugs signalés le 13/11 : le message envoyé revenait dans la saisie ; quitter avant la réponse la perdait.
            await page.aller(BASE + "#/nouvelle")
            await page.attendre("document.querySelector('.etat-conv').innerText.includes('Prêt')", 15)
            demande = "Sans outil, écris les nombres de un à quatre-vingts en toutes lettres, un par ligne, rien d'autre."
            await page.js(f"const t=document.getElementById('texte'); t.value={json.dumps(demande)}; t.dispatchEvent(new Event('input')); t.form.requestSubmit()")
            await page.attendre("location.hash.startsWith('#/conversation/')", 60)
            lien = await page.js("location.hash")
            await asyncio.sleep(2)
            await page.aller(BASE + "#/historique")   # on quitte avant la fin de la réponse
            await asyncio.sleep(3)
            await page.aller(BASE + lien)             # on revient
            await page.attendre("document.getElementById('texte')", 15)
            rapport["saisie_au_retour"] = await page.js("document.getElementById('texte').value")
            await asyncio.sleep(1)
            rapport["etat_au_retour"] = await page.js("document.querySelector('.etat-conv').innerText")
            await page.attendre("document.querySelector('.etat-conv').innerText.includes('Prêt') && document.querySelector('.reponse, .claude') && !document.querySelector('.curseur')", 180)
            await asyncio.sleep(1)
            rapport["bulles_du_message"] = await page.js(f"[...document.querySelectorAll('.bulle-moi')].filter(b => b.textContent === {json.dumps(demande)}).length")
            rapport["fin_de_reponse"] = await page.js("[...document.querySelectorAll('.claude .corps, .claude')].pop().innerText.slice(-60)")
            await page.capture(f"{sortie}/quitter-retour.png")
            await page.aller(BASE + "#/nouvelle")
            await page.attendre("document.getElementById('texte')", 15)
            rapport["saisie_nouvelle_conversation"] = await page.js("document.getElementById('texte').value")
        elif scenario == "modele":
            await page.aller(BASE + "#/nouvelle")
            await page.attendre("document.querySelector('.etat-conv').innerText.includes('Prêt')", 15)
            await page.attendre("[...document.querySelector('select[aria-label=\"Modèle de Claude\"]').options].some(o => o.value === 'haiku')", 60)
            rapport["modeles"] = await page.js("[...document.querySelector('select[aria-label=\"Modèle de Claude\"]').options].map(o => o.textContent)")
            await page.js("const s=document.querySelector('select[aria-label=\"Modèle de Claude\"]'); s.value='haiku'; s.dispatchEvent(new Event('change'))")
            # Maj+Tab dans la zone de saisie : Demander → Modifs auto → Plan
            for _ in range(2):
                await page.js("document.getElementById('texte').dispatchEvent(new KeyboardEvent('keydown', {key: 'Tab', shiftKey: true, bubbles: true}))")
                await asyncio.sleep(0.3)
            rapport["mode"] = await page.js("document.querySelector('select[aria-label=\"Mode de Claude\"]').value")
            await page.js("{ const t=document.getElementById('texte'); t.value='Crée le fichier essai-plan.txt dans le dossier courant avec le mot bonjour.'; t.dispatchEvent(new Event('input')); t.form.requestSubmit() }")
            await page.attendre("document.querySelector('.accord .btns') || (document.querySelector('.etat-conv').innerText.includes('Prêt') && !document.querySelector('.curseur'))", 180)
            rapport["carte"] = await page.js("document.querySelector('.accord')?.innerText.slice(0, 200) || null")
            await page.capture(f"{sortie}/mode-plan.png")
            if rapport["carte"]:
                await page.js("[...document.querySelectorAll('.accord .bouton')].find(b => b.textContent === 'Refuser').click()")
            await page.attendre("document.querySelector('.etat-conv').innerText.includes('Prêt') && !document.querySelector('.curseur')", 180)
            rapport["fichier_cree"] = os.path.exists(os.path.expanduser("~/essai-plan.txt"))
            await page.js("{ const t=document.getElementById('texte'); t.value='En une phrase : quel modèle Claude es-tu exactement ?'; t.dispatchEvent(new Event('input')); t.form.requestSubmit() }")
            await page.attendre("document.querySelector('.etat-conv').innerText.includes('Prêt') && !document.querySelector('.curseur')", 180)
            rapport["reponse_modele"] = await page.js("[...document.querySelectorAll('.reponse')].pop().innerText")
            rapport["modele_affiche"] = await page.js("[...document.querySelectorAll('.claude .nom small')].pop().textContent")
            await page.capture(f"{sortie}/modele.png")
        rapport["erreurs_js"] = page.erreurs
    except Exception as e:
        rapport["echec"] = repr(e)
        rapport["erreurs_js"] = page.erreurs
        rapport["texte_page"] = (await page.js("document.querySelector('main').innerText"))[:300]
        rapport["dictee_reponse"] = await page.js("window.__dictee || null")
        await page.capture(f"{sortie}/echec-{scenario}.png")
    finally:
        await page.ws.close()
        chrome.terminate()
    print(json.dumps(rapport, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    asyncio.run(principal(sys.argv[1], sys.argv[2]))
