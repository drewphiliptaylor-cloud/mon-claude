// Menu des commandes « / » : s'ouvre quand le message commence par « / », se filtre à la frappe.
import { api, el } from "./outils.js";

let cache = null;
async function charger() {
  if (!cache) {
    try { cache = (await api("/api/commandes")).commandes; }
    catch { cache = []; }
  }
  return cache;
}

// Branche le menu sur une zone de saisie. `ancre` = élément positionné au-dessus duquel le menu s'affiche.
export function brancherMenuCommandes(zone, ancre) {
  const liste = el("div", { class: "menu-commandes", role: "listbox", id: "menu-commandes", "aria-label": "Commandes", hidden: true });
  ancre.style.position = "relative";
  ancre.append(liste);
  zone.setAttribute("aria-controls", "menu-commandes");
  zone.setAttribute("aria-autocomplete", "list");
  let choix = [], actif = 0;

  const fermer = () => { liste.hidden = true; zone.setAttribute("aria-expanded", "false"); zone.removeAttribute("aria-activedescendant"); };
  const motCle = () => { const m = zone.value.match(/^\/([^\s]*)$/); return m ? m[1].toLowerCase() : null; };

  function dessiner() {
    liste.replaceChildren(...choix.map((c, i) => el("div", {
      class: "option-commande" + (i === actif ? " actif" : ""), role: "option", id: `cmd-${i}`, "aria-selected": String(i === actif),
      onmousedown: e => { e.preventDefault(); inserer(c); } },
      el("b", {}, "/" + c.nom), c.description ? el("span", {}, c.description) : null)));
    if (choix.length) { zone.setAttribute("aria-activedescendant", `cmd-${actif}`); liste.children[actif]?.scrollIntoView({ block: "nearest" }); }
  }
  function inserer(c) {
    zone.value = `/${c.nom} `;
    zone.dispatchEvent(new Event("input"));
    fermer(); zone.focus();
    zone.setSelectionRange(zone.value.length, zone.value.length);
  }
  async function maj() {
    const mot = motCle();
    if (mot === null) return fermer();
    const toutes = await charger();
    if (motCle() !== mot) return;  // le texte a changé pendant le chargement : une autre mise à jour suit
    choix = toutes.filter(c => c.nom.toLowerCase().includes(mot) || (c.description || "").toLowerCase().includes(mot))
      .sort((a, b) => (b.nom.toLowerCase().startsWith(mot)) - (a.nom.toLowerCase().startsWith(mot))).slice(0, 8);
    actif = 0;
    if (!choix.length) return fermer();
    liste.hidden = false; zone.setAttribute("aria-expanded", "true");
    dessiner();
  }
  zone.addEventListener("input", maj);
  zone.form?.addEventListener("submit", fermer);
  zone.addEventListener("blur", () => setTimeout(fermer, 100));
  // en phase de capture : passe avant le gestionnaire « Entrée = envoyer »
  zone.addEventListener("keydown", e => {
    if (liste.hidden) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault(); actif = (actif + (e.key === "ArrowDown" ? 1 : -1) + choix.length) % choix.length; dessiner();
    } else if ((e.key === "Enter" || e.key === "Tab") && !e.isComposing) {
      e.preventDefault(); e.stopImmediatePropagation(); inserer(choix[actif]);
    } else if (e.key === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); fermer(); }
  }, true);
}
