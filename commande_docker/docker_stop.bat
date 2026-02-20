@echo off
chcp 65001 >nul
cls

echo.
echo ================================
echo ⏹️  ARRÊT DOCKER
echo ================================
echo.

REM Aller dans le dossier configuration
cd /d "Sources-20251202T134703Z-1-001\Sources\configuration"

REM Arrêter docker-compose
echo 🛑 Arrêt des conteneurs Docker...
docker-compose down

echo.
echo ✅ Docker est arrêté!
echo.

echo ================================
pause
