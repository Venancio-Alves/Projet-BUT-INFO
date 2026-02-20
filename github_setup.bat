@echo off
chcp 65001 >nul
cls

echo.
echo =====================================
echo 🚀 GITHUB SETUP - MedicSearch
echo =====================================
echo.

cd /d "C:\Users\thugg\OneDrive\Documents\semestre 5\SAE\sae1.1"

REM Vérifier que git init a déjà été fait
if exist .git (
    echo ✅ Git repo existe déjà
) else (
    echo 🔧 Initialisation git...
    git init
)

echo.
echo 📋 Configuration git...
git config user.name "MedicSearch"
git config user.email "contact@medicsearch.local"

echo.
echo 📁 Ajout des fichiers...
git add .

echo.
echo 📝 Premier commit...
git commit -m "Initial commit - MedicSearch v1.0"

echo.
echo ✅ SETUP TERMINÉ!
echo.
echo 📌 PROCHAINES ÉTAPES:
echo.
echo 1. Va sur: https://github.com/new
echo 2. Crée un repo: "medicsearch"
echo 3. Reviens et lance: github_push.bat
echo.
echo =====================================
pause
