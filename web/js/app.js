// Point d'entrée : réglages, menu repliable, routeur par #.
import { api, el, toast } from "./outils.js";
import { etatApp } from "./etat.js";
import { initTeintes } from "./teintes.js";
import { pageAccueil } from "./accueil.js";
import { pageConversation } from "./conversation.js";
import { pageHistorique, pageProjets, pageTaches, pageAgenda, pageReglages } from "./pages.js";
import { pageOutils, pageAntiseche, pageMemoire, pageTravaux, pageGalerie } from "./pages-outils.js";

const vue = document.getElementById("vue");
const menu = document.getElementById("menu");
const replier = document.getElementById("replier");

function appliquerMenu(reduit) {
  menu.classList.toggle("reduit", reduit);
  replier.setAttribute("aria-expanded", String(!reduit));
  replier.setAttribute("aria-label", reduit ? "Agrandir le menu" : "Réduire le menu");
}
replier.addEventListener("click", async () => {
  const r = !menu.classList.contains("reduit"); appliquerMenu(r);
  try { await api("/api/reglages/menu_reduit", { methode: "PUT", corps: { valeur: r } }); } catch { /* sans gravité */ }
});
// bulle avec le nom de l'entrée quand le menu est réduit
let bulle = null;
menu.querySelectorAll(".it").forEach(it => {
  const montrer = () => {
    if (!menu.classList.contains("reduit")) return;
    bulle?.remove();
    const r = it.getBoundingClientRect();
    bulle = el("div", { class: "bulle-menu", role: "tooltip" }, it.getAttribute("title") || it.querySelector(".lib").textContent);
    bulle.style.top = (r.top + r.height / 2 - 14) + "px";
    document.body.append(bulle);
  };
  const cacher = () => { bulle?.remove(); bulle = null; };
  it.addEventListener("mouseenter", montrer); it.addEventListener("focus", montrer);
  it.addEventListener("mouseleave", cacher); it.addEventListener("blur", cacher);
});

etatApp.majCompteurs = d => {
  if (!d) return;
  const n = d.taches.filter(x => !x.fait).length;
  document.getElementById("nb-taches").textContent = n || "";
  const m = document.getElementById("menu-taches");
  if (n) m.setAttribute("data-badge", String(n)); else m.removeAttribute("data-badge");
};

const ROUTES = { accueil: pageAccueil, historique: pageHistorique, projets: pageProjets, taches: pageTaches, agenda: pageAgenda, reglages: pageReglages,
                 outils: pageOutils, antiseche: pageAntiseche, memoire: pageMemoire, travaux: pageTravaux, galerie: pageGalerie };

async function router() {
  const [, nom = "accueil", id] = location.hash.split("/");
  // la conversation qui vient de recevoir son identifiant ne doit pas être rechargée
  if (nom === "conversation" && id && id === etatApp.conversationActive && vue.querySelector(".conv")) return;
  if (etatApp.fermerConversation) { etatApp.fermerConversation(); etatApp.fermerConversation = null; }
  etatApp.conversationActive = nom === "conversation" ? id : null;
  const actif = nom === "conversation" ? "historique" : nom;
  menu.querySelectorAll(".it[data-route]").forEach(a => {
    const on = a.dataset.route === actif; a.classList.toggle("on", on);
    if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  try {
    if (nom === "conversation" && id) await pageConversation(vue, id);
    else if (nom === "nouvelle") await pageConversation(vue, null, id ? decodeURIComponent(id) : null);
    else await (ROUTES[nom] || pageAccueil)(vue);
  } catch (e) {
    vue.replaceChildren(el("div", { class: "page" }, el("p", { class: "erreur-txt" }, "Cette page n'a pas pu s'afficher : " + e.message)));
  }
}

async function demarrer() {
  try {
    etatApp.reglages = await api("/api/reglages");
  } catch (e) {
    vue.replaceChildren(el("div", { class: "page" }, el("h1", {}, "Serveur injoignable"), el("p", { class: "erreur-txt" }, e.message)));
    return;
  }
  initTeintes(etatApp.reglages);
  appliquerMenu(!!etatApp.reglages.menu_reduit);
  api("/api/taches").then(etatApp.majCompteurs).catch(() => {});
  api("/api/projets").then(d => { document.getElementById("nb-projets").textContent = d.projets.length || ""; }).catch(() => {});
  window.addEventListener("hashchange", router);
  router();
}
window.addEventListener("unhandledrejection", e => toast("Erreur : " + (e.reason?.message || e.reason)));
demarrer();
