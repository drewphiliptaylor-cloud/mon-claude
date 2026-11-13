// Dictée : le micro enregistre en WAV 16 kHz mono dans le navigateur, le serveur transcrit avec whisper (local).
import { api, el, ic, toast } from "./outils.js";

const FREQ = 16000;
let etatServeur = null;
async function disponible() {
  if (!etatServeur) {
    try { etatServeur = await api("/api/dictee"); } catch (e) { etatServeur = { disponible: false, raison: e.message }; }
  }
  return etatServeur;
}

// ponytail: ScriptProcessorNode (ancien mais disponible partout) au lieu d'un AudioWorklet.
// Plafond : traitement sur le fil principal, sans conséquence pour quelques minutes de voix.
// Upgrade : AudioWorklet dans un fichier séparé si Safari/Chrome retirent ScriptProcessor.
class Enregistreur {
  async demarrer() {
    this.flux = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (this.ctx.state === "suspended") await this.ctx.resume();  // Safari peut démarrer le contexte en pause
    this.source = this.ctx.createMediaStreamSource(this.flux);
    this.proc = this.ctx.createScriptProcessor(4096, 1, 1);
    this.morceaux = [];
    this.proc.onaudioprocess = e => this.morceaux.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    this.source.connect(this.proc); this.proc.connect(this.ctx.destination);
  }
  async arreter() {
    this.proc.disconnect(); this.source.disconnect();
    this.flux.getTracks().forEach(t => t.stop());
    const freqOrigine = this.ctx.sampleRate;
    await this.ctx.close();
    return encoderWav(reechantillonner(fusionner(this.morceaux), freqOrigine, FREQ), FREQ);
  }
}

function fusionner(morceaux) {
  const total = morceaux.reduce((n, m) => n + m.length, 0), sortie = new Float32Array(total);
  let pos = 0; for (const m of morceaux) { sortie.set(m, pos); pos += m.length; }
  return sortie;
}
function reechantillonner(donnees, de, vers) {
  if (de === vers) return donnees;
  const ratio = de / vers, n = Math.floor(donnees.length / ratio), sortie = new Float32Array(n);
  for (let i = 0; i < n; i++) {  // moyenne sur la fenêtre : évite le repliement des aigus
    const a = Math.floor(i * ratio), b = Math.min(Math.floor((i + 1) * ratio), donnees.length);
    let s = 0; for (let j = a; j < b; j++) s += donnees[j];
    sortie[i] = s / Math.max(1, b - a);
  }
  return sortie;
}
function encoderWav(echantillons, freq) {
  const tampon = new ArrayBuffer(44 + echantillons.length * 2), v = new DataView(tampon);
  const ecrire = (pos, txt) => { for (let i = 0; i < txt.length; i++) v.setUint8(pos + i, txt.charCodeAt(i)); };
  ecrire(0, "RIFF"); v.setUint32(4, 36 + echantillons.length * 2, true); ecrire(8, "WAVE");
  ecrire(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, freq, true); v.setUint32(28, freq * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  ecrire(36, "data"); v.setUint32(40, echantillons.length * 2, true);
  for (let i = 0; i < echantillons.length; i++) {
    const s = Math.max(-1, Math.min(1, echantillons[i]));
    v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([tampon], { type: "audio/wav" });
}

function inserer(zone, texte) {
  const debut = zone.selectionStart ?? zone.value.length, fin = zone.selectionEnd ?? zone.value.length;
  const avant = zone.value.slice(0, debut), apres = zone.value.slice(fin);
  const ajout = (avant && !/\s$/.test(avant) ? " " : "") + texte;
  zone.value = avant + ajout + apres;
  const pos = (avant + ajout).length;
  zone.focus(); zone.setSelectionRange(pos, pos);
  zone.dispatchEvent(new Event("input"));
}

// Bouton micro branché sur une zone de saisie (input ou textarea).
export function boutonMicro(zone) {
  const b = el("button", { class: "rond micro", type: "button", "aria-label": "Dicter", title: "Dicter (clic pour commencer, clic pour arrêter)", "aria-pressed": "false" }, ic("micro"));
  let enr = null, occupe = false;
  disponible().then(e => { if (!e.disponible) { b.disabled = true; b.classList.add("desactive"); b.title = "Dictée indisponible : " + e.raison; } });
  b.addEventListener("click", async () => {
    if (occupe) return;
    if (!enr) {
      try { enr = new Enregistreur(); await enr.demarrer(); }
      catch (e) {
        enr = null;
        toast(e.name === "NotAllowedError" ? "Micro refusé : autorise-le pour ce site dans les réglages du navigateur." : "Micro indisponible : " + e.message);
        return;
      }
      b.classList.add("enregistre"); b.setAttribute("aria-pressed", "true"); b.setAttribute("aria-label", "Arrêter la dictée");
      return;
    }
    occupe = true;
    b.classList.remove("enregistre"); b.classList.add("transcrit"); b.setAttribute("aria-pressed", "false"); b.setAttribute("aria-label", "Transcription en cours");
    try {
      const wav = await enr.arreter();
      const r = await api("/api/dictee", { methode: "POST", brut: wav });
      if (r.texte) inserer(zone, r.texte); else toast("Je n'ai rien entendu.");
    } catch (e) { toast("Dictée : " + e.message); }
    finally { enr = null; occupe = false; b.classList.remove("transcrit"); b.setAttribute("aria-label", "Dicter"); }
  });
  return b;
}
