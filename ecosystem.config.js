module.exports = {
  apps: [
    {
      name: 'instantvende-api',
      script: './venv/Scripts/python.exe',
      args: '-m uvicorn main:app --host 0.0.0.0 --port 8000',
      cwd: './backend',
      max_memory_restart: '500M',
      autorestart: true,
      restart_delay: 3000,
      max_restarts: 10,
      min_uptime: '10s',
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1'
      },
      out_file: './logs/api-out.log',
      error_file: './logs/api-error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      merge_logs: true
    },
    {
      name: 'instantvende-wa',
      script: './whatsapp_client.js',
      cwd: './whatsapp',
      interpreter: 'node',
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 50,
      min_uptime: '5s',
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
      script: './node_modules/vite/bin/vite.js',
      args: 'preview --port 4173',
      cwd: './frontend',
      interpreter: 'node',
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
