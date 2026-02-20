@echo off
chcp 65001 >nul
cls

echo.
echo ================================
echo 🚀 DEMARRAGE DOCKER
echo ================================
echo.

REM Aller dans le dossier configuration
cd /d "Sources-20251202T134703Z-1-001\Sources\configuration"

REM Lancer docker-compose
echo 📦 Lancement des conteneurs Docker...
docker-compose up -d

echo.
echo ✅ Docker est lancé!
echo.
echo 📊 Conteneurs actifs:
docker ps

echo.
echo ================================
pause
