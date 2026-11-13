// Pages du menu : Historique, Projets, À faire, Agenda, Réglages.
import { api, el, toast, libJour, heure, depuis } from "./outils.js";
import { etatApp } from "./etat.js";
import { ligneTache } from "./accueil.js";
import { selecteurTeinte, selecteurMode } from "./teintes.js";
import { reglageNotifications } from "./notifications.js";

const page = (titre, sous, ...contenu) => el("div", { class: "page" },
  el("div", { class: "haut" }, el("div", {}, el("h1", {}, titre), sous ? el("p", {}, sous) : null)), ...contenu);

export async function pageHistorique(vue) {
  const liste = el("div", { class: "liste-conv" }, el("p", { class: "vide" }, "Chargement…"));
  vue.replaceChildren(page("Historique", "Tes conversations Claude Code, y compris celles du terminal.", liste));
  try {
    const { conversations } = await api("/api/conversations");
    liste.replaceChildren(...(conversations.length ? conversations.map(c => el("a", { href: `#/conversation/${c.id}` },
      el("b", {}, c.titre), el("span", { class: "doux" }, depuis(c.maj)))) : [el("p", { class: "vide" }, "Aucune conversation.")]));
  } catch (e) { liste.replaceChildren(el("p", { class: "erreur-txt" }, e.message)); }
}

export async function pageProjets(vue) {
  const grille = el("div", { class: "grille-projets" }, el("p", { class: "vide" }, "Chargement…"));
  vue.replaceChildren(page("Projets", "Lu dans ton CLAUDE.md et tes notes de session (lecture seule).", grille));
  try {
    const { projets } = await api("/api/projets");
    grille.replaceChildren(...(projets.length ? projets.map(p => el("div", { class: "carte" },
      el("div", { style: "display:flex;justify-content:space-between;gap:8px;align-items:baseline" }, el("b", {}, p.nom.replace(/_/g, " ")), el("span", { class: "puce" }, p.statut)),
      p.detail ? el("p", { class: "doux" }, "Reste : " + p.detail) : null,
      el("p", { class: "doux" }, el("code", {}, p.emplacement)),
      p.derniere_note ? el("p", { class: "doux" }, `Dernière note : ${p.derniere_note.titre} (${p.derniere_note.date})`) : null,
      p.dossier ? el("a", { class: "bouton", href: `#/nouvelle/${encodeURIComponent(p.nom)}` }, "Nouvelle conversation dans ce projet") : null))
      : [el("p", { class: "vide" }, "Aucun projet trouvé dans le tableau « Mes projets actifs ».")]));
  } catch (e) { grille.replaceChildren(el("p", { class: "erreur-txt" }, e.message)); }
}

export async function pageTaches(vue) {
  const zones = el("div");
  const champ = el("input", { class: "saisie-simple", placeholder: "Nouvelle tâche…", maxlength: "300", "aria-label": "Nouvelle tâche" });
  const section = el("select", { class: "saisie-simple", "aria-label": "Section" }, el("option", { value: "Perso" }, "Perso"), el("option", { value: "Pro" }, "Pro"));
  const prio = el("select", { class: "saisie-simple", "aria-label": "Priorité" }, el("option", { value: "moyenne" }, "Moyenne"), el("option", { value: "haute" }, "Haute"), el("option", { value: "basse" }, "Basse"));
  const form = el("form", { class: "ligne-form", style: "margin-bottom:24px" }, champ, section, prio, el("button", { class: "bouton prim", type: "submit" }, "Ajouter"));
  vue.replaceChildren(page("À faire", "Fichier ~/todo/taches.md — tu peux aussi le modifier à la main.", form, zones));
  async function recharger() {
    try {
      const d = await api("/api/taches");
      etatApp.majCompteurs(d);
      const blocs = ["Pro", "Perso"].map(s => {
        const t = d.taches.filter(x => x.section === s);
        return el("div", { class: "carte", style: "margin-bottom:16px" }, el("h2", { style: "margin:0 0 8px;font-size:17px" }, s),
          t.length ? t.map(x => { const l = ligneTache(x, recharger);
            l.append(el("button", { class: "mini", type: "button", "aria-label": "Supprimer " + x.texte, onclick: async () => {
              if (!confirm(`Supprimer « ${x.texte} » ?`)) return;
              try { await api(`/api/taches/${x.id}`, { methode: "DELETE" }); } catch (e) { toast(e.message); }
              recharger(); } }, "✕")); return l; }) : el("p", { class: "vide" }, "Rien ici."));
      });
      if (d.ice.length) blocs.push(el("div", { class: "carte" }, el("h2", { style: "margin:0 0 8px;font-size:17px" }, "File ICE (skill /to-do, lecture seule)"),
        d.ice.map(i => el("div", { class: "tache" }, el("span", { class: "puce" }, "ICE " + i.score), el("span", { class: "txt" }, i.titre)))));
      zones.replaceChildren(...blocs);
    } catch (e) { zones.replaceChildren(el("p", { class: "erreur-txt" }, e.message)); }
  }
  form.addEventListener("submit", async e => {
    e.preventDefault();
    if (!champ.value.trim()) return;
    try { await api("/api/taches", { methode: "POST", corps: { texte: champ.value, section: section.value, priorite: prio.value } }); champ.value = ""; }
    catch (err) { toast(err.message); }
    recharger();
  });
  await recharger();
}

export async function pageAgenda(vue) {
  const zone = el("div", {}, el("p", { class: "vide" }, "Chargement…"));
  vue.replaceChildren(page("Agenda", "Les 7 prochains jours, lus dans ton Google Agenda (mis à jour toutes les 10 min).", zone));
  try {
    const a = await api("/api/agenda?jours=7");
    if (!a.configure) { zone.replaceChildren(el("p", { class: "doux" }, "Agenda non configuré. "), el("a", { class: "bouton", href: "#/reglages" }, "Ouvrir les réglages")); return; }
    if (a.erreur) { zone.replaceChildren(el("p", { class: "erreur-txt" }, a.erreur)); return; }
    const parJour = new Map();
    a.evenements.forEach(e => { const d = new Date(e.debut), k = d.toDateString(); if (!parJour.has(k)) parJour.set(k, [d, []]); parJour.get(k)[1].push(e); });
    zone.replaceChildren(...(parJour.size ? [...parJour.values()].map(([d, evs]) => el("div", { class: "carte", style: "margin-bottom:16px" },
      el("h2", { style: "margin:0 0 8px;font-size:17px" }, libJour(d)),
      evs.map(e => el("div", { class: "rdv" }, el("span", { class: "h" }, e.journee ? "Jour" : heure(new Date(e.debut))), el("i"),
        el("div", {}, el("b", {}, e.titre), e.lieu ? el("small", {}, e.lieu) : null)))))
      : [el("p", { class: "vide" }, "Rien de prévu sur les 7 prochains jours.")]));
  } catch (e) { zone.replaceChildren(el("p", { class: "erreur-txt" }, e.message)); }
}

export async function pageReglages(vue) {
  const r = etatApp.reglages;
  const lien = el("input", { class: "saisie-simple", type: "url", placeholder: "https://calendar.google.com/calendar/ical/…/basic.ics", "aria-label": "Adresse secrète iCal" });
  const etatLien = el("p", { class: "doux" }, r.ical_configure ? "✓ Agenda configuré. Le lien est gardé sur ton Mac seulement." : "Agenda non configuré.");
  const formLien = el("form", { class: "ligne-form" }, lien, el("button", { class: "bouton prim", type: "submit" }, "Enregistrer"),
    r.ical_configure ? el("button", { class: "bouton", type: "button", onclick: async () => {
      if (!confirm("Oublier le lien de l'agenda ?")) return;
      await api("/api/agenda/lien", { methode: "DELETE" }); r.ical_configure = false; pageReglages(vue); } }, "Oublier") : null);
  formLien.addEventListener("submit", async e => {
    e.preventDefault(); etatLien.textContent = "Vérification…";
    try { const x = await api("/api/agenda/lien", { methode: "PUT", corps: { url: lien.value } }); r.ical_configure = true; lien.value = "";
      etatLien.textContent = `✓ Agenda configuré : ${x.nombre} événement(s) sur 3 jours.`; }
    catch (err) { etatLien.textContent = err.message; }
  });
  const ecriture = el("input", { type: "checkbox", id: "ecriture", checked: !!r.agenda_ecriture_validee });
  ecriture.addEventListener("change", async () => {
    try { await api("/api/reglages/agenda_ecriture_validee", { methode: "PUT", corps: { valeur: ecriture.checked } }); r.agenda_ecriture_validee = ecriture.checked; toast(ecriture.checked ? "Ajout à l'agenda activé." : "Ajout à l'agenda désactivé."); }
    catch (e) { toast(e.message); ecriture.checked = !ecriture.checked; }
  });
  const prenom = el("input", { class: "saisie-simple", type: "text", maxlength: "30", value: r.prenom || "", placeholder: "Ex. Alex", "aria-label": "Ton prénom", autocomplete: "given-name" });
  const formPrenom = el("form", { class: "ligne-form" }, prenom, el("button", { class: "bouton prim", type: "submit" }, "Enregistrer"));
  formPrenom.addEventListener("submit", async e => {
    e.preventDefault();
    try { await api("/api/reglages/prenom", { methode: "PUT", corps: { valeur: prenom.value } }); r.prenom = prenom.value.trim(); toast(r.prenom ? `Bonjour ${r.prenom} !` : "Prénom effacé."); }
    catch (err) { toast(err.message); }
  });
  vue.replaceChildren(page("Réglages", null,
    el("section", { class: "carte reglage" }, el("h2", {}, "Ton prénom"), el("p", { class: "doux" }, "Affiché dans la salutation de l'accueil."), formPrenom),
    el("section", { class: "carte reglage" }, el("h2", {}, "Apparence"), el("p", { class: "doux" }, "Auto suit le mode clair ou sombre de ton Mac."), el("div", { class: "actions" }, selecteurMode(), selecteurTeinte())),
    reglageNotifications(),
    el("section", { class: "carte reglage" }, el("h2", {}, "Agenda (lecture)"),
      el("p", { class: "doux" }, "Google Agenda → ⚙ Paramètres → clique sur ton agenda à gauche → « Adresse secrète au format iCal ». Copie-la ici."),
      formLien, etatLien),
    el("section", { class: "carte reglage" }, el("h2", {}, "Agenda (ajout de rendez-vous)"),
      el("p", { class: "doux" }, "L'action rapide peut créer un rendez-vous par ton connecteur Google Agenda, toujours après ton clic sur « Ajouter ». Cette fonction n'a pas encore été testée avec toi : fais un premier essai ensemble, puis active-la."),
      el("label", { style: "display:flex;gap:8px;align-items:center" }, ecriture, "J'ai testé l'ajout avec Claude : activer l'ajout direct à l'agenda")),
    el("section", { class: "carte reglage" }, el("h2", {}, "Où sont mes données ?"),
      el("p", { class: "doux" }, "Réglages et images : ~/.dashboard-claude · Tâches : ~/todo/taches.md · Conversations : celles de Claude Code (~/.claude/projects). Rien ne sort de ton Mac, à part tes échanges avec Claude et la lecture de ton agenda Google."))));
}
