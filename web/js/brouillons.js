// Brouillons : le message commencé reste là si on change de page ou recharge.
// ponytail: gardé dans ce navigateur (localStorage) ; plafond : pas partagé entre appareils ;
// upgrade : stocker côté serveur quand le dashboard sera utilisé depuis le téléphone.
import { lire, ecrire } from "./outils.js";

const PREFIXE = "brouillon:";
const IMAGE = /^[0-9a-f]{32}\.(png|jpg|gif|webp)$/;

export function lireBrouillon(zone) {
  const b = lire(PREFIXE + zone, null);
  if (!b || typeof b !== "object") return { texte: "", images: [] };
  const images = Array.isArray(b.images) ? b.images.filter(i => i && IMAGE.test(i.id || "")).map(i => ({ id: i.id, url: `/api/images/${i.id}`, nom: String(i.nom || "image") })) : [];
  return { texte: typeof b.texte === "string" ? b.texte : "", images };
}

// Écriture immédiate à chaque frappe (localStorage est synchrone et rapide) : rien ne se perd en changeant de page.
export function garderBrouillon(zone, texte, images = []) {
  if (!texte.trim() && !images.length) return effacerBrouillon(zone);
  ecrire(PREFIXE + zone, { texte, images: images.map(i => ({ id: i.id, nom: i.nom })), le: Date.now() });
}

export function effacerBrouillon(zone) {
  try { localStorage.removeItem(PREFIXE + zone); } catch { /* navigation privée */ }
}
