require('dotenv').config();

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
const BACKEND_API_KEY = process.env.BACKEND_API_KEY || '';
const BUSINESS_NAME = process.env.BUSINESS_NAME || 'InstantVende';
const AI_TIMEOUT_MS = parseInt(process.env.AI_TIMEOUT_MS || '90000', 10);
const TYPING_DELAY_MS = parseInt(process.env.TYPING_DELAY_MS || '3000', 10);

if (!BACKEND_API_KEY) {
    console.error('❌ BACKEND_API_KEY no está configurada en .env');
    console.error('   Copia whatsapp/.env.example a whatsapp/.env y configura la clave');
    process.exit(1);
}

console.log('═══════════════════════════════════════════════════════');
console.log(`📱 ${BUSINESS_NAME} - Cliente WhatsApp`);
console.log('═══════════════════════════════════════════════════════\n');

const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: './whatsapp-session'
    }),
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu'
        ]
    }
});

client.on('qr', (qr) => {
    console.log('\n📱 ESCANEA ESTE CÓDIGO QR CON TU WHATSAPP:\n');
    console.log('Pasos:');
    console.log('1. Abre WhatsApp en tu teléfono');
    console.log('2. Ve a Configuración > Dispositivos vinculados');
    console.log('3. Toca "Vincular un dispositivo"');
    console.log('4. Escanea el código de abajo:\n');
    
    qrcode.generate(qr, { small: true });
    
    console.log('\n⏳ Esperando escaneo...\n');
});

client.on('ready', async () => {
    console.log('═══════════════════════════════════════════════════════');
    console.log('✅ WhatsApp conectado exitosamente!');
    console.log('═══════════════════════════════════════════════════════');
    console.log('🤖 Bot activo y listo para recibir mensajes');
    console.log('📊 Backend: ' + BACKEND_URL);
    console.log('═══════════════════════════════════════════════════════\n');
    
    const info = await client.info;
    console.log('📱 Cuenta conectada:');
    console.log('   Nombre: ' + info.pushname);
    console.log('   Número: ' + info.wid.user);
    console.log('   Plataforma: ' + info.platform);
    console.log('\n💬 Esperando mensajes...\n');
});

client.on('authenticated', () => {
    console.log('🔐 Autenticación exitosa');
});

client.on('auth_failure', (msg) => {
    console.error('❌ Error de autenticación:', msg);
    console.log('💡 Elimina la carpeta "whatsapp-session" y vuelve a intentar');
});

client.on('loading_screen', (percent, message) => {
    console.log(`⏳ Cargando WhatsApp: ${percent}% - ${message}`);
});

client.on('message', async (message) => {
    try {
        // Ignorar grupos, estados y mensajes propios
        if (message.from.includes('@g.us')) return;
        if (message.from === 'status@broadcast') return;
        if (message.fromMe) return;

        const contact = await message.getContact();
        const contactName = contact.pushname || 'Desconocido';

        console.log('\n═══════════════════════════════════════════════════════');
        console.log('ℹ️  De:', contactName, '|', message.from);
        console.log('💬 Mensaje:', message.body);
        console.log('🕒 Hora:', new Date().toLocaleTimeString());

        // Marcar como leído
        await message.getChat().then(chat => chat.sendSeen());

        // Mostrar "escribiendo..." mientras procesamos
        const chat = await message.getChat();
        await chat.sendStateTyping();

        // Si la IA tarda más de TYPING_DELAY_MS, mantenemos el indicador activo
        const typingInterval = setInterval(async () => {
            try { await chat.sendStateTyping(); } catch (_) {}
        }, TYPING_DELAY_MS);

        console.log('🤖 Procesando con IA...');

        const response = await axios.post(`${BACKEND_URL}/api/process-message`, {
            phone: message.from,
            message: message.body
        }, {
            timeout: AI_TIMEOUT_MS,
            headers: { 'X-API-Key': BACKEND_API_KEY }
        });

        clearInterval(typingInterval);
        await chat.clearState();

        const data = response.data;

        if (data.bot_enabled && data.reply) {
            console.log('✅ Respuesta lista (' + data.reply.length + ' chars)');
            console.log('📤 Enviando...');

            await message.reply(data.reply);

            // Si hay imagen del producto, enviarla también
            if (data.media_url) {
                try {
                    const { MessageMedia } = require('whatsapp-web.js');
                    const media = await MessageMedia.fromUrl(data.media_url);
                    await chat.sendMessage(media);
                    console.log('🖼️ Imagen enviada:', data.media_url);
                } catch (imgErr) {
                    console.log('⚠️  No se pudo enviar imagen:', imgErr.message);
                }
            }

            console.log('✅ Enviado exitosamente');
        } else if (!data.bot_enabled) {
            console.log('👤 Bot desactivado — respuesta manual requerida');
        }

        console.log('═══════════════════════════════════════════════════════\n');

    } catch (error) {
        console.error('\n❌ ERROR:');

        let userMsg = null;

        if (error.code === 'ECONNREFUSED') {
            console.error('   Backend no responde en', BACKEND_URL);
            console.error('   ¿Está corriendo el backend? (python main.py)');
        } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
            console.error('   Timeout — la IA tardó más de', AI_TIMEOUT_MS / 1000, 'segundos');
            userMsg = 'Disculpa la demora 🙏 Escribe *#catalogo* para ver nuestros productos o *#ayuda* para los comandos disponibles.';
        } else if (error.response?.status === 401) {
            console.error('   Error de autenticación (401) — verifica BACKEND_API_KEY en .env');
        } else if (error.response) {
            console.error('   Status:', error.response.status);
            console.error('   Error:', JSON.stringify(error.response.data));
        } else {
            console.error('  ', error.message);
        }

        console.log('═══════════════════════════════════════════════════════\n');

        try {
            await message.reply(userMsg || 'Disculpa, tuve un problema técnico. Escribe *#ayuda* para ver los comandos disponibles. 🙏');
        } catch (e) {
            console.error('No se pudo enviar mensaje de error al cliente');
        }
    }
});

client.on('disconnected', (reason) => {
    console.log('\n❌ WhatsApp desconectado');
    console.log('Razón:', reason);
});

process.on('unhandledRejection', (error) => {
    console.error('❌ Error no manejado:', error);
});

console.log('🚀 Iniciando cliente de WhatsApp...');
console.log('⏳ Esto puede tardar 10-30 segundos...\n');
console.log('💡 La primera vez descargará Chromium (~150MB)\n');

client.initialize().catch(error => {
    console.error('❌ Error al inicializar:', error.message);
    console.log('\n💡 Soluciones:');
    console.log('   1. Verifica tu internet');
    console.log('   2. Elimina carpeta "whatsapp-session"');
    console.log('   3. Intenta de nuevo\n');
});