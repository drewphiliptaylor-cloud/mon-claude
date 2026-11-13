// Accueil : salutation, action rapide, widgets réorganisables.
import { api, el, ic, toast, libJour, heure, depuis, auj } from "./outils.js";
import { selecteurTeinte, selecteurMode } from "./teintes.js";
import { etatApp, aller } from "./etat.js";
import { boutonMicro } from "./dictee.js";
import { lireBrouillon, garderBrouillon, effacerBrouillon } from "./brouillons.js";

const DEFAUT = [["agenda", "L"], ["todo", "L"], ["reprendre", "M"], ["date", "S"], ["quota", "S"]];
const TOUTES = ["S", "M", "L", "XL"];
let donnees = {};

// ---------- widgets ----------
function entete(icone, titre, droite, lien) {
  const t = lien ? el("a", { href: lien }, titre) : titre;
  return el("h3", {}, ic(icone), t, droite ? el("span", { class: "dr" }, droite) : null);
}

function evenementsParJour(evs) {
  const groupes = new Map();
  for (const e of evs) {
    const d = new Date(e.debut);
    const cle = d.toDateString();
    if (!groupes.has(cle)) groupes.set(cle, { jour: d, evs: [] });
    groupes.get(cle).evs.push(e);
  }
  return [...groupes.values()];
}

function ligneRdv(e, detail) {
  const d = new Date(e.debut), f = new Date(e.fin);
  const passe = !e.journee && f < auj();
  return el("div", { class: "rdv" + (passe ? " passe" : "") },
    el("span", { class: "h" }, e.journee ? "Jour" : heure(d)), el("i"),
    el("div", {}, el("b", {}, e.titre), detail && (e.lieu || !e.journee)
      ? el("small", {}, [e.journee ? "" : dureeTexte(d, f), e.lieu].filter(Boolean).join(" · ")) : null));
}
const dureeTexte = (d, f) => { const m = Math.round((f - d) / 60000); return m >= 60 ? `${Math.floor(m / 60)} h${m % 60 ? " " + String(m % 60).padStart(2, "0") : ""}` : `${m} min`; };

const W = {
  agenda: { nom: "Agenda", tailles: TOUTES, rendu(t) {
    const a = donnees.agenda;
    if (!a) return [entete("agenda", "Agenda"), el("p", { class: "doux" }, "Chargement…")];
    if (!a.configure) return [entete("agenda", "Agenda"), el("p", { class: "doux" }, "À configurer : colle ton lien iCal dans "), el("a", { href: "#/reglages", class: "bouton" }, "Réglages")];
    if (a.erreur) return [entete("agenda", "Agenda"), el("p", { class: "erreur-txt" }, a.erreur)];
    const evs = a.evenements;
    if (t === "S") {
      const prochain = evs.find(e => !e.journee && new Date(e.fin) > auj()) || evs[0];
      if (!prochain) return [entete("agenda", "Agenda", null, "#/agenda"), el("p", { class: "doux" }, "Rien de prévu sur 3 jours.")];
      return [entete("agenda", "Agenda", null, "#/agenda"), el("div", { class: "gros" }, prochain.journee ? "Jour" : heure(new Date(prochain.debut))),
        el("div", { class: "doux", style: "margin-top:6px" }, prochain.titre), el("div", { class: "doux pied" }, libJour(new Date(prochain.debut)))];
    }
    const jours = evenementsParJour(t === "M" ? evs.filter(e => new Date(e.debut).toDateString() === auj().toDateString()) : evs);
    const corps = el("div", { class: "defile" });
    if (!jours.length) corps.append(el("p", { class: "vide" }, t === "M" ? "Rien aujourd'hui." : "Rien de prévu sur 3 jours."));
    for (const g of jours) {
      if (t !== "M") corps.append(el("div", { class: "jour" }, libJour(g.jour)));
      g.evs.forEach(e => corps.append(ligneRdv(e, t !== "M")));
    }
    return [entete("agenda", "Agenda", t === "M" ? "Aujourd'hui" : "3 jours", "#/agenda"), corps];
  } },
  todo: { nom: "À faire", tailles: TOUTES, rendu(t) {
    const d = donnees.taches;
    if (!d) return [entete("afaire", "À faire"), el("p", { class: "doux" }, "Chargement…")];
    const ouvertes = d.taches.filter(x => !x.fait);
    if (t === "S") return [entete("afaire", "À faire", null, "#/taches"), el("div", { class: "gros" }, String(ouvertes.length)),
      el("div", { class: "doux pied" }, `dont ${ouvertes.filter(x => x.priorite === "haute").length} prioritaire(s)`)];
    const liste = el("div", { class: "defile" });
    const n = t === "M" ? 3 : 50;
    if (!ouvertes.length) liste.append(el("p", { class: "vide" }, "Rien à faire. Profite !"));
    ouvertes.slice(0, n).forEach(x => liste.append(ligneTache(x, () => chargerTaches(true))));
    return [entete("afaire", "À faire", String(ouvertes.length), "#/taches"), liste];
  } },
  reprendre: { nom: "Reprendre", tailles: ["M", "L", "XL"], rendu(t) {
    const c = donnees.conversations;
    if (!c) return [entete("historique", "Reprendre"), el("p", { class: "doux" }, "Chargement…")];
    const n = t === "M" ? 2 : 4, col = t === "XL" ? 4 : 2;
    const tuiles = el("div", { class: "tuiles", style: `grid-template-columns:repeat(${col},minmax(0,1fr))` },
      c.slice(0, n).map(x => el("a", { class: "tuile", href: `#/conversation/${x.id}` }, el("b", {}, x.titre), el("small", {}, depuis(x.maj)))));
    return [entete("historique", "Reprendre", null, "#/historique"), c.length ? tuiles : el("p", { class: "vide" }, "Aucune conversation.")];
  } },
  projets: { nom: "Projets", tailles: ["M", "L", "XL"], rendu(t) {
    const p = donnees.projets;
    if (!p) return [entete("projets", "Projets"), el("p", { class: "doux" }, "Chargement…")];
    const n = t === "M" ? 2 : 4, col = t === "XL" ? 4 : 2;
    return [entete("projets", "Projets", null, "#/projets"), el("div", { class: "tuiles", style: `grid-template-columns:repeat(${col},minmax(0,1fr))` },
      p.slice(0, n).map(x => el("a", { class: "tuile", href: "#/projets" }, el("b", {}, x.nom.replace(/_/g, " ")), el("small", {}, x.statut))))];
  } },
  quota: { nom: "Quota", tailles: ["S", "M"], rendu() {
    const d = donnees.quota || {}, pc = d.pourcentages, q = d.quota;
    const jauge = (lib, f) => f ? [el("div", { class: "doux" }, `${lib} · ${f.pourcentage} %` + (f.reinit ? ` · zéro ${quand(f.reinit)}` : "")),
      el("div", { class: "jauge", role: "meter", "aria-valuenow": String(f.pourcentage), "aria-valuemin": "0", "aria-valuemax": "100", "aria-label": `Quota ${lib}` },
        Object.assign(el("i"), { style: `width:${f.pourcentage}%` }))] : [];
    if (pc) return [entete("jauge", "Quota"), ...jauge("5 h", pc.cinq_heures), ...jauge("7 jours", pc.sept_jours),
      el("div", { class: "doux pied", style: "font-size:var(--t11)" }, `mis à jour ${depuis(pc.vu_le * 1000)}`)];
    if (!("quota" in donnees)) return [entete("jauge", "Quota"), el("p", { class: "doux" }, "Lecture du quota…")];
    if (!q) return [entete("jauge", "Quota"), el("p", { class: "doux" }, "Connu après ta prochaine conversation.")];
    const libStatut = { allowed: "Disponible", allowed_warning: "Bientôt atteint", rejected: "Atteint" }[q.statut] || q.statut;
    return [entete("jauge", "Quota"), el("div", { style: "font-size:var(--t17);font-weight:600" }, libStatut),
      q.reinit ? el("div", { class: "doux" }, `Fenêtre de 5 h : remise à zéro ${quand(q.reinit)}`) : null,
      el("div", { class: "doux pied inerte", title: "Claude Code n'a pas pu donner le pourcentage : nouvel essai dans quelques minutes" }, "Pourcentage : indisponible pour l'instant")];
  } },
  date: { nom: "Date", tailles: ["S"], rendu() {
    const d = auj();
    return [el("div", { class: "doux", style: "color:var(--rouge);font-weight:600;text-transform:uppercase" }, d.toLocaleDateString("fr-FR", { weekday: "long" })),
      el("div", { class: "gros", style: "font-size:56px" }, String(d.getDate())), el("div", { class: "doux pied" }, d.toLocaleDateString("fr-FR", { month: "long" }))];
  } },
};

function quand(secondes) {
  const d = new Date(secondes * 1000);
  return d.toDateString() === auj().toDateString() ? `à ${heure(d)}` : `${libJour(d).toLowerCase()} à ${heure(d)}`;
}

export function ligneTache(x, apres) {
  const bascule = async () => {
    try { await api(`/api/taches/${x.id}`, { methode: "PATCH" }); }
    catch (e) { toast(e.message); }
    apres();
  };
  return el("div", { class: "tache" + (x.fait ? " fait" : "") },
    el("button", { class: "case", type: "button", "aria-label": (x.fait ? "Décocher " : "Cocher ") + x.texte, "aria-pressed": String(x.fait), onclick: bascule }, x.fait ? "✓" : ""),
    el("span", { class: "txt" }, x.texte), el("span", { class: "pt " + x.priorite, title: "Priorité " + x.priorite }));
}

// ---------- chargement des données ----------
async function charger(cle, chemin, extraire = r => r) {
  try { donnees[cle] = extraire(await api(chemin)); }
  catch (e) { donnees[cle] = null; if (cle === "agenda") donnees.agenda = { configure: true, evenements: [], erreur: e.message }; }
}
async function chargerTaches(redessiner) { await charger("taches", "/api/taches"); etatApp.majCompteurs(donnees.taches); if (redessiner) dessinerGrille(); }

// ---------- grille ----------
let grille, galerie, disposition, edition = false, source = null;
async function sauverDisposition() {
  try { await api("/api/reglages/disposition", { methode: "PUT", corps: { valeur: disposition } }); }
  catch (e) { toast("Disposition non enregistrée : " + e.message); }
}
function dessinerGrille() {
  if (!grille || !grille.isConnected) return;
  grille.classList.toggle("edition", edition);
  grille.replaceChildren(...disposition.map(([id, t], i) => {
    const w = W[id];
    const d = el("section", { class: `w ${t}`, "aria-label": `${w.nom}, taille ${t}`, draggable: edition ? "true" : null }, ...w.rendu(t));
    d.prepend(el("button", { class: "retirer", type: "button", "aria-label": `Retirer ${w.nom}`, onclick: () => { disposition.splice(i, 1); sauverDisposition(); dessinerGrille(); } }, "−"));
    d.append(el("div", { class: "deplacer" },
      el("button", { type: "button", "aria-label": `Déplacer ${w.nom} avant`, disabled: i === 0, onclick: () => deplacer(i, i - 1) }, "←"),
      el("button", { type: "button", "aria-label": `Déplacer ${w.nom} après`, disabled: i === disposition.length - 1, onclick: () => deplacer(i, i + 1) }, "→")));
    d.append(el("div", { class: "tailles", role: "group", "aria-label": `Taille de ${w.nom}` }, TOUTES.map(s =>
      el("button", { type: "button", "aria-pressed": String(s === t), disabled: !w.tailles.includes(s), onclick: () => { disposition[i][1] = s; sauverDisposition(); dessinerGrille(); } }, s))));
    if (edition) {
      d.addEventListener("dragstart", () => { source = i; d.classList.add("glisse"); });
      d.addEventListener("dragend", () => d.classList.remove("glisse"));
      d.addEventListener("dragover", e => { e.preventDefault(); d.classList.add("cible"); });
      d.addEventListener("dragleave", () => d.classList.remove("cible"));
      d.addEventListener("drop", e => { e.preventDefault(); if (source !== null && source !== i) deplacer(source, i); source = null; });
    }
    return d;
  }));
  galerie.querySelector(".liste").replaceChildren(
    ...Object.keys(W).filter(id => !disposition.some(([x]) => x === id)).map(id =>
      el("button", { type: "button", onclick: () => { disposition.push([id, W[id].tailles[0]]); sauverDisposition(); dessinerGrille(); } }, "+ " + W[id].nom)),
    ...["Travaux en cours", "Boîte à outils", "Ce que je retiens"].map(n => el("button", { type: "button", disabled: true }, n + " · bientôt")));
}
function deplacer(de, vers) { const [m] = disposition.splice(de, 1); disposition.splice(vers, 0, m); sauverDisposition(); dessinerGrille(); }

// ---------- action rapide ----------
let zoneProp, demandeInitiale = "";
function iso(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; }
function jolieDate(s) { const [a, m, j] = s.split("-").map(Number); return libJour(new Date(a, m - 1, j)); }

function attente(message) {
  zoneProp.replaceChildren(el("div", { class: "prop attente" }, el("div", { class: "prop-tete" }, el("span", { class: "orbe petite reflechit" }, el("i")), el("span", {}, message))));
}

async function proposer(texte, precision = "", precedente = null) {
  attente(precision ? "Je prends en compte ta précision…" : "Je regarde ce que tu me demandes…");
  try {
    const p = await api("/api/rapide/proposer", { methode: "POST", corps: { texte, precision, precedente } });
    p.date = p.dates_possibles.length === 1 ? p.dates_possibles[0] : "";
    dessinerProp(p);
  } catch (e) {
    zoneProp.replaceChildren(el("div", { class: "prop" }, el("p", { class: "erreur-txt" }, e.message),
      el("button", { class: "bouton", type: "button", onclick: () => zoneProp.replaceChildren() }, "Fermer")));
  }
}

function manques(p) {
  if (p.genre === "agenda") return [!p.titre && "le titre", !p.date && "le jour", !p.heure && "l'heure"].filter(Boolean);
  if (p.genre === "tache") return [!p.titre && "l'intitulé"].filter(Boolean);
  return [];
}

function dessinerProp(p) {
  const fermer = () => zoneProp.replaceChildren();
  const tete = el("div", { class: "prop-tete", tabindex: "-1" }, el("span", { class: "orbe petite" }, el("i")));
  const carte = el("div", { class: "prop" }, tete);
  if (p.genre === "conversation") {
    tete.append(el("span", {}, "Ça mérite une ", el("b", {}, "vraie conversation"), " plutôt qu'une action rapide."));
    carte.append(el("div", { class: "prop-actions" },
      el("button", { class: "bouton prim", type: "button", onclick: () => { etatApp.brouillon = demandeInitiale; aller("#/nouvelle"); } }, "Ouvrir une conversation"),
      el("button", { class: "bouton", type: "button", onclick: fermer }, "Annuler")));
    zoneProp.replaceChildren(carte); tete.focus(); return;
  }
  tete.append(el("span", {}, "Je vais ", el("b", {}, p.genre === "agenda" ? "ajouter à ton agenda" : "ajouter à ta to-do"), " :"));
  const champs = el("div", { class: "champs" });
  const question = el("p", { class: "question", "aria-live": "polite" });
  const valider = el("button", { class: "bouton prim", type: "button" }, p.genre === "agenda" ? "Ajouter à l'agenda" : "Ajouter à la to-do");
  const ecritureOk = p.genre !== "agenda" || etatApp.reglages.agenda_ecriture_validee;
  const maj = () => {
    const m = manques(p);
    valider.disabled = m.length > 0 || !ecritureOk;
    question.textContent = (p.genre === "agenda" && !p.date && p.dates_possibles.length > 1) ? (p.question || "Quel jour ?") : (m.length ? `Il me manque ${m.join(", ")}.` : (p.question && !p.heure ? p.question : ""));
    champs.querySelectorAll("label[data-requis]").forEach(l => l.classList.toggle("manque", !l.querySelector("input").value));
  };
  const champ = (lib, input, requis, large) => { const l = el("label", { class: "champ" + (large ? " large" : ""), "data-requis": requis ? "1" : null }, lib, input); champs.append(l); return input; };
  const entree = (type, val, f) => { const i = el("input", { type, value: val || "" }); i.addEventListener("input", () => { f(i.value.trim()); maj(); }); return i; };
  const choix = (opts, val, f) => { const s = el("select", {}, opts.map(([v, t]) => el("option", { value: v, selected: v === val }, t))); s.addEventListener("change", () => { f(s.value); maj(); }); return s; };

  if (p.genre === "agenda") {
    champ("Titre", entree("text", p.titre, v => p.titre = v), true);
    if (!p.date && p.dates_possibles.length > 1) {
      champs.append(el("div", { class: "champ large manque" }, "Jour", el("div", { class: "choix-jour" },
        p.dates_possibles.map(d => el("button", { type: "button", onclick: () => { p.date = d; dessinerProp(p); } }, jolieDate(d))))));
    } else champ("Jour", entree("date", p.date, v => p.date = v), true);
    champ("Heure", entree("time", p.heure, v => p.heure = v), true);
    const durees = [[15, "15 min"], [30, "30 min"], [45, "45 min"], [60, "1 h"], [90, "1 h 30"], [120, "2 h"], [180, "3 h"]];
    if (!durees.some(([v]) => v === p.duree_minutes)) durees.push([p.duree_minutes, `${p.duree_minutes} min`]);
    champ("Durée", choix(durees.map(([v, t]) => [String(v), t]), String(p.duree_minutes), v => p.duree_minutes = Number(v)));
  } else {
    champ("Tâche", entree("text", p.titre, v => p.titre = v), true, true);
    champ("Section", choix([["Perso", "Perso"], ["Pro", "Pro"]], p.section, v => p.section = v));
    champ("Priorité", choix([["haute", "Haute"], ["moyenne", "Moyenne"], ["basse", "Basse"]], p.priorite, v => p.priorite = v));
  }
  const zp = el("form", { class: "preciser", hidden: true },
    el("input", { class: "saisie-simple", "aria-label": "Ta précision", placeholder: "Ex. à 10h, jeudi prochain, 30 min…" }),
    el("button", { class: "bouton prim", type: "submit" }, "Envoyer"));
  zp.addEventListener("submit", e => { e.preventDefault(); const v = zp.querySelector("input").value.trim(); if (v) proposer(demandeInitiale, v, p); });

  valider.addEventListener("click", async () => {
    if (manques(p).length) return;
    valider.disabled = true; valider.textContent = "Ajout…";
    try {
      const r = await api("/api/rapide/valider", { methode: "POST", corps: { genre: p.genre === "tache" ? "tache" : "agenda", titre: p.titre, date: p.date, heure: p.heure, duree_minutes: p.duree_minutes, section: p.section, priorite: p.priorite } });
      if (r.ok === false) throw new Error(r.message || "Claude n'a pas pu créer l'événement.");
      const resume = p.genre === "agenda" ? `${p.titre}, ${jolieDate(p.date).toLowerCase()} à ${p.heure.replace(":", " h ")}` : p.titre;
      const ok = el("div", { class: "prop ok" }, el("div", { class: "prop-tete", tabindex: "-1" }, el("span", {}, "✓"),
        el("span", {}, (p.genre === "agenda" ? "Ajouté à ton agenda : " : "Ajouté à ta to-do : ") + resume),
        p.genre === "tache" ? el("button", { class: "bouton", type: "button", style: "margin-left:auto", onclick: async () => {
          try { await api(`/api/taches/${r.tache.id}`, { methode: "DELETE" }); } catch (e) { toast(e.message); }
          fermer(); chargerTaches(true);
        } }, "Annuler l'ajout") : el("span", { class: "doux", style: "margin-left:auto" }, "Pour l'annuler : supprime-le dans Google Agenda."),
        el("button", { class: "bouton", type: "button", onclick: fermer }, "Fermer")));
      zoneProp.replaceChildren(ok); ok.firstChild.focus();
      if (p.genre === "tache") chargerTaches(true); else { await charger("agenda", "/api/agenda"); dessinerGrille(); }
    } catch (e) { valider.disabled = false; valider.textContent = "Réessayer"; question.textContent = e.message; }
  });

  carte.append(champs, question, el("div", { class: "prop-actions" }, valider,
    el("button", { class: "bouton", type: "button", onclick: () => { zp.hidden = !zp.hidden; if (!zp.hidden) zp.querySelector("input").focus(); } }, "Préciser…"),
    el("button", { class: "bouton", type: "button", onclick: fermer }, "Annuler"),
    el("a", { class: "lien", href: "#/nouvelle", onclick: () => { etatApp.brouillon = demandeInitiale; } }, "Continuer en conversation ↗")), zp,
    el("p", { class: "note-vraie" }, !ecritureOk
      ? "L'ajout direct à l'agenda n'a pas encore été testé avec toi : il est désactivé. Active-le dans Réglages."
      : (p.genre === "agenda" ? "Rien n'est écrit dans ton agenda avant ton clic sur « Ajouter »." : "Rien n'est ajouté avant ton clic sur « Ajouter ».")));
  zoneProp.replaceChildren(carte); maj(); tete.focus();
}

// ---------- page ----------
export async function pageAccueil(vue) {
  const h = auj().getHours();
  const salut = h < 5 ? "Bonne nuit" : h < 18 ? "Bonjour" : "Bonsoir";
  const sous = el("p", {}, auj().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" }).replace(/^./, c => c.toUpperCase()));
  const modifier = el("button", { class: "bouton", type: "button" }, "Modifier les widgets");
  const champ = el("input", { id: "demande", placeholder: "Qu'est-ce qu'on fait aujourd'hui ?  Ex. ajoute dans mon agenda le rdv coiffeur de ce jeudi", autocomplete: "off" });
  const envoyer = el("button", { class: "rond env plein", type: "submit", "aria-label": "Envoyer", disabled: true }, ic("envoyer"));
  const form = el("form", { class: "saisie" }, el("label", { class: "sr", for: "demande" }, "Ta demande"), champ,
    boutonMicro(champ), envoyer);
  zoneProp = el("div", { id: "proposition", "aria-live": "polite" });
  grille = el("div", { class: "grille", "aria-live": "polite" });
  galerie = el("section", { class: "galerie", "aria-label": "Ajouter un widget" }, el("h2", {}, "Ajouter un widget"),
    el("p", {}, "Les widgets retirés reviennent ici. Les grisés sont prévus mais pas encore construits."), el("div", { class: "liste" }));
  vue.replaceChildren(el("div", { class: "page" },
    el("div", { class: "haut" }, el("div", {}, el("h1", {}, etatApp.reglages.prenom ? `${salut} ${etatApp.reglages.prenom}` : salut), sous), el("div", { class: "actions" }, selecteurMode(), selecteurTeinte(), modifier)),
    form, zoneProp, el("div", { class: "zone" }, grille, galerie)));

  champ.addEventListener("input", () => { envoyer.disabled = !champ.value.trim(); garderBrouillon("accueil", champ.value); });
  form.addEventListener("submit", e => { e.preventDefault(); const t = champ.value.trim(); if (!t) return; demandeInitiale = t; champ.value = ""; envoyer.disabled = true; effacerBrouillon("accueil"); proposer(t); });
  const b = lireBrouillon("accueil");
  if (b.texte) { champ.value = b.texte; envoyer.disabled = false; }
  modifier.addEventListener("click", () => { edition = !edition; modifier.textContent = edition ? "Terminé" : "Modifier les widgets"; modifier.classList.toggle("prim", edition); dessinerGrille(); });
  zoneProp.addEventListener("keydown", e => { if (e.key === "Escape") { zoneProp.replaceChildren(); champ.focus(); } });

  disposition = (etatApp.reglages.disposition || DEFAUT).filter(([id]) => W[id]);
  edition = false; donnees = {};
  dessinerGrille();
  // Quota à part : le demander à Claude Code prend quelques secondes, le reste de l'accueil n'attend pas.
  charger("quota", "/api/quota").then(() => { if (!edition) dessinerGrille(); });
  await Promise.all([
    charger("agenda", "/api/agenda"), chargerTaches(false),
    charger("conversations", "/api/conversations", r => r.conversations),
    charger("projets", "/api/projets", r => r.projets),
  ]);
  const nbRdv = (donnees.agenda?.evenements || []).filter(e => new Date(e.debut).toDateString() === auj().toDateString()).length;
  const nbT = (donnees.taches?.taches || []).filter(x => !x.fait).length;
  sous.textContent += ` · ${nbRdv} rendez-vous aujourd'hui · ${nbT} tâche${nbT > 1 ? "s" : ""} à faire`;
  dessinerGrille();
}
