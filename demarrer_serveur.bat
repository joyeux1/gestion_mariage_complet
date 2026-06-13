@echo off
REM Demarre Django avec Python 3.12 + reconnaissance faciale (face_recognition)
cd /d "%~dp0"
call environnement_virtuel\Scripts\activate.bat
echo Python utilise :
python --version
python -c "import face_recognition; print('face_recognition : OK')" 2>nul || (
    echo.
    echo [ERREUR] face_recognition manquant. Executez :
    echo   pip install -r requirements.txt
    echo   pip install face-recognition==1.3.0 --no-deps
    pause
    exit /b 1
)
python manage.py runserver
pause
