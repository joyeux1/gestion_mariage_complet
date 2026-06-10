@echo off
cd /d "%~dp0"
echo.
echo === Tunnel Internet pour le telephone ===
echo 1. Terminal 1 : python manage.py runserver 0.0.0.0:8000
echo 2. Terminal 2 : ce script (ici)
echo.
where cloudflared >nul 2>&1
if errorlevel 1 (
    echo Installation de cloudflared...
    winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
)
python scripts\tunnel_cloudflare.py
pause
