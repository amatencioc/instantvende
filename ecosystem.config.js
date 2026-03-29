// En Linux/Mac Python 3 se llama 'python3'; en Windows es 'python'
const pythonInterpreter = process.platform === 'win32' ? 'python' : 'python3';

module.exports = {
  apps: [
    {
      name: 'instantvende-api',
      script: 'uvicorn',
      args: 'main:app --host 0.0.0.0 --port 8000',
      cwd: './backend',
      interpreter: pythonInterpreter,
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
      env: {
        NODE_ENV: 'production'
      },
      out_file: './logs/wa-out.log',
      error_file: './logs/wa-error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      merge_logs: true
    },
    {
      // Requiere haber ejecutado 'npm run build' en frontend/ antes de iniciar
      name: 'instantvende-admin',
      script: 'npm',
      args: 'run preview',
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
