// Petits outils partagés : appels API, création d'éléments, rendu Markdown sûr, dates.

export async function api(chemin, { methode = "GET", corps, brut } = {}) {
  const opts = { method: methode, headers: {} };
  if (brut) opts.body = brut;
  else if (corps !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(corps); }
  let r;
  try { r = await fetch(chemin, opts); }
  catch { throw new Error("Le serveur du dashboard ne répond pas. Est-il lancé ?"); }
  let data = null;
  try { data = await r.json(); } catch { /* réponse vide */ }
  if (!r.ok) throw Object.assign(new Error((data && (data.detail || data.erreur)) || `Erreur ${r.status}`), { statut: r.status });
  return data;
}

// el("div", {class:"x", onclick}, "texte", enfant…) — le texte passe TOUJOURS par textContent.
export function el(tag, attrs = {}, ...enfants) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (k === "class") n.className = v;
    else if (k === "style") n.setAttribute("style", v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const e of enfants.flat()) {
    if (e === null || e === undefined || e === false) continue;
    n.append(e instanceof Node ? e : document.createTextNode(String(e)));
  }
  return n;
}

export function ic(nom, cls = "ic") {
  const ns = "http://www.w3.org/2000/svg";
  const s = document.createElementNS(ns, "svg"); s.setAttribute("class", cls); s.setAttribute("aria-hidden", "true");
  const u = document.createElementNS(ns, "use"); u.setAttribute("href", `#i-${nom}`); s.appendChild(u);
  return s;
}

export function toast(message) {
  const t = el("div", { class: "toast", role: "status" }, message);
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}

export const lire = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } };
export const ecrire = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* navigation privée */ } };

// ---------- dates ----------
export const FUSEAU = "Europe/Paris";
export const auj = () => new Date();
export const memeJour = (a, b) => a.toDateString() === b.toDateString();
export function libJour(d) {
  const n = Math.round((new Date(d.getFullYear(), d.getMonth(), d.getDate()) - new Date(auj().getFullYear(), auj().getMonth(), auj().getDate())) / 864e5);
  if (n === 0) return "Aujourd'hui";
  if (n === 1) return "Demain";
  const t = d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: n > 6 ? "long" : undefined });
  return t[0].toUpperCase() + t.slice(1);
}
export const heure = d => d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
export function depuis(ms) {
  const s = (Date.now() - ms) / 1000;
  if (s < 60) return "à l'instant";
  if (s < 3600) return `il y a ${Math.round(s / 60)} min`;
  const d = new Date(ms);
  if (memeJour(d, auj())) return `aujourd'hui ${heure(d)}`;
  const hier = new Date(); hier.setDate(hier.getDate() - 1);
  if (memeJour(d, hier)) return `hier ${heure(d)}`;
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" }) + " " + heure(d);
}

// ---------- Markdown sûr ----------
// On échappe TOUT d'abord, puis on reconnaît un petit sous-ensemble. Aucun HTML venant de Claude n'est interprété.
const echapper = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
function enLigne(s) {
  const codes = [];
  s = s.replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_, t, u) => `<a href="${u}" target="_blank" rel="noopener noreferrer">${t}</a>`);
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[i]}</code>`);
}
export function markdown(source) {
  const lignes = echapper(source || "").split("\n");
  let html = "", liste = null, para = [], bloc = null;
  const finPara = () => { if (para.length) { html += `<p>${enLigne(para.join("<br>"))}</p>`; para = []; } };
  const finListe = () => { if (liste) { html += `</${liste}>`; liste = null; } };
  const cellules = l => l.trim().replace(/^\||\|$/g, "").split("|").map(c => enLigne(c.trim()));
  for (let i = 0; i < lignes.length; i++) {
    const l = lignes[i];
    // tableau : ligne | a | b | suivie d'une ligne de séparation |---|---|
    if (bloc === null && /^\s*\|.*\|\s*$/.test(l) && /^\s*\|[\s:|-]+\|\s*$/.test(lignes[i + 1] || "")) {
      finPara(); finListe();
      html += `<div class="tableau"><table><thead><tr>${cellules(l).map(c => `<th>${c}</th>`).join("")}</tr></thead><tbody>`;
      i += 2;
      while (i < lignes.length && /^\s*\|.*\|\s*$/.test(lignes[i])) { html += `<tr>${cellules(lignes[i]).map(c => `<td>${c}</td>`).join("")}</tr>`; i++; }
      html += "</tbody></table></div>"; i--;
      continue;
    }
    if (bloc !== null) {
      if (/^```/.test(l)) { html += `<pre><code>${bloc.join("\n")}</code></pre>`; bloc = null; } else bloc.push(l);
      continue;
    }
    if (/^```/.test(l)) { finPara(); finListe(); bloc = []; continue; }
    const t = l.match(/^(#{1,4})\s+(.*)$/);
    const ul = l.match(/^\s*[-*]\s+(.*)$/);
    const ol = l.match(/^\s*\d+[.)]\s+(.*)$/);
    if (t) { finPara(); finListe(); html += `<h${Math.min(t[1].length + 1, 4)}>${enLigne(t[2])}</h${Math.min(t[1].length + 1, 4)}>`; }
    else if (ul || ol) {
      finPara(); const genre = ul ? "ul" : "ol";
      if (liste !== genre) { finListe(); html += `<${genre}>`; liste = genre; }
      html += `<li>${enLigne((ul || ol)[1])}</li>`;
    }
    else if (!l.trim()) { finPara(); finListe(); }
    else { finListe(); para.push(l); }
  }
  if (bloc !== null) html += `<pre><code>${bloc.join("\n")}</code></pre>`;
  finPara(); finListe();
  return html;
}
