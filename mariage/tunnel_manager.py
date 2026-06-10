"""Gestion du tunnel Cloudflare (cloudflared) pour capture mobile."""
import re
import subprocess
import sys
import threading

from django.conf import settings

_process = None
_lock = threading.Lock()
_ready = threading.Event()
_tunnel_url = None
_reader_started = False

URL_PATTERN = re.compile(r'https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com')


def _fichier_tunnel():
    return settings.BASE_DIR / 'tunnel_url.txt'


def _port_local():
    return int(getattr(settings, 'CAPTURE_MOBILE_PORT', 8000))


def lire_url_fichier():
    path = _fichier_tunnel()
    if path.is_file():
        texte = path.read_text(encoding='utf-8').strip()
        if texte:
            return texte.rstrip('/')
    return None


def processus_actif():
    global _process
    return _process is not None and _process.poll() is None


def _consommer_sortie(proc):
    """Lit la sortie cloudflared et enregistre l'URL publique."""
    global _tunnel_url
    try:
        for line in proc.stdout:
            if _tunnel_url:
                continue
            match = URL_PATTERN.search(line)
            if match:
                _tunnel_url = match.group(0).rstrip('/')
                _fichier_tunnel().write_text(_tunnel_url, encoding='utf-8')
                _ready.set()
    except Exception:
        pass


def _lancer_processus():
    global _process, _reader_started, _tunnel_url, _ready

    flags = 0
    if sys.platform == 'win32':
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

    _ready.clear()
    _tunnel_url = None
    _process = subprocess.Popen(
        ['cloudflared', 'tunnel', '--url', f'http://127.0.0.1:{_port_local()}'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=flags,
    )
    _reader_started = True
    threading.Thread(target=_consommer_sortie, args=(_process,), daemon=True).start()


def statut_tunnel():
    url = _tunnel_url or lire_url_fichier()
    actif = processus_actif()
    return {
        'ok': bool(url and actif),
        'url': url,
        'actif': actif,
        'local_sante': f'{url}/local/sante/' if url else None,
    }


def demarrer_tunnel(timeout=60):
    """Démarre cloudflared en arrière-plan si nécessaire."""
    global _process, _tunnel_url

    with _lock:
        if processus_actif():
            url = _tunnel_url or lire_url_fichier()
            if url:
                return {
                    'ok': True,
                    'url': url,
                    'deja_actif': True,
                    'local_url': f'{url}/local/',
                }

        if _process and _process.poll() is not None:
            _process = None

        try:
            _lancer_processus()
        except FileNotFoundError:
            return {
                'ok': False,
                'error': (
                    'cloudflared introuvable. Installez-le avec : '
                    'winget install Cloudflare.cloudflared'
                ),
            }
        except OSError as exc:
            return {'ok': False, 'error': str(exc)}

    if _ready.wait(timeout=timeout):
        url = _tunnel_url or lire_url_fichier()
        return {
            'ok': True,
            'url': url,
            'deja_actif': False,
            'local_url': f'{url}/local/' if url else None,
        }

    return {
        'ok': False,
        'error': 'Le tunnel met trop de temps à démarrer. Réessayez dans quelques secondes.',
    }
