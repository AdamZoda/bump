@echo off
title Installateur Discord Bumper
echo ==================================================
echo   INSTALLATION DES DEPENDANCES DISCORD BUMPER
echo ==================================================
echo.

:: 1. Verifier si Python est installe
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python n'est pas detecte sur votre systeme.
    echo [i] Telechargement et installation automatique de Python en cours...
    
    :: Utiliser PowerShell pour telecharger l'installateur Python
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.5/python-3.11.5-amd64.exe' -OutFile 'python_installer.exe'"
    
    if exist python_installer.exe (
        echo [i] Lancement de l'installation de Python (Veuillez autoriser l'installation si demande)...
        :: Installer Python de maniere silencieuse pour l'utilisateur actuel et ajouter au PATH
        python_installer.exe /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
        del python_installer.exe
        echo [OK] Python a ete installe. Veuillez relancer ce script pour finaliser.
        pause
        exit
    ) else (
        echo [X] Erreur lors du telechargement de Python. Veuillez l'installer manuellement sur https://python.org
        pause
        exit
    )
)

echo [OK] Python est detecte sur votre systeme.
echo [i] Installation/Mise a jour des dependances necessaires (pyautogui, pywin32, pyperclip, Pillow)...
echo.

:: 2. Installer les packages via pip
python -m pip install --upgrade pip
python -m pip install pyautogui pywin32 pyperclip Pillow

if %errorlevel% neq 0 (
    echo [X] Une erreur est survenue lors de l'installation des packages Python.
    pause
    exit
)

echo.
echo [OK] Toutes les dependances ont ete installees avec succes !
echo.

:: 3. Generer le lanceur bat
echo @echo off > lanceur.bat
echo cd /d "%%~dp0" >> lanceur.bat
echo start pythonw discord_bumper_gui.py >> lanceur.bat
echo exit >> lanceur.bat

echo [OK] Le fichier 'lanceur.bat' a ete cree dans le dossier du projet.
echo.
echo ==================================================
echo   INSTALLATION TERMINEE AVEC SUCCES !
echo   Vous pouvez lancer l'application avec lanceur.bat
echo ==================================================
echo.
pause
