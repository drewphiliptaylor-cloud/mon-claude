// Notifications du Mac : prévenir quand Claude a fini de répondre ou attend ton accord,
// seulement si tu regardes ailleurs (autre onglet, autre appli, fenêtre réduite).
// Le choix est gardé dans ce navigateur : l'autorisation de notifier lui appartient aussi.
// Limite : la page doit rester ouverte (fermer la page arrête la conversation en cours).
import { el, toast, lire, ecrire } from "./outils.js";

const CLE = "notifications";
const possible = () => "Notification" in window;
export const actives = () => possible() && Notification.permission === "granted" && lire(CLE, false) === true;

// force : pour l'essai depuis les réglages, même quand la page est au premier plan
export function prevenir(titre, corps, lien, force = false) {
  if (!actives() || (!force && document.visibilityState === "visible" && document.hasFocus())) return;
  try {
    const n = new Notification(titre, { body: (corps || "").replace(/\s+/g, " ").trim().slice(0, 140), icon: "/web/icone-192.png", tag: lien || titre });
    n.onclick = () => { window.focus(); if (lien) location.hash = lien; n.close(); };
  } catch { /* navigateur qui refuse les notifications hors service worker : on reste silencieux */ }
}

export function reglageNotifications() {
  const etat = el("p", { class: "doux", role: "status" });
  const bascule = el("input", { type: "checkbox", id: "notif" });
  const essai = el("button", { class: "bouton", type: "button" }, "Essayer");
  function maj() {
    if (!possible()) { etat.textContent = "Ce navigateur ne sait pas afficher de notifications."; bascule.disabled = essai.disabled = true; return; }
    const p = Notification.permission;
    bascule.checked = actives();
    essai.disabled = !actives();
    etat.textContent = p === "denied"
      ? "Notifications bloquées pour cette page. Pour les débloquer : clique sur l'icône à gauche de l'adresse → Notifications → Autoriser, puis recharge."
      : actives() ? "✓ Activées. Si rien ne s'affiche à l'essai : Réglages Système → Notifications → ton navigateur → Autoriser."
      : "Désactivées.";
  }
  bascule.addEventListener("change", async () => {
    if (bascule.checked && Notification.permission !== "granted") {
      try { await Notification.requestPermission(); } catch { /* refus */ }
    }
    ecrire(CLE, bascule.checked && Notification.permission === "granted");
    maj();
    if (bascule.checked && !actives()) toast("Le navigateur n'a pas donné l'autorisation.");
  });
  essai.addEventListener("click", () => prevenir("Mon Claude", "Essai : c'est ici que tu seras prévenu.", null, true));
  maj();
  return el("section", { class: "carte reglage" }, el("h2", {}, "Notifications"),
    el("p", { class: "doux" }, "Te prévenir quand Claude a fini de répondre ou attend ton accord, si tu es sur une autre fenêtre. La page Mon Claude doit rester ouverte."),
    el("div", { class: "actions", style: "display:flex;gap:12px;align-items:center;flex-wrap:wrap" },
      el("label", { style: "display:flex;gap:8px;align-items:center" }, bascule, "Me prévenir"), essai),
    etat);
}
