"""Lance un tunnel Cloudflare gratuit et enregistre l'URL dans tunnel_url.txt."""
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / 'tunnel_url.txt'


def main():
    try:
        proc = subprocess.Popen(
            ['cloudflared', 'tunnel', '--url', 'http://127.0.0.1:8000'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        print('cloudflared introuvable.')
        print('Installez-le : winget install Cloudflare.cloudflared')
        sys.exit(1)

    print('Tunnel en cours… (laissez cette fenêtre ouverte)')
    print('Django doit tourner dans un autre terminal : runserver 0.0.0.0:8000')
    print('-' * 50)

    for line in proc.stdout:
        print(line, end='')
            match = re.search(r'https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com', line)
        if match:
            url = match.group(0).rstrip('/')
            OUT.write_text(url, encoding='utf-8')
            print()
            print('=' * 50)
            print('URL enregistrée pour le téléphone :')
            print(f'  {url}/local/')
            print('=' * 50)
            print('Sur le guichet : cliquez à nouveau « Capturer depuis le téléphone »')
            print()

    proc.wait()


if __name__ == '__main__':
    main()
