"""Frontières de confiance : qui peut parler au serveur, quels fichiers on accepte."""
from typing import Optional

TAILLE_MAX_IMAGE = 10 * 1024 * 1024  # 10 Mo
TAILLE_MAX_MESSAGE = 50_000          # caractères

# Signatures de début de fichier (« magic bytes ») : on ne se fie jamais au nom ni au type annoncé.
_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
)


def hotes_autorises(port: int) -> set:
    return {f"127.0.0.1:{port}", f"localhost:{port}"}


def origines_autorisees(port: int) -> set:
    return {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}


def requete_autorisee(host: Optional[str], origin: Optional[str], port: int) -> bool:
    """Refuse les requêtes venues d'un autre site (CSRF) ou d'un nom d'hôte piégé (DNS rebinding)."""
    if not host or host.lower() not in hotes_autorises(port):
        return False
    if origin is not None and origin.lower() not in origines_autorisees(port):
        return False
    return True


def type_image(donnees: bytes) -> Optional[tuple]:
    """Renvoie (type MIME, extension) si les octets sont une image acceptée, sinon None."""
    if not donnees or len(donnees) > TAILLE_MAX_IMAGE:
        return None
    for signature, mime, ext in _SIGNATURES:
        if donnees.startswith(signature):
            return mime, ext
    if len(donnees) >= 12 and donnees[:4] == b"RIFF" and donnees[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None
