from datetime import date

import httpx
import pytest
from app import agenda

ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//FR
BEGIN:VEVENT
UID:1
DTSTART;TZID=Europe/Paris:20261112T140000
DTEND;TZID=Europe/Paris:20261112T160000
SUMMARY:Prototype maquette carton
LOCATION:Atelier
END:VEVENT
BEGIN:VEVENT
UID:2
DTSTART:20261113T090000Z
DTEND:20261113T100000Z
SUMMARY:Revue des devis
END:VEVENT
BEGIN:VEVENT
UID:3
DTSTART;VALUE=DATE:20261114
DTEND;VALUE=DATE:20261115
SUMMARY:Salon
END:VEVENT
BEGIN:VEVENT
UID:4
DTSTART;TZID=Europe/Paris:20261105T090000
DTEND;TZID=Europe/Paris:20261105T093000
RRULE:FREQ=WEEKLY
SUMMARY:Point d'equipe
END:VEVENT
BEGIN:VEVENT
UID:5
DTSTART;TZID=Europe/Paris:20261120T090000
DTEND;TZID=Europe/Paris:20261120T093000
SUMMARY:Hors fenetre
END:VEVENT
END:VCALENDAR
"""


def test_evenements_de_la_fenetre_tries_avec_recurrence():
    ev = agenda.analyser(ICS, date(2026, 11, 12), jours=3)
    assert [e["titre"] for e in ev] == ["Point d'equipe", "Prototype maquette carton", "Revue des devis", "Salon"], \
        "il faut l'événement récurrent du 12, les trois événements de la fenêtre, et rien hors fenêtre"


def test_heure_utc_convertie_en_heure_de_paris():
    revue = [e for e in agenda.analyser(ICS, date(2026, 11, 12)) if e["titre"] == "Revue des devis"][0]
    assert revue["debut"].startswith("2026-11-13T10:00:00+01:00"), revue["debut"]


def test_journee_entiere_reperee():
    salon = [e for e in agenda.analyser(ICS, date(2026, 11, 12)) if e["titre"] == "Salon"][0]
    assert salon["journee"] is True


def test_evenement_sur_plusieurs_jours_affiche_chaque_jour_de_la_fenetre():
    ics = ICS.replace(b"DTSTART;VALUE=DATE:20261114\nDTEND;VALUE=DATE:20261115", b"DTSTART;VALUE=DATE:20261111\nDTEND;VALUE=DATE:20261114")
    salon = [e for e in agenda.analyser(ics, date(2026, 11, 12)) if e["titre"] == "Salon"]
    assert [e["debut"][:10] for e in salon] == ["2026-11-12", "2026-11-13"], \
        "commencé avant la fenêtre et fini le 14 au matin : visible le 12 et le 13"


def test_contenu_non_ical_refuse():
    with pytest.raises(agenda.AgendaErreur):
        agenda.analyser(b"<html>connexion requise</html>", date(2026, 11, 12))


@pytest.mark.parametrize("url", ["http://calendar.google.com/x.ics", "file:///etc/passwd", "", "javascript:alert(1)"])
def test_liens_non_https_refuses(url):
    with pytest.raises(agenda.AgendaErreur):
        agenda.verifier_url(url)


def test_lien_de_partage_cid_explique():
    with pytest.raises(agenda.AgendaErreur, match="adresse secrète"):
        agenda.verifier_url("https://calendar.google.com/calendar/u/0?cid=abc")


def test_reponse_trop_volumineuse_refusee(monkeypatch):
    def faux(requete):
        return httpx.Response(200, content=b"x" * (agenda.TAILLE_MAX + 10))
    transport = httpx.MockTransport(faux)
    vrai_client = httpx.Client
    monkeypatch.setattr(agenda.httpx, "Client", lambda **kw: vrai_client(transport=transport, **kw))
    with pytest.raises(agenda.AgendaErreur, match="volumineux"):
        agenda.telecharger("https://exemple.test/a.ics")


def test_erreur_http_lisible(monkeypatch):
    transport = httpx.MockTransport(lambda r: httpx.Response(404))
    vrai_client = httpx.Client
    monkeypatch.setattr(agenda.httpx, "Client", lambda **kw: vrai_client(transport=transport, **kw))
    with pytest.raises(agenda.AgendaErreur, match="404"):
        agenda.telecharger("https://exemple.test/a.ics")
