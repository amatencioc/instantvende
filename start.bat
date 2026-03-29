@echo off
echo === InstantVende - Iniciando servicios ===

:: Crear carpeta de logs si no existe
if not exist "logs" mkdir logs

:: Instalar PM2 si no está instalado
where pm2 >nul 2>&1
if %errorlevel% neq 0 (
    echo Instalando PM2...
    npm install -g pm2
)

:: Iniciar o recargar todos los servicios
pm2 start ecosystem.config.js

echo.
echo === Estado de los servicios ===
pm2 status

echo.
echo === Comandos útiles ===
echo   pm2 logs              -- Ver logs en tiempo real
echo   pm2 logs instantvende-api  -- Solo logs del backend
echo   pm2 logs instantvende-wa   -- Solo logs de WhatsApp
echo   pm2 stop all          -- Detener todo
echo   pm2 restart all       -- Reiniciar todo
echo   pm2 delete all        -- Eliminar de PM2
echo.
