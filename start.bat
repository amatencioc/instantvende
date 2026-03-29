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

:: Copiar archivos .env si no existen
if not exist "backend\.env" (
    echo Copiando backend\.env.example ^> backend\.env
    copy backend\.env.example backend\.env
    echo AVISO: Edita backend\.env y pon una API_SECRET_KEY real antes de continuar.
)
if not exist "whatsapp\.env" (
    echo Copiando whatsapp\.env.example ^> whatsapp\.env
    copy whatsapp\.env.example whatsapp\.env
    echo AVISO: Edita whatsapp\.env y pon el mismo valor de API_SECRET_KEY.
)
if not exist "frontend\.env" (
    echo Copiando frontend\.env.example ^> frontend\.env
    copy frontend\.env.example frontend\.env
)

:: Instalar dependencias del cliente WhatsApp
echo.
echo [1/3] Instalando dependencias de WhatsApp...
cd whatsapp
call npm install --silent
cd ..

:: Instalar dependencias y compilar el panel de administracion
echo.
echo [2/3] Compilando el panel de administracion (frontend)...
cd frontend
call npm install --silent
call npm run build
cd ..

:: Iniciar o recargar todos los servicios con PM2
echo.
echo [3/3] Iniciando servicios con PM2...
pm2 start ecosystem.config.js

echo.
echo === Estado de los servicios ===
pm2 status

echo.
echo =========================================
echo   InstantVende esta corriendo en:
echo     API Backend  : http://localhost:8000
echo     API Docs     : http://localhost:8000/docs
echo     Panel Admin  : http://localhost:3000
echo =========================================
echo.
echo Al iniciar por primera vez el bot de WhatsApp, escanea el código QR:
echo   pm2 logs instantvende-wa
echo.
echo === Comandos útiles ===
echo   pm2 logs              -- Ver logs en tiempo real
echo   pm2 logs instantvende-api   -- Solo logs del backend
echo   pm2 logs instantvende-wa    -- Solo logs de WhatsApp
echo   pm2 logs instantvende-admin -- Solo logs del panel
echo   pm2 stop all          -- Detener todo
echo   pm2 restart all       -- Reiniciar todo
echo   pm2 delete all        -- Eliminar de PM2
echo.
