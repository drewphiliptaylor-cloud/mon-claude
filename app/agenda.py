"""Lecture de l'agenda par le lien iCal privé de Google Agenda (aucun quota Claude consommé).

L'écriture (ajout d'un rendez-vous) passe par Claude et son connecteur Google Agenda :
voir app/rapide.py.
"""
import time
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
import icalendar
import recurring_ical_events

TAILLE_MAX = 5 * 1024 * 1024
DELAI = 10.0
DUREE_CACHE = 600  # 10 min
FUSEAU = ZoneInfo("Europe/Paris")
_cache: dict = {}


class AgendaErreur(Exception):
    """Message lisible par l'utilisateur."""


def verifier_url(url: str) -> str:
    url = (url or "").strip()
    p = urlparse(url)
    if p.scheme != "https" or not p.netloc:
        raise AgendaErreur("Le lien doit commencer par https://.")
    if "cid=" in p.query and not p.path.endswith(".ics"):
        raise AgendaErreur("Ce lien est un lien de partage. Il faut « l'adresse secrète au format iCal », "
                           "qui se termine par .ics (Google Agenda → Paramètres → ton agenda).")
    return url


def telecharger(url: str) -> bytes:
    url = verifier_url(url)
    try:
        with httpx.Client(timeout=DELAI, follow_redirects=True) as c, c.stream("GET", url) as r:
            if r.status_code != 200:
                raise AgendaErreur(f"Google Agenda a répondu {r.status_code}. Vérifie le lien.")
            morceaux, total = [], 0
            for m in r.iter_bytes():
                total += len(m)
                if total > TAILLE_MAX:
                    raise AgendaErreur("L'agenda est trop volumineux (plus de 5 Mo).")
                morceaux.append(m)
            return b"".join(morceaux)
    except httpx.HTTPError as e:
        raise AgendaErreur(f"Agenda injoignable : {type(e).__name__}.") from e


def analyser(ics: bytes, debut: date, jours: int = 3, fuseau: ZoneInfo = FUSEAU) -> list:
    try:
        cal = icalendar.Calendar.from_ical(ics)
    except ValueError as e:
        raise AgendaErreur("Le contenu reçu n'est pas un agenda iCal.") from e
    a = datetime.combine(debut, datetime.min.time(), fuseau)
    b = a + timedelta(days=jours)
    sortie = []
    for ev in recurring_ical_events.of(cal).between(a, b):
        d, f = ev.get("DTSTART").dt, ev.get("DTEND").dt if ev.get("DTEND") else None
        journee = not isinstance(d, datetime)
        if journee:
            d_loc = datetime.combine(d, datetime.min.time(), fuseau)
            f_loc = datetime.combine(f, datetime.min.time(), fuseau) if f else d_loc + timedelta(days=1)
        else:
            d_loc = (d if d.tzinfo else d.replace(tzinfo=fuseau)).astimezone(fuseau)
            f_loc = (f if f and f.tzinfo else (f.replace(tzinfo=fuseau) if f else d_loc)).astimezone(fuseau)
        titre, lieu = str(ev.get("SUMMARY", "(sans titre)")), str(ev.get("LOCATION", ""))
        if journee:
            # un événement sur plusieurs jours apparaît chaque jour de la fenêtre qu'il couvre
            jour = max(d_loc, a)
            while jour < min(f_loc, b):
                sortie.append({"titre": titre, "lieu": lieu, "debut": jour.isoformat(),
                               "fin": (jour + timedelta(days=1)).isoformat(), "journee": True})
                jour += timedelta(days=1)
        else:
            sortie.append({"titre": titre, "lieu": lieu, "debut": d_loc.isoformat(), "fin": f_loc.isoformat(), "journee": False})
    sortie.sort(key=lambda e: (e["debut"], not e["journee"]))
    return sortie


def evenements(url: str, debut: Optional[date] = None, jours: int = 3) -> list:
    debut = debut or datetime.now(FUSEAU).date()
    maintenant = time.time()
    en_cache = _cache.get(url)
    if en_cache and maintenant - en_cache[0] < DUREE_CACHE:
        ics = en_cache[1]
    else:
        ics = telecharger(url)
        _cache[url] = (maintenant, ics)
    return analyser(ics, debut, jours)


def vider_cache() -> None:
    _cache.clear()
