@echo off
chcp 65001 >nul
cls

echo.
echo ================================
echo 📊 STATUT DOCKER
echo ================================
echo.

echo 📦 Conteneurs en cours d'exécution:
docker ps

echo.
echo ================================
echo 📋 Les images disponibles:
docker images

echo.
echo ================================
pause
