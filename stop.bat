@echo off
echo === InstantVende - Deteniendo servicios ===
pm2 stop all
pm2 status
