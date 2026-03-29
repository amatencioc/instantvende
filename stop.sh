#!/usr/bin/env bash
echo "=== InstantVende - Deteniendo servicios ==="
pm2 stop all
pm2 status
echo ""
echo "Todos los servicios detenidos. Para reiniciar ejecuta: ./start.sh"
