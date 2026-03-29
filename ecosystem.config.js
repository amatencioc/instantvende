module.exports = {
  apps: [
    {
      name: 'instantvende-api',
      script: 'uvicorn',
      args: 'main:app --host 0.0.0.0 --port 8000',
      cwd: './backend',
      interpreter: 'python',
      interpreter_args: '-m',
      // Reiniciar si usa más de 500MB RAM (ej: Ollama se queda cargado)
      max_memory_restart: '500M',
      // Reiniciar automáticamente si el proceso muere
      autorestart: true,
      // Esperar 3s entre reinicios para evitar loops
      restart_delay: 3000,
      // Máximo 10 reinicios en 1 minuto antes de marcar como "errored"
      max_restarts: 10,
      min_uptime: '10s',
      // Variables de entorno
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1'
      },
      // Logs
      out_file: './logs/api-out.log',
      error_file: './logs/api-error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      merge_logs: true
    },
    {
      name: 'instantvende-wa',
      script: './whatsapp/whatsapp_client.js',
      cwd: '.',
      interpreter: 'node',
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 10,
      min_uptime: '10s',
      // Watch para recargar si el archivo cambia (opcional, comentar en producción)
      // watch: ['whatsapp/whatsapp_client.js'],
      env: {
        NODE_ENV: 'production'
      },
      out_file: './logs/wa-out.log',
      error_file: './logs/wa-error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      merge_logs: true
    },
    {
      name: 'instantvende-admin',
      script: 'npx',
      args: 'vite preview --port 3000 --host',
      cwd: './frontend',
      env: {
        NODE_ENV: 'production'
      },
      out_file: './logs/admin-out.log',
      error_file: './logs/admin-error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      merge_logs: true
    }
  ]
};
