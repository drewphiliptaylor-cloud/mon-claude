"""Quota de l'abonnement : pourcentages lus dans le tampon écrit par la status line de Claude Code.

`~/.claude/statusline.py` écrit `~/.dashboard-claude/quota.json` à chaque rafraîchissement
(quand une session Claude Code est ouverte dans un terminal). Le mode SDK, lui, ne donne
que l'état et l'heure de remise à zéro : sans terminal, on interroge `/usage` (voir plus bas).
"""
import json
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PERIME = 6 * 3600  # au-delà, la valeur ne dit plus rien du présent


def _fenetre(d) -> Optional[dict]:
    if not isinstance(d, dict):
        return None
    p, r = d.get("used_percentage"), d.get("resets_at")
    if not isinstance(p, (int, float)) or not 0 <= p <= 100:
        return None
    sortie = {"pourcentage": round(float(p))}
    if isinstance(r, (int, float)) and r > 0:
        sortie["reinit"] = int(r)
    return sortie


def lire(chemin: Path, maintenant: Optional[float] = None) -> Optional[dict]:
    maintenant = maintenant or time.time()
    try:
        d = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    vu = d.get("vu_le")
    if not isinstance(vu, (int, float)) or maintenant - vu > PERIME:
        return None
    h5, d7 = _fenetre(d.get("five_hour")), _fenetre(d.get("seven_day"))
    if h5 and h5.get("reinit") and h5["reinit"] < maintenant:
        h5 = {"pourcentage": 0}  # la fenêtre de 5 h est déjà repartie à zéro
    if not h5 and not d7:
        return None
    return {"cinq_heures": h5, "sept_jours": d7, "vu_le": int(vu)}


# ---------- Sans terminal : commande /usage de Claude Code ----------
# `/usage` est une commande locale de Claude Code : elle ne consomme aucun quota (coût 0, ~1 s)
# et renvoie un texte du genre :
#   Current session: 42% used · resets Nov 13 at 1:50pm (Europe/Paris)
#   Current week (all models): 31% used · resets Nov 14 at 10pm (Europe/Paris)
# ponytail: on lit un texte destiné aux humains (anglais) ; si Claude Code change sa formulation,
# l'analyse renvoie None et le widget retombe sur l'état seul (jamais un faux chiffre).
# Chemin d'upgrade : un champ « utilization » rempli dans RateLimitEvent du SDK, à lire directement.
_LIGNE = re.compile(r"^\s*Current (session|week \(all models\))\s*:\s*(\d{1,3})% used"
                    r"(?:\s*·\s*resets (.+?)\s*(?:\(([^)]+)\))?)?\s*$", re.MULTILINE)
_MOIS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_REINIT = re.compile(r"^([A-Za-z]{3})[a-z]*\s+(\d{1,2})(?:,?\s+(\d{4}))?\s+at\s+(\d{1,2})(?::(\d{2}))?\s*([ap]m)$", re.IGNORECASE)


def _reinit(texte: str, fuseau: Optional[str], maintenant: float) -> Optional[int]:
    m = _REINIT.match(texte.strip())
    if not m or m.group(1).lower()[:3] not in _MOIS:
        return None
    try:
        tz = ZoneInfo(fuseau) if fuseau else None
    except (ZoneInfoNotFoundError, ValueError):
        tz = None
    h = int(m.group(4)) % 12 + (12 if m.group(6).lower() == "pm" else 0)
    mois, jour, minute = _MOIS[m.group(1).lower()[:3]], int(m.group(2)), int(m.group(5) or 0)
    annee = int(m.group(3)) if m.group(3) else datetime.fromtimestamp(maintenant, tz).year
    try:
        d = datetime(annee, mois, jour, h, minute, tzinfo=tz)
        if not m.group(3) and d.timestamp() < maintenant - 86400:  # « Jan 2 » vu le 30 décembre : l'an prochain
            d = d.replace(year=annee + 1)
    except ValueError:
        return None
    return int(d.timestamp())


def analyser_usage(texte: str, maintenant: Optional[float] = None) -> Optional[dict]:
    """Texte de `/usage` → même forme que `lire()`. None si rien de reconnaissable."""
    maintenant = maintenant or time.time()
    fenetres = {}
    for genre, pc, reinit, fuseau in _LIGNE.findall(texte or ""):
        p = int(pc)
        if not 0 <= p <= 100:
            continue
        f = {"pourcentage": p}
        r = _reinit(reinit, fuseau, maintenant) if reinit else None
        if r:
            f["reinit"] = r
        fenetres["cinq_heures" if genre == "session" else "sept_jours"] = f
    if not fenetres:
        return None
    return {"cinq_heures": fenetres.get("cinq_heures"), "sept_jours": fenetres.get("sept_jours"), "vu_le": int(maintenant)}


async def interroger(cwd: str) -> Optional[str]:
    """Lance `/usage` dans Claude Code (sans réglages, sans trace dans l'historique). Texte brut ou None."""
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
    options = ClaudeAgentOptions(cwd=cwd, cli_path=shutil.which("claude"), setting_sources=[], max_turns=1,
                                 extra_args={"no-session-persistence": None})
    texte = None
    async for m in query(prompt="/usage", options=options):
        if isinstance(m, ResultMessage) and not m.is_error:
            texte = m.result
    return texte
