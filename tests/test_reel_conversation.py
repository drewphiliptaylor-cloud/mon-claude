"""Bout en bout : vrai serveur, vrai Claude Code. Consomme du quota : `pytest -m reel`."""
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import websockets

RACINE = Path(__file__).resolve().parent.parent


def _port_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def serveur(tmp_path):
    port = _port_libre()
    env = {**os.environ, "DASHBOARD_PORT": str(port), "DASHBOARD_DATA": str(tmp_path / "data"),
           "DASHBOARD_DOSSIER": str(tmp_path), "DASHBOARD_TACHES": str(tmp_path / "taches.md")}
    p = subprocess.Popen([sys.executable, "-m", "app.serveur"], cwd=RACINE, env=env)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield port, tmp_path
    p.terminate()
    p.wait(5)


async def _echange(port, texte, repondre_accord=None, delai=180):
    evs = []
    async with websockets.connect(f"ws://127.0.0.1:{port}/ws/conversation",
                                  additional_headers={"Origin": f"http://127.0.0.1:{port}"}) as ws:
        await ws.send(json.dumps({"type": "message", "texte": texte}))
        async with asyncio.timeout(delai):
            while True:
                ev = json.loads(await ws.recv())
                evs.append(ev)
                if ev["type"] == "accord" and repondre_accord is not None:
                    await ws.send(json.dumps({"type": "accord", "id": ev["id"], "ok": repondre_accord}))
                if ev["type"] in ("fin", "erreur"):
                    return evs


@pytest.mark.reel
async def test_reel_reponse_au_fil_de_l_eau(serveur):
    port, _ = serveur
    evs = await _echange(port, "Réponds seulement le mot : bonjour")
    types = [e["type"] for e in evs]
    assert "session" in types and "fin" in types, types
    texte = "".join(e["delta"] for e in evs if e["type"] == "texte")
    assert "bonjour" in texte.lower(), texte


def _png_rouge(taille=16) -> bytes:
    import struct
    import zlib

    def bloc(genre, donnees):
        return struct.pack(">I", len(donnees)) + genre + donnees + struct.pack(">I", zlib.crc32(genre + donnees) & 0xFFFFFFFF)
    lignes = b"".join(b"\x00" + b"\xff\x00\x00" * taille for _ in range(taille))
    return (b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", struct.pack(">IIBBBBB", taille, taille, 8, 2, 0, 0, 0))
            + bloc(b"IDAT", zlib.compress(lignes)) + bloc(b"IEND", b""))


@pytest.mark.reel
async def test_reel_image_jointe_vue_par_claude(serveur):
    import httpx
    port, _ = serveur
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as c:
        r = await c.post("/api/images", files={"fichier": ("rouge.png", _png_rouge(), "image/png")})
    assert r.status_code == 200, r.text
    evs = []
    async with websockets.connect(f"ws://127.0.0.1:{port}/ws/conversation", additional_headers={"Origin": f"http://127.0.0.1:{port}"}) as ws:
        await ws.send(json.dumps({"type": "message", "texte": "De quelle couleur est cette image ? Réponds en un seul mot.", "images": [r.json()["id"]]}))
        async with asyncio.timeout(180):
            while True:
                ev = json.loads(await ws.recv())
                evs.append(ev)
                if ev["type"] in ("fin", "erreur"):
                    break
    texte = "".join(e["delta"] for e in evs if e["type"] == "texte").lower()
    assert "rouge" in texte, f"Claude doit voir l'image : {texte!r} {[e for e in evs if e['type'] == 'erreur']}"


@pytest.mark.reel
async def test_reel_interruption_puis_nouveau_message(serveur):
    port, _ = serveur
    async with websockets.connect(f"ws://127.0.0.1:{port}/ws/conversation", additional_headers={"Origin": f"http://127.0.0.1:{port}"}) as ws:
        await ws.send(json.dumps({"type": "message", "texte": "Écris un poème de 40 vers sur la mer, sans outil."}))
        async with asyncio.timeout(120):
            while json.loads(await ws.recv())["type"] != "texte":
                pass
            await ws.send(json.dumps({"type": "interrompre"}))
            while json.loads(await ws.recv())["type"] not in ("fin", "erreur"):
                pass
            await ws.send(json.dumps({"type": "message", "texte": "Réponds seulement : encore là"}))
            texte = ""
            while True:
                ev = json.loads(await ws.recv())
                if ev["type"] == "texte":
                    texte += ev["delta"]
                if ev["type"] in ("fin", "erreur"):
                    break
    assert "encore" in texte.lower(), f"la conversation doit continuer après une interruption : {texte!r}"


@pytest.mark.reel
async def test_reel_autorisation_refusee_par_l_utilisateur(serveur):
    port, dossier = serveur
    evs = await _echange(port, "Crée le fichier essai.txt dans le dossier courant avec la commande Bash `touch essai.txt`.",
                         repondre_accord=False)
    assert any(e["type"] == "accord" for e in evs), [e["type"] for e in evs]
    assert any(e["type"] == "accord_fini" and e["ok"] is False for e in evs)
    assert not (dossier / "essai.txt").exists(), "le fichier ne doit pas exister après un refus"
