"""Lien court /local/ pour la capture mobile (empreinte / photo)."""
import socket
from pathlib import Path

from django.conf import settings
from django.core.cache import cache

CACHE_KEY_TOKEN = 'mariage:capture_mobile:local_token'


def detecter_ip_lan():
    """Adresse IPv4 locale du PC sur le réseau Wi‑Fi / LAN."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.6)
            sock.connect(('8.8.8.8', 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith('127.'):
                return ip
    except OSError:
        pass
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith('127.'):
                return ip
    except OSError:
        pass
    return None


def port_capture():
    return int(getattr(settings, 'CAPTURE_MOBILE_PORT', 8000))


def lire_url_tunnel():
    """URL publique (tunnel) lue depuis settings ou tunnel_url.txt."""
    custom = getattr(settings, 'CAPTURE_MOBILE_TUNNEL_URL', '').strip()
    if custom:
        return custom.rstrip('/')
    path = Path(settings.BASE_DIR) / 'tunnel_url.txt'
    if path.is_file():
        texte = path.read_text(encoding='utf-8').strip()
        if texte and 'api.trycloudflare.com' not in texte:
            return texte.rstrip('/')
    return None


def base_url_reseau_local(request=None):
    """
    URL de base accessible depuis le téléphone sur le même Wi‑Fi.
    CAPTURE_MOBILE_SHORT_BASE_URL :
      - vide ou 'auto' → IP LAN détectée automatiquement
      - sinon → URL fixe (ex. http://192.168.1.167:8000)
    """
    custom = getattr(settings, 'CAPTURE_MOBILE_SHORT_BASE_URL', '').strip()
    if custom and custom.lower() not in ('auto', ''):
        return custom.rstrip('/')

    ip = detecter_ip_lan()
    port = port_capture()
    if ip:
        return f'http://{ip}:{port}'

    if request is not None:
        return request.build_absolute_uri('/').rstrip('/')

    return f'http://127.0.0.1:{port}'


def base_url_capture_phone(request=None):
    """Priorité : tunnel Internet, sinon IP locale."""
    tunnel = lire_url_tunnel()
    if tunnel:
        return tunnel
    return base_url_reseau_local(request)


def duree_cache_secondes():
    return int(getattr(settings, 'CAPTURE_MOBILE_EXPIRE_MINUTES', 15)) * 60


def enregistrer_session_locale(token):
    """Mémorise le token de la dernière session créée au guichet."""
    cache.set(CACHE_KEY_TOKEN, token, timeout=duree_cache_secondes())


def resoudre_token_local():
    return cache.get(CACHE_KEY_TOKEN)


def url_capture_courte(request=None):
    """URL à ouvrir sur le téléphone."""
    return base_url_capture_phone(request) + '/local/'


def url_capture_directe(token, request=None):
    """Lien direct vers la page de capture (fiable avec tunnel)."""
    return f"{base_url_capture_phone(request)}/capture/{token}/"


def infos_reseau_capture(request=None):
    """Métadonnées affichées au guichet pour guider l'opérateur."""
    tunnel = lire_url_tunnel()
    ip = detecter_ip_lan()
    mode = 'tunnel' if tunnel else 'lan'
    return {
        'lan_ip': ip,
        'mode': mode,
        'tunnel_actif': bool(tunnel),
        'capture_url_short': url_capture_courte(request),
        'capture_url_lan': base_url_reseau_local(request) + '/local/',
        'capture_url_tunnel': (tunnel + '/local/') if tunnel else None,
        'port': port_capture(),
        'runserver_hint': f'python manage.py runserver 0.0.0.0:{port_capture()}',
        'tunnel_hint': 'Lancez demarrer_tunnel.bat si le Wi-Fi local bloque le téléphone.',
    }
