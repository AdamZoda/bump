@echo off
title Bumper Multi-Bot - Build EXE
cd /d "%~dp0"
echo.
echo ============================================
echo   COMPILATION EN .EXE (PyInstaller)
echo ============================================
echo.

:: Verifier si PyInstaller est installe
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Installation de PyInstaller...
    pip install pyinstaller
)

:: Verifier si pyarmor est installe (obfuscation optionnelle)
:: pip install pyarmor

echo.
echo [*] Compilation en cours... (peut prendre 1-2 minutes)
echo.

:: Compilation en EXE monofichier avec icone personnalisee
pyinstaller ^
    --onefile ^
    --windowed ^
    --icon=logo-V2.png ^
    --name="BumperMultiBot" ^
    --add-data="logo-V2.png;." ^
    --hidden-import=win32gui ^
    --hidden-import=win32con ^
    --hidden-import=win32com ^
    --hidden-import=win32com.client ^
    --hidden-import=pywintypes ^
    --hidden-import=pyautogui ^
    --hidden-import=PIL ^
    --hidden-import=PIL.Image ^
    --hidden-import=PIL.ImageTk ^
    --hidden-import=pyperclip ^
    --clean ^
    discord_bumper_gui.py

if %errorlevel% neq 0 (
    echo.
    echo [ERREUR] La compilation a echoue.
    pause
    exit
)

echo.
echo ============================================
echo   SUCCES ! EXE cree dans le dossier dist\
echo ============================================
echo.
echo   Fichier a distribuer : dist\BumperMultiBot.exe
echo.
echo   Tu peux partager ce seul fichier .exe
echo   Le code source est compile et protege.
echo.

:: Copier l'exe a la racine du projet pour faciliter l'acces
if exist "dist\BumperMultiBot.exe" (
    copy "dist\BumperMultiBot.exe" "BumperMultiBot.exe" >nul
    echo   Copie dans le dossier courant : BumperMultiBot.exe
)

pause
