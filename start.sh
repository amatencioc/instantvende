#!/usr/bin/env bash
set -e

echo "=== InstantVende - Iniciando servicios ==="

# Crear carpeta de logs si no existe
mkdir -p logs

# Instalar PM2 si no está instalado
if ! command -v pm2 &>/dev/null; then
  echo "Instalando PM2..."
  npm install -g pm2
fi

# Copiar archivos .env si no existen
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "AVISO: Se creó backend/.env desde el ejemplo."
  echo "       Edítalo y pon una API_SECRET_KEY real antes de continuar."
fi
if [ ! -f whatsapp/.env ]; then
  cp whatsapp/.env.example whatsapp/.env
  echo "AVISO: Se creó whatsapp/.env desde el ejemplo."
  echo "       Edítalo y pon el mismo valor de API_SECRET_KEY que en backend/.env."
fi
if [ ! -f frontend/.env ]; then
  cp frontend/.env.example frontend/.env
fi

# 1) Instalar dependencias del cliente WhatsApp
echo ""
echo "[1/3] Instalando dependencias de WhatsApp..."
(cd whatsapp && npm install --silent)

# 2) Instalar dependencias y compilar el panel de administración
echo ""
echo "[2/3] Compilando el panel de administración (frontend)..."
(cd frontend && npm install --silent && npm run build)

# 3) Iniciar todos los servicios con PM2
echo ""
echo "[3/3] Iniciando servicios con PM2..."
pm2 start ecosystem.config.js

echo ""
echo "=== Estado de los servicios ==="
pm2 status

echo ""
echo "========================================="
echo "  InstantVende está corriendo en:"
echo "    API Backend  : http://localhost:8000"
echo "    API Docs     : http://localhost:8000/docs"
echo "    Panel Admin  : http://localhost:3000"
echo "========================================="
echo ""
echo "Al iniciar por primera vez el bot de WhatsApp, escanea el código QR:"
echo "  pm2 logs instantvende-wa"
echo ""
echo "=== Comandos útiles ==="
echo "  pm2 logs                     -- Ver logs en tiempo real"
echo "  pm2 logs instantvende-api    -- Solo logs del backend"
echo "  pm2 logs instantvende-wa     -- Solo logs de WhatsApp"
echo "  pm2 logs instantvende-admin  -- Solo logs del panel"
echo "  pm2 stop all                 -- Detener todo"
echo "  pm2 restart all              -- Reiniciar todo"
echo "  pm2 delete all               -- Eliminar de PM2"
