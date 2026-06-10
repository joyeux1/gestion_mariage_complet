@echo off
REM Serveur accessible depuis le telephone sur le meme Wi-Fi (ecoute sur toutes les interfaces)
cd /d "%~dp0"
echo.
echo  Demarrage du serveur pour le reseau local (0.0.0.0:8000)
echo  Sur le telephone, ouvrez l'URL courte affichee apres « Capturer depuis le telephone »
echo.
python manage.py runserver 0.0.0.0:8000
