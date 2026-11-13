// Conversation : bulles, étapes réelles, orbe d'état, images, autorisations — en direct par WebSocket.
import { api, el, ic, toast, markdown, heure } from "./outils.js";
import { etatApp } from "./etat.js";
import { brancherMenuCommandes } from "./commandes.js";
import { boutonMicro } from "./dictee.js";
import { lireBrouillon, garderBrouillon, effacerBrouillon } from "./brouillons.js";
import { prevenir } from "./notifications.js";

const ETATS = { pret: "Prêt", reflechit: "Réfléchit…", lit: "Lit…", commande: "Lance une commande…", ecrit: "Écrit…", attend: "Attend ton accord", connexion: "Connexion…", coupe: "Déconnecté" };

function blocEtapes(ouvert) {
  const titre = el("span", {}, "En cours");
  const etapes = el("div", { class: "etapes" });
  const bouton = el("button", { type: "button", "aria-expanded": String(ouvert) }, titre, ic("chev", "ic chev"));
  const p = el("div", { class: "pensee", "data-ouvert": String(ouvert) }, bouton, etapes);
  bouton.addEventListener("click", () => { const o = p.dataset.ouvert !== "true"; p.dataset.ouvert = String(o); bouton.setAttribute("aria-expanded", String(o)); });
  return { p, titre, etapes, ouvrir(o) { p.dataset.ouvert = String(o); bouton.setAttribute("aria-expanded", String(o)); } };
}

function bulleMoi(texte, images, nbImagesPassees) {
  const b = el("div", { class: "moi" });
  if (images?.length) b.append(el("div", { class: "images" }, images.map(i => el("button", { type: "button", "aria-label": "Agrandir " + i.nom, onclick: () => agrandir(i.url, i.nom) }, el("img", { src: i.url, alt: i.nom })))));
  if (nbImagesPassees) b.append(el("div", { class: "images" }, el("span", { class: "compte" }, `📎 ${nbImagesPassees} image${nbImagesPassees > 1 ? "s" : ""}`)));
  if (texte) b.append(el("div", { class: "bulle-moi" }, texte));
  return b;
}

function agrandir(url, alt) {
  const d = document.getElementById("visionneuse"), img = document.getElementById("vis-img");
  img.src = url; img.alt = alt || "";
  d.showModal();
  d.onclick = () => d.close();
}

function boutonCopier(texte) {
  return el("button", { class: "copier", type: "button", "aria-label": "Copier la réponse", onclick: async e => {
    try { await navigator.clipboard.writeText(texte); e.target.textContent = "Copié ✓"; }
    catch { toast("Copie impossible."); }
    setTimeout(() => { e.target.textContent = "Copier"; }, 1500);
  } }, "Copier");
}

function tourPasse(item) {
  const corps = el("div", { class: "corps" }, el("div", { class: "nom" }, "Claude", item.texte ? boutonCopier(item.texte) : null));
  if (item.etapes.length) {
    const b = blocEtapes(false);
    b.titre.textContent = `${item.etapes.length} étape${item.etapes.length > 1 ? "s" : ""}`;
    item.etapes.forEach(e => b.etapes.append(el("div", { class: "etape " + e.type }, e.texte)));
    corps.append(b.p);
  }
  if (item.texte) { const r = el("div", { class: "reponse" }); r.innerHTML = markdown(item.texte); corps.append(r); }
  return el("div", { class: "claude" }, el("span", { class: "orbe" }, el("i")), corps);
}

export async function pageConversation(vue, sessionId, projet = null) {
  const titre = el("h1", {}, sessionId ? "Conversation" : "Nouvelle conversation");
  const orbeHaut = el("span", { class: "orbe petite" }, el("i")), etatTxt = el("span", {}, ETATS.connexion);
  const filIn = el("div", { class: "fil-in" }), fil = el("main", { class: "fil", "aria-live": "polite" }, filIn);
  const texte = el("textarea", { id: "texte", rows: "1", placeholder: "Écris à Claude… (tu peux aussi glisser ou coller une image)" });
  const pj = el("div", { class: "pj", "aria-label": "Images jointes" });
  const fichier = el("input", { type: "file", accept: "image/png,image/jpeg,image/gif,image/webp", multiple: true, hidden: true });
  const envoyer = el("button", { class: "rond env plein", type: "submit", "aria-label": "Envoyer" }, ic("envoyer"));
  const form = el("form", { class: "composer" }, pj, el("div", { class: "ligne-saisie" },
    el("label", { class: "rond", title: "Joindre des images" }, ic("trombone"), el("span", { class: "sr" }, "Joindre des images"), fichier),
    el("label", { class: "sr", for: "texte" }, "Ton message"), texte,
    boutonMicro(texte), envoyer));
  const conteneur = el("div", { class: "conv" },
    el("header", {}, titre, el("span", { class: "puce", title: "Dossier de travail de Claude" }, "…"), el("div", { class: "etat-conv", "aria-live": "polite" }, orbeHaut, etatTxt)),
    fil, el("div", { class: "bas-conv" }, form, el("p", { class: "aide-conv" }, "Entrée pour envoyer · Maj+Entrée pour aller à la ligne · « / » pour les commandes")));
  vue.replaceChildren(conteneur);
  const puce = conteneur.querySelector(".puce");
  const enBas = () => { fil.scrollTop = fil.scrollHeight; };

  // ---------- historique ----------
  if (sessionId) {
    try {
      const c = await api(`/api/conversations/${sessionId}`);
      titre.textContent = c.titre || "Conversation";
      puce.textContent = (c.cwd || "").replace(/^\/Users\/[^/]+/, "~") || "~";
      c.messages.forEach(m => filIn.append(m.role === "moi" ? bulleMoi(m.texte, null, m.images) : tourPasse(m)));
      enBas();
    } catch (e) { filIn.append(el("div", { class: "erreur-conv" }, e.message)); }
  } else puce.textContent = "~";

  // ---------- état ----------
  let occupe = false, tour = null, jointes = [];  // jointes : {id, url, nom}
  const etat = e => {
    orbeHaut.className = "orbe petite " + (e === "pret" || e === "connexion" || e === "coupe" ? "" : e);
    etatTxt.textContent = ETATS[e] || e;
    if (tour) { tour.orbe.className = "orbe " + (e === "pret" ? "" : e); if (e !== "pret") tour.sous.textContent = (ETATS[e] || "").toLowerCase(); }
  };
  const majEnvoyer = () => {
    envoyer.replaceChildren(ic(occupe ? "stop" : "envoyer"));
    envoyer.setAttribute("aria-label", occupe ? "Interrompre" : "Envoyer");
    envoyer.disabled = !occupe && !texte.value.trim() && !jointes.length;
  };

  // ---------- WebSocket ----------
  let ws = null, dejaEcrit = false;
  function connecter() {
    const params = new URLSearchParams();
    if (sessionId) params.set("session", sessionId); else if (projet) params.set("projet", projet);
    const ici = new WebSocket(`ws://${location.host}/ws/conversation${params.size ? "?" + params : ""}`);
    ws = ici; etat("connexion");
    ici.addEventListener("open", () => { if (ws === ici) etat("pret"); });
    ici.addEventListener("close", () => {
      if (ws !== ici || !conteneur.isConnected) return;  // fermeture voulue (changement de dossier, page quittée)
      etat("coupe"); occupe = false; tour = null; majEnvoyer();
      filIn.append(el("div", { class: "erreur-conv" }, "La connexion avec le serveur est coupée. ", el("button", { class: "bouton", type: "button", onclick: () => location.reload() }, "Reconnecter")));
    });
    ici.addEventListener("message", m => { if (ws !== ici) return; let ev; try { ev = JSON.parse(m.data); } catch { return; } recevoir(ev); });
  }
  etatApp.fermerConversation = () => { const w = ws; ws = null; try { w?.close(); } catch { /* déjà fermée */ } };

  // Nouvelle conversation : choix du dossier où Claude travaille (avant le premier message)
  if (!sessionId) {
    try {
      const { projets } = await api("/api/projets");
      const choix = el("select", { class: "puce", "aria-label": "Dossier de travail de Claude", style: "border:0;font:inherit;font-size:var(--t11)" },
        el("option", { value: "" }, "Dossier personnel (~)"),
        projets.filter(p => p.dossier).map(p => el("option", { value: p.nom, selected: p.nom === projet }, `Projet ${p.nom.replace(/_/g, " ")}`)));
      choix.addEventListener("change", () => {
        if (dejaEcrit) return;
        projet = choix.value || null;
        const ancien = ws; ws = null; ancien?.close(); connecter();
      });
      puce.replaceWith(choix);
    } catch { /* sans projets : dossier personnel */ }
  }
  connecter();

  function nouveauTour() {
    const orbe = el("span", { class: "orbe reflechit" }, el("i")), sous = el("small", {}, "réfléchit…");
    const b = blocEtapes(true);
    const reponse = el("div", { class: "reponse curseur" });
    const nom = el("div", { class: "nom" }, "Claude ", sous);
    const corps = el("div", { class: "corps" }, nom, b.p, reponse);
    filIn.append(el("div", { class: "claude" }, orbe, corps));
    return { orbe, sous, nom, b, corps, reponse, brut: "", nb: 0, debut: Date.now(), rendu: 0 };
  }
  function rendreReponse() {
    if (!tour || tour.rendu) return;
    tour.rendu = requestAnimationFrame(() => { if (!tour) return; tour.reponse.innerHTML = markdown(tour.brut); tour.rendu = 0; enBas(); });
  }
  function ajouterEtape(type, txt) {
    tour.b.etapes.append(el("div", { class: "etape " + type }, txt)); tour.nb++;
    tour.b.titre.textContent = `En cours · ${tour.nb} étape${tour.nb > 1 ? "s" : ""}`;
  }
  function recevoir(ev) {
    if (ev.type === "session" && ev.id && ev.id !== sessionId) {  // nouvelle conversation, ou copie d'une conversation occupée ailleurs
      sessionId = ev.id; etatApp.conversationActive = ev.id;
      history.replaceState(null, "", `#/conversation/${ev.id}`);
      return;
    }
    if (!tour && ["etat", "etape", "texte", "accord"].includes(ev.type) && occupe) tour = nouveauTour();
    if (!tour && ["etape", "texte", "accord"].includes(ev.type)) return;  // événement hors tour : ignoré
    switch (ev.type) {
      case "etat": etat(ev.etat); break;
      case "etape":
        if (tour.brut.trim()) { ajouterEtape("pense", tour.brut.trim()); tour.brut = ""; tour.reponse.replaceChildren(); }
        ajouterEtape("action", ev.texte); enBas(); break;
      case "texte": tour.brut += ev.delta; rendreReponse(); break;
      case "accord": {
        const oui = el("button", { class: "bouton prim", type: "button" }, "Autoriser"), non = el("button", { class: "bouton", type: "button" }, "Refuser");
        const carte = el("div", { class: "accord", "data-id": ev.id }, el("b", {}, "Claude demande ton accord"), el("div", {}, ev.texte),
          ev.detail ? el("pre", {}, el("code", {}, ev.detail)) : null, el("div", { class: "btns" }, oui, non));
        const repondre = ok => { ws?.send(JSON.stringify({ type: "accord", id: ev.id, ok })); oui.disabled = non.disabled = true; };
        oui.addEventListener("click", () => repondre(true)); non.addEventListener("click", () => repondre(false));
        tour.corps.insertBefore(carte, tour.reponse); enBas(); oui.focus();
        prevenir("Claude attend ton accord", `${titre.textContent} · ${ev.texte}`, location.hash); break;
      }
      case "accord_fini": {
        const carte = filIn.querySelector(`.accord[data-id="${CSS.escape(ev.id)}"]`);
        if (carte) { carte.classList.add("fait"); carte.querySelector("b").textContent = ev.ok ? "✓ Autorisé par toi" : "✕ Refusé"; }
        break;
      }
      case "fin":
        if (tour) {
          cancelAnimationFrame(tour.rendu); tour.rendu = 0;
          tour.reponse.innerHTML = markdown(tour.brut); tour.reponse.classList.remove("curseur");
          const s = Math.max(1, Math.round((Date.now() - tour.debut) / 1000));
          if (tour.nb) { tour.b.titre.textContent = `A travaillé ${s} s · ${tour.nb} étape${tour.nb > 1 ? "s" : ""}`; tour.b.ouvrir(false); }
          else tour.b.p.remove();
          tour.sous.textContent = heure(new Date());
          if (tour.brut.trim()) tour.nom.append(boutonCopier(tour.brut));
          if (ev.erreur) tour.corps.append(el("div", { class: "erreur-conv" }, "Claude s'est arrêté sur une erreur."));
          prevenir(ev.erreur ? "Claude s'est arrêté sur une erreur" : "Claude a répondu", `${titre.textContent} · ${tour.brut}`, location.hash);
        }
        tour = null; occupe = false; etat("pret"); majEnvoyer(); enBas(); break;
      case "info":
        filIn.insertBefore(el("div", { class: "info-conv", role: "status" }, ev.message), filIn.lastElementChild); enBas(); break;
      case "erreur":
        filIn.append(el("div", { class: "erreur-conv", role: "alert" }, ev.message));
        if (tour) tour.reponse.classList.remove("curseur");
        tour = null; occupe = false; majEnvoyer(); enBas(); break;
    }
  }

  // ---------- saisie & images ----------
  const ajuster = () => { texte.style.height = "auto"; texte.style.height = Math.min(texte.scrollHeight, 200) + "px"; majEnvoyer(); };
  async function joindre(fichiers) {
    for (const f of fichiers) {
      if (!f.type.startsWith("image/")) { toast(`${f.name} n'est pas une image.`); continue; }
      const fd = new FormData(); fd.append("fichier", f);
      try { const r = await api("/api/images", { methode: "POST", brut: fd }); jointes.push({ id: r.id, url: r.url, nom: f.name }); }
      catch (e) { toast(`${f.name} : ${e.message}`); }
    }
    dessinerPJ(); majEnvoyer();
  }
  const zoneBrouillon = () => sessionId ? `conv:${sessionId}` : (projet ? `nouvelle:${projet}` : "nouvelle");
  const sauver = () => garderBrouillon(zoneBrouillon(), texte.value, jointes);
  function dessinerPJ() {
    pj.replaceChildren(...jointes.map((j, i) => el("div", { class: "vignette" }, el("img", { src: j.url, alt: j.nom }),
      el("button", { type: "button", "aria-label": "Retirer " + j.nom, onclick: () => { jointes.splice(i, 1); dessinerPJ(); majEnvoyer(); } }, "✕"))));
    sauver();
  }
  fichier.addEventListener("change", () => { joindre([...fichier.files]); fichier.value = ""; });
  texte.addEventListener("paste", e => { const f = [...(e.clipboardData?.files || [])]; if (f.length) { e.preventDefault(); joindre(f); } });
  ["dragenter", "dragover"].forEach(t => form.addEventListener(t, e => { e.preventDefault(); form.classList.add("survol"); }));
  ["dragleave", "drop"].forEach(t => form.addEventListener(t, e => { e.preventDefault(); form.classList.remove("survol"); }));
  form.addEventListener("drop", e => joindre([...(e.dataTransfer?.files || [])]));
  texte.addEventListener("input", () => { ajuster(); sauver(); });
  texte.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); } });

  form.addEventListener("submit", e => {
    e.preventDefault();
    if (!ws || ws.readyState !== WebSocket.OPEN) { toast("Pas encore connecté au serveur, réessaie dans un instant."); return; }
    if (occupe) { ws.send(JSON.stringify({ type: "interrompre" })); return; }
    const msg = texte.value.trim();
    if (!msg && !jointes.length) return;
    dejaEcrit = true; conteneur.querySelector("select.puce")?.setAttribute("disabled", "");
    effacerBrouillon(zoneBrouillon());
    filIn.append(bulleMoi(msg, jointes));
    ws.send(JSON.stringify({ type: "message", texte: msg, images: jointes.map(j => j.id) }));
    if (titre.textContent === "Nouvelle conversation" && msg) titre.textContent = msg.slice(0, 60);
    jointes = []; dessinerPJ(); texte.value = ""; occupe = true; tour = nouveauTour(); ajuster(); enBas();
  });

  if (etatApp.brouillon) { texte.value = etatApp.brouillon; etatApp.brouillon = ""; sauver(); }
  else {
    const b = lireBrouillon(zoneBrouillon());
    if (b.texte || b.images.length) { texte.value = b.texte; jointes = b.images; dessinerPJ(); }
  }
  brancherMenuCommandes(texte, form);
  ajuster(); texte.focus();
}
