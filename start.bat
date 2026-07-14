@echo off
title Bumper Multi-Bot - Demarrage
cd /d "%~dp0"

:: Verifier si Python est installe
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python non detecte. Lancement de l'installateur...
    call install.bat
    exit
)

:: Verifier si les dependances sont installees
python -c "import pyautogui, win32gui, PIL" >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Dependances manquantes. Lancement de l'installateur...
    call install.bat
    exit
)

:: Lancer l'application sans fenetre noire
start pythonw discord_bumper_gui.py
exit
