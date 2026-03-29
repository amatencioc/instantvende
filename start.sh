#!/usr/bin/env bash
# ============================================================
# InstantVende — Script de inicio (Linux / Mac)
# Instala dependencias, construye el frontend e inicia PM2
# ============================================================
set -e

echo "=== InstantVende - Iniciando servicios ==="
echo ""

# Crear carpeta de logs si no existe
mkdir -p logs

# ── Paso 1: Dependencias del backend Python ──
echo "[1/4] Instalando dependencias del backend Python..."
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install -q -r requirements.txt
deactivate
cd ..
echo "      OK"
echo ""

# ── Paso 2: Dependencias del cliente WhatsApp ──
echo "[2/4] Instalando dependencias del cliente WhatsApp..."
cd whatsapp && npm install --silent && cd ..
echo "      OK"
echo ""

# ── Paso 3: Instalar y construir el panel de administración ──
echo "[3/4] Instalando y construyendo el panel de administración..."
cd frontend && npm install --silent && npm run build && cd ..
echo "      OK"
echo ""

# ── Paso 4: Iniciar todos los servicios con PM2 ──
echo "[4/4] Iniciando todos los servicios con PM2..."
if ! command -v pm2 &>/dev/null; then
    echo "Instalando PM2 globalmente..."
    npm install -g pm2
fi

# Actualizar la variable PATH del venv en el ecosistema para el backend
# PM2 lanzará python3 del venv si está en PATH; de lo contrario usa el sistema
VENV_BIN="$(pwd)/backend/venv/bin"
export PATH="$VENV_BIN:$PATH"

pm2 start ecosystem.config.js

echo ""
echo "============================================"
echo "  InstantVende — Todos los servicios activos"
echo "============================================"
echo "  Backend API:   http://localhost:8000"
echo "  Docs API:      http://localhost:8000/docs"
echo "  Panel Admin:   http://localhost:3000"
echo "============================================"
echo ""
pm2 status

echo ""
echo "=== Comandos útiles ==="
echo "  pm2 logs                      -- Ver todos los logs"
echo "  pm2 logs instantvende-api     -- Solo logs del backend"
echo "  pm2 logs instantvende-wa      -- Solo logs de WhatsApp"
echo "  pm2 logs instantvende-admin   -- Solo logs del panel"
echo "  pm2 stop all                  -- Detener todo"
echo "  pm2 restart all               -- Reiniciar todo"
echo "  pm2 delete all                -- Eliminar de PM2"
echo ""
echo "IMPORTANTE: Para conectar WhatsApp, escanea el código QR:"
echo "  pm2 logs instantvende-wa"
echo "  WhatsApp > Configuración > Dispositivos vinculados > Vincular dispositivo"
echo ""
