// Teintes : deux couleurs (dominante, secondaire) → toutes les nuances de l'interface.
import { api, el, toast } from "./outils.js";

export const BASE = [
  { id: "ambre", nom: "Ambre", a: "#e5a00d", b: "#f0c25a" },
  { id: "menthe", nom: "Menthe & lavande", a: "#4fd1b5", b: "#b9a6ff" },
];
const HEX = /^#[0-9a-f]{6}$/i;
const etat = { perso: [], active: "ambre" };
const toutes = () => BASE.concat(etat.perso);
const trouver = id => toutes().find(t => t.id === id) || BASE[0];

export function poserCouleurs(a, b) {
  const st = document.documentElement.style, mix = (c, p, d) => `color-mix(in srgb, ${c} ${p}%, ${d})`;
  st.setProperty("--ambre", a);
  st.setProperty("--ambre-doux", mix(a, 16, "transparent"));
  st.setProperty("--acc-clair", mix(a, 55, "#fff"));
  st.setProperty("--acc-fonce", mix(a, 30, "#000"));
  st.setProperty("--icone", b);
  st.setProperty("--anneau", mix(b, 35, "transparent"));
  st.setProperty("--lueur", mix(b, 60, "transparent"));
}

// ---------- mode clair / sombre ----------
const MODES = [["auto", "Auto", "Suit le réglage de ton Mac"], ["sombre", "Sombre", "Mode sombre"], ["clair", "Clair", "Mode clair"]];
export function appliquerMode(mode) {
  if (!MODES.some(([m]) => m === mode)) mode = "auto";
  document.documentElement.dataset.mode = mode;
  try { localStorage.setItem("mode", mode); } catch { /* sans gravité : évite juste un flash au chargement */ }
  document.querySelectorAll(".choix-mode button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
}
export function selecteurMode() {
  const groupe = el("div", { class: "choix-mode", role: "group", "aria-label": "Apparence" },
    MODES.map(([m, lib, titre]) => el("button", { type: "button", "data-mode": m, title: titre,
      "aria-pressed": String(document.documentElement.dataset.mode === m), onclick: async () => {
        appliquerMode(m);
        try { await api("/api/reglages/mode", { methode: "PUT", corps: { valeur: m } }); }
        catch (e) { toast("Apparence non enregistrée : " + e.message); }
      } }, lib)));
  return groupe;
}

export function initTeintes(reglages) {
  appliquerMode(reglages.mode || "auto");
  etat.perso = (reglages.teintes || []).filter(t => t && HEX.test(t.a) && HEX.test(t.b) && typeof t.nom === "string");
  etat.active = reglages.teinte_active || "ambre";
  const t = trouver(etat.active); poserCouleurs(t.a, t.b);
}

async function sauver() {
  try {
    await api("/api/reglages/teintes", { methode: "PUT", corps: { valeur: etat.perso } });
    await api("/api/reglages/teinte_active", { methode: "PUT", corps: { valeur: etat.active } });
  } catch (e) { toast("Teinte non enregistrée : " + e.message); }
}

const echantillon = t => { const e = el("span", { class: "ech", "aria-hidden": "true" }); e.style.setProperty("--a", t.a); e.style.setProperty("--b", t.b); return e; };

// Bouton « Teinte » + fenêtre de choix et d'édition. Renvoie l'élément à insérer.
export function selecteurTeinte() {
  const ech = el("span", { class: "ech" }), nom = el("span");
  const btn = el("button", { class: "teinte-btn", type: "button", "aria-haspopup": "dialog", "aria-expanded": "false" }, ech, nom);
  const liste = el("div");
  const vueListe = el("div", {}, el("h2", {}, "Teintes"), liste,
    el("button", { class: "ajout-t", type: "button", onclick: () => ouvrirEditeur(null) }, "+ Créer une teinte"));
  const edNom = el("input", { type: "text", maxlength: "24", placeholder: "Ex. Forêt" });
  const edA = el("input", { type: "color", "aria-label": "Couleur dominante" }), hexA = el("code");
  const edB = el("input", { type: "color", "aria-label": "Couleur secondaire" }), hexB = el("code");
  const err = el("p", { class: "erreur-txt", role: "alert" });
  const titreEd = el("h2", { style: "margin:0" }, "Nouvelle teinte");
  const ed = el("form", { class: "editeur", hidden: true }, titreEd,
    el("label", { class: "champ" }, "Nom", edNom),
    el("div", { class: "champ" }, "Couleur dominante", el("small", {}, "boutons, page active, logo, jauges"), el("label", { class: "couleur" }, edA, hexA)),
    el("div", { class: "champ" }, "Couleur secondaire", el("small", {}, "pictos du menu, cercles"), el("label", { class: "couleur" }, edB, hexB)),
    err,
    el("div", { class: "actions", style: "justify-content:flex-end" },
      el("button", { class: "bouton", type: "button", onclick: () => fermerEditeur() }, "Annuler"),
      el("button", { class: "bouton prim", type: "submit" }, "Enregistrer")));
  const pop = el("div", { class: "pop", role: "dialog", "aria-label": "Teintes", hidden: true }, vueListe, ed);
  const ancre = el("div", { class: "ancre" }, btn, pop);
  let enCours = null;

  function majBouton() {
    const t = trouver(etat.active); nom.textContent = t.nom; ech.style.setProperty("--a", t.a); ech.style.setProperty("--b", t.b);
  }
  function choisir(id) { etat.active = trouver(id).id; const t = trouver(id); poserCouleurs(t.a, t.b); majBouton(); lister(); sauver(); }
  function lister() {
    liste.replaceChildren(...toutes().map(t => {
      const row = el("div", { class: "ligne-t" },
        el("button", { class: "choisir", type: "button", "aria-pressed": String(t.id === etat.active), onclick: () => choisir(t.id) }, echantillon(t), el("span", {}, t.nom)));
      if (!BASE.includes(t)) {
        row.append(el("button", { class: "mini", type: "button", "aria-label": "Modifier " + t.nom, onclick: () => ouvrirEditeur(t) }, "✎"),
          el("button", { class: "mini", type: "button", "aria-label": "Supprimer " + t.nom, onclick: () => {
            if (!confirm(`Supprimer la teinte « ${t.nom} » ?`)) return;
            etat.perso = etat.perso.filter(x => x !== t); choisir(etat.active === t.id ? "ambre" : etat.active);
          } }, "✕"));
      }
      return row;
    }));
  }
  function apercu() { hexA.textContent = edA.value; hexB.textContent = edB.value; poserCouleurs(edA.value, edB.value); }
  function ouvrirEditeur(t) {
    enCours = t; const base = t || trouver(etat.active);
    titreEd.textContent = t ? "Modifier la teinte" : "Nouvelle teinte";
    edNom.value = t ? t.nom : ""; edA.value = base.a; edB.value = base.b; err.textContent = ""; apercu();
    vueListe.hidden = true; ed.hidden = false; edNom.focus();
  }
  function fermerEditeur() { if (ed.hidden) return; ed.hidden = true; vueListe.hidden = false; const t = trouver(etat.active); poserCouleurs(t.a, t.b); }
  function ouvrir(o) { if (!o) fermerEditeur(); pop.hidden = !o; btn.setAttribute("aria-expanded", String(o)); if (o) pop.querySelector(".choisir")?.focus(); }
  edA.addEventListener("input", apercu); edB.addEventListener("input", apercu);
  ed.addEventListener("submit", e => {
    e.preventDefault();
    const n = edNom.value.trim();
    if (!n) { err.textContent = "Donne un nom à ta teinte."; edNom.focus(); return; }
    if (toutes().some(t => t !== enCours && t.nom.toLowerCase() === n.toLowerCase())) { err.textContent = "Ce nom existe déjà."; edNom.focus(); return; }
    if (enCours) Object.assign(enCours, { nom: n, a: edA.value, b: edB.value });
    else { enCours = { id: "t" + Date.now(), nom: n, a: edA.value, b: edB.value }; etat.perso.push(enCours); }
    ed.hidden = true; vueListe.hidden = false; choisir(enCours.id);
  });
  btn.addEventListener("click", () => ouvrir(pop.hidden));
  ancre.addEventListener("keydown", e => { if (e.key === "Escape" && !pop.hidden) { ouvrir(false); btn.focus(); } });
  const dehors = e => {
    if (!ancre.isConnected) return document.removeEventListener("click", dehors);  // page quittée
    if (!pop.hidden && !ancre.contains(e.target)) ouvrir(false);
  };
  document.addEventListener("click", dehors);
  majBouton(); lister();
  return ancre;
}
