@echo off
echo === InstantVende - Iniciando servicios ===
echo.

:: Crear carpeta de logs si no existe
if not exist "logs" mkdir logs

:: ── Paso 1: Instalar dependencias del cliente WhatsApp ──
echo [1/3] Instalando dependencias del cliente WhatsApp...
cd whatsapp
call npm install --silent
cd ..
echo     OK
echo.

:: ── Paso 2: Instalar y construir el panel de administracion ──
echo [2/3] Instalando y construyendo el panel de administracion...
cd frontend
call npm install --silent
call npm run build
cd ..
echo     OK
echo.

:: ── Paso 3: Iniciar todos los servicios con PM2 ──
echo [3/3] Iniciando todos los servicios con PM2...

:: Instalar PM2 si no esta instalado
where pm2 >nul 2>&1
if %errorlevel% neq 0 (
    echo Instalando PM2 globalmente...
    npm install -g pm2
)

:: Iniciar o recargar todos los servicios
pm2 start ecosystem.config.js

echo.
echo ============================================
echo   InstantVende -- Todos los servicios activos
echo ============================================
echo   Backend API:   http://localhost:8000
echo   Docs API:      http://localhost:8000/docs
echo   Panel Admin:   http://localhost:3000
echo ============================================
echo.
pm2 status

echo.
echo === Comandos utiles ===
echo   pm2 logs                      -- Ver todos los logs
echo   pm2 logs instantvende-api     -- Solo logs del backend
echo   pm2 logs instantvende-wa      -- Solo logs de WhatsApp
echo   pm2 logs instantvende-admin   -- Solo logs del panel
echo   pm2 stop all                  -- Detener todo
echo   pm2 restart all               -- Reiniciar todo
echo   pm2 delete all                -- Eliminar de PM2
echo.
echo IMPORTANTE: Para conectar WhatsApp, escanea el codigo QR con tu telefono:
echo   pm2 logs instantvende-wa
echo WhatsApp ^> Configuracion ^> Dispositivos vinculados ^> Vincular dispositivo
echo.
echo NOTA: Si el backend falla, asegurate de haber instalado las dependencias Python:
echo   cd backend ^&^& pip install -r requirements.txt
echo.
