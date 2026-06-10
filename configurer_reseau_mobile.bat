@echo off
REM ============================================================
REM  A executer en tant qu'ADMINISTRATEUR (clic droit)
REM  Autorise le telephone a joindre Django sur le port 8000
REM ============================================================
cd /d "%~dp0"

echo.
echo [1/2] Reseau Wi-Fi en mode PRIVE (autorise les appareils du meme Wi-Fi)...
powershell -NoProfile -Command "Set-NetConnectionProfile -InterfaceAlias 'Wi-Fi' -NetworkCategory Private -ErrorAction SilentlyContinue"
if errorlevel 1 (
    echo    Impossible de changer le profil - continuez quand meme.
) else (
    echo    OK - Wi-Fi en mode Prive.
)

echo.
echo [2/2] Regle pare-feu Windows pour le port 8000...
netsh advfirewall firewall delete rule name="Gestion Mariage Django 8000" >nul 2>&1
netsh advfirewall firewall add rule name="Gestion Mariage Django 8000" dir=in action=allow protocol=TCP localport=8000 profile=private,domain enable=yes
if errorlevel 1 (
    echo    ERREUR - relancez ce fichier en Administrateur.
    pause
    exit /b 1
)
echo    OK - port 8000 ouvert sur reseau prive.

echo.
echo ============================================================
echo  Termine. Gardez runserver_lan.bat actif, puis sur le phone :
echo  http://VOTRE_IP:8000/local/
echo  (l'IP s'affiche apres « Capturer depuis le telephone »)
echo ============================================================
echo.
pause
