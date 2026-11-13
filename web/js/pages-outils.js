// Pages ajoutées la nuit du 13/11 : Boîte à outils, Antisèche, Ce que je retiens.
import { api, el, depuis, markdown } from "./outils.js";
import { etatApp } from "./etat.js";

const page = (titre, sous, ...contenu) => el("div", { class: "page" },
  el("div", { class: "haut" }, el("div", {}, el("h1", {}, titre), sous ? el("p", {}, sous) : null)), ...contenu);

// ---------- Boîte à outils : les skills en tuiles ----------
export async function pageOutils(vue) {
  const grille = el("div", { class: "grille-projets" }, el("p", { class: "vide" }, "Chargement…"));
  vue.replaceChildren(page("Boîte à outils", "Tout ce que je sais faire avec tes skills. « Utiliser » ouvre une conversation avec la commande prête : tu complètes, puis tu envoies.", grille));
  try {
    const { commandes } = await api("/api/commandes");
    const skills = commandes.filter(c => c.genre === "skill");
    grille.replaceChildren(...(skills.length ? skills.map(c => el("div", { class: "carte outil" },
      el("b", {}, "/" + c.nom), el("p", { class: "doux" }, c.description || "Sans description."),
      el("button", { class: "bouton", type: "button", onclick: () => { etatApp.brouillon = `/${c.nom} `; location.hash = "#/nouvelle"; } }, "Utiliser")))
      : [el("p", { class: "vide" }, "Aucun skill trouvé.")]));
  } catch (e) { grille.replaceChildren(el("p", { class: "erreur-txt" }, e.message)); }
}

// ---------- Antisèche : les gestes à connaître ----------
const GESTES = [
  ["Dans ce dashboard", [
    ["Entrée", "Envoyer le message"], ["Maj + Entrée", "Aller à la ligne"],
    ["/", "En début de message : ouvrir le menu des commandes (flèches + Entrée pour choisir, Échap pour fermer)"],
    ["Micro", "Clic pour dicter, clic pour arrêter : le texte s'ajoute sans être envoyé"],
    ["Carré (pendant une réponse)", "Interrompre Claude"], ["Échap", "Fermer une fenêtre ou une proposition"],
    ["Cmd + R", "Recharger la page (ton brouillon est gardé)"]]],
  ["Dans le terminal Claude Code", [
    ["Maj + Tab", "Changer de mode d'autorisation (le mode actif s'affiche en bas)"],
    ["Échap", "Interrompre Claude pendant qu'il travaille"],
    ["Échap deux fois", "Revenir à un message précédent pour le modifier"],
    ["! commande", "Lancer une commande du terminal sans quitter Claude (ex. ! gh auth login)"],
    ["@ fichier", "Citer un fichier dans ton message"],
    ["Ctrl + C deux fois", "Quitter Claude Code"]]],
  ["Commandes utiles", [
    ["/resume", "Reprendre une conversation précédente"], ["/permissions", "Voir et changer les autorisations"],
    ["/compact", "Résumer la conversation pour libérer de la place"], ["/statusline-aide", "Comprendre la ligne du bas"],
    ["/session-note", "Archiver la session dans Obsidian"]]],
];
export function pageAntiseche(vue) {
  vue.replaceChildren(page("Antisèche", "Les gestes à connaître, au même endroit.",
    ...GESTES.map(([titre, lignes]) => el("section", { class: "carte", style: "margin-bottom:16px" },
      el("h2", { style: "margin:0 0 8px;font-size:17px" }, titre),
      el("dl", { class: "gestes" }, lignes.flatMap(([t, d]) => [el("dt", {}, el("kbd", {}, t)), el("dd", {}, d)]))))));
}

// ---------- Travaux en cours : les sessions Claude Code en arrière-plan ----------
export async function pageTravaux(vue) {
  const zone = el("div", { class: "liste-conv" }, el("p", { class: "vide" }, "Chargement…"));
  vue.replaceChildren(page("Travaux en cours", "Ce que Claude fait en arrière-plan (lecture seule). Pour répondre à un travail qui attend, utilise le terminal : claude agents.", zone));
  try {
    const { travaux } = await api("/api/travaux");
    if (!travaux.length) { zone.replaceChildren(el("p", { class: "vide" }, "Aucun travail en arrière-plan.")); return; }
    zone.replaceChildren(...travaux.map(t => {
      const contenu = [el("div", { style: "min-width:0" }, el("b", {}, t.detail || t.id),
        t.besoin && t.besoin !== t.detail ? el("div", { class: "doux" }, "Question : " + t.besoin) : null),
        el("div", { style: "display:flex;gap:8px;align-items:center;flex:none" }, el("span", { class: "puce etat-" + t.etat }, t.libelle), el("span", { class: "doux" }, depuis(t.maj * 1000)))];
      // un travail encore actif ne s'ouvre pas ici : y écrire en même temps mélangerait les deux fils
      return t.session && t.etat !== "working" ? el("a", { href: `#/conversation/${t.session}` }, ...contenu) : el("div", { class: "ligne-travail" }, ...contenu);
    }));
  } catch (e) { zone.replaceChildren(el("p", { class: "erreur-txt" }, e.message)); }
}

// ---------- Galerie : images envoyées et maquettes ----------
export async function pageGalerie(vue) {
  const zone = el("div", {}, el("p", { class: "vide" }, "Chargement…"));
  vue.replaceChildren(page("Galerie", "Les images que tu m'as envoyées et les maquettes du dashboard.", zone));
  try {
    const g = await api("/api/galerie");
    const images = g.images.length ? el("div", { class: "galerie-images" }, g.images.map(i => el("button", { type: "button", "aria-label": "Agrandir l'image",
      onclick: () => { const d = document.getElementById("visionneuse"); document.getElementById("vis-img").src = i.url; d.showModal(); d.onclick = () => d.close(); } },
      el("img", { src: i.url, alt: "Image envoyée " + depuis(i.le * 1000), loading: "lazy" }))))
      : el("p", { class: "vide" }, "Aucune image envoyée pour l'instant.");
    zone.replaceChildren(el("h2", { style: "font-size:17px" }, "Images"), images,
      el("h2", { style: "font-size:17px;margin-top:24px" }, "Maquettes"),
      el("div", { class: "liste-conv" }, g.maquettes.map(m => el("a", { href: m.url, target: "_blank", rel: "noopener" }, el("b", {}, m.nom), el("span", { class: "doux" }, "ouvrir ↗")))));
  } catch (e) { zone.replaceChildren(el("p", { class: "erreur-txt" }, e.message)); }
}

// ---------- Ce que je retiens : la mémoire de Claude en clair ----------
export async function pageMemoire(vue) {
  const zone = el("div", {}, el("p", { class: "vide" }, "Chargement…"));
  vue.replaceChildren(page("Ce que je retiens", "Ce que Claude garde en mémoire sur toi d'une session à l'autre (lecture seule). Pour corriger, dis-le-moi dans une conversation.", zone));
  try {
    const { souvenirs } = await api("/api/memoire");
    if (!souvenirs.length) { zone.replaceChildren(el("p", { class: "vide" }, "Aucun souvenir enregistré.")); return; }
    const rubriques = [...new Set(souvenirs.map(s => s.rubrique))];
    zone.replaceChildren(...rubriques.map(r => el("section", { style: "margin-bottom:24px" },
      el("h2", { style: "font-size:17px;margin:0 0 10px" }, r),
      souvenirs.filter(s => s.rubrique === r).map(s => {
        const corps = el("div", { class: "reponse", hidden: true });
        corps.innerHTML = markdown(s.texte);  // markdown() échappe tout le HTML d'abord
        const bouton = el("button", { type: "button", class: "souvenir-tete", "aria-expanded": "false" },
          el("b", {}, s.description || s.nom), el("span", { class: "doux" }, depuis(s.modifie * 1000)));
        bouton.addEventListener("click", () => { corps.hidden = !corps.hidden; bouton.setAttribute("aria-expanded", String(!corps.hidden)); });
        return el("div", { class: "carte souvenir" }, bouton, corps);
      }))));
  } catch (e) { zone.replaceChildren(el("p", { class: "erreur-txt" }, e.message)); }
}
