@echo off
chcp 65001 >nul
cls

echo.
echo =====================================
echo 📤 PUSH VERS GITHUB
echo =====================================
echo.

cd /d "C:\Users\thugg\OneDrive\Documents\semestre 5\SAE\sae1.1"

echo.
echo 📝 Entrez l'URL de votre repo GitHub:
echo Exemple: https://github.com/tonnom/medicsearch.git
echo.
set /p GITHUB_URL="URL: "

echo.
echo 🔗 Ajout du remote...
git remote add origin %GITHUB_URL%

echo.
echo 📤 Push vers GitHub...
git branch -M main
git push -u origin main

echo.
echo ✅ PUSH TERMINÉ!
echo.
echo 🎉 Votre projet est maintenant sur GitHub!
echo.
echo =====================================
pause
