require('dotenv').config();

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
const BACKEND_API_KEY = process.env.BACKEND_API_KEY || '';
const BUSINESS_NAME = process.env.BUSINESS_NAME || 'InstantVende';
const AI_TIMEOUT_MS = parseInt(process.env.AI_TIMEOUT_MS || '90000', 10);
const TYPING_DELAY_MS = parseInt(process.env.TYPING_DELAY_MS || '3000', 10);
const MAX_RETRIES = parseInt(process.env.MAX_RETRIES || '2', 10);
const RECONNECT_DELAY_MS = parseInt(process.env.RECONNECT_DELAY_MS || '5000', 10);
const MAX_MSG_LENGTH = parseInt(process.env.MAX_MSG_LENGTH || '3500', 10);
const WHATSAPP_SESSION_PATH = process.env.WHATSAPP_SESSION_PATH || './whatsapp-session';
const ERROR_MSG_TIMEOUT = process.env.ERROR_MSG_TIMEOUT ||
    'Disculpa la demora 🙏 Escribe *#catalogo* para ver nuestros productos.';
const ERROR_MSG_GENERAL = process.env.ERROR_MSG_GENERAL ||
    'Disculpa, tuve un problema técnico. Escribe *#ayuda* para los comandos. 🙏';

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
        dataPath: WHATSAPP_SESSION_PATH
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

/**
 * Llama al backend con reintentos ante errores de red (backoff exponencial).
 * @param {number} attempt - intento actual (empieza en 1)
 */
async function callBackend(phone, messageBody, attempt = 1) {
    try {
        return await axios.post(`${BACKEND_URL}/api/process-message`, {
            phone,
            message: messageBody
        }, {
            timeout: AI_TIMEOUT_MS,
            headers: { 'X-API-Key': BACKEND_API_KEY }
        });
    } catch (error) {
        const isNetworkError = error.code === 'ECONNREFUSED' || error.code === 'ECONNRESET';
        if (isNetworkError && attempt <= MAX_RETRIES) {
            const delayMs = 1000 * attempt; // backoff lineal: 1s, 2s, ...
            console.log(`🔄 Reintento ${attempt}/${MAX_RETRIES} en ${delayMs / 1000}s...`);
            await new Promise(resolve => setTimeout(resolve, delayMs));
            return callBackend(phone, messageBody, attempt + 1);
        }
        throw error;
    }
}

/**
 * Divide un texto largo en fragmentos que no superen maxLen caracteres,
 * preferentemente cortando en saltos de línea o puntos.
 */
function splitMessage(text, maxLen) {
    if (text.length <= maxLen) return [text];

    const MIN_SPLIT_RATIO = 0.5; // posición mínima aceptable para el corte (50% del límite)
    const parts = [];
    let remaining = text;
    while (remaining.length > maxLen) {
        let cutAt = maxLen;
        // Preferir corte en salto de línea
        const lastNewline = remaining.lastIndexOf('\n', maxLen);
        if (lastNewline > maxLen * MIN_SPLIT_RATIO) {
            cutAt = lastNewline + 1;
        } else {
            // Preferir corte en punto o espacio
            const lastPeriod = remaining.lastIndexOf('.', maxLen);
            const lastSpace = remaining.lastIndexOf(' ', maxLen);
            const bestBreak = Math.max(lastPeriod, lastSpace);
            if (bestBreak > maxLen * MIN_SPLIT_RATIO) cutAt = bestBreak + 1;
        }
        parts.push(remaining.slice(0, cutAt).trim());
        remaining = remaining.slice(cutAt).trim();
    }
    if (remaining.length > 0) parts.push(remaining);
    return parts;
}

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

        const response = await callBackend(message.from, message.body);

        clearInterval(typingInterval);
        await chat.clearState();

        const data = response.data;

        if (data.bot_enabled && data.reply) {
            console.log('✅ Respuesta lista (' + data.reply.length + ' chars)');
            console.log('📤 Enviando...');

            // Dividir respuestas largas en múltiples mensajes
            const parts = splitMessage(data.reply, MAX_MSG_LENGTH);
            for (let i = 0; i < parts.length; i++) {
                if (i === 0) {
                    await message.reply(parts[i]);
                } else {
                    await chat.sendMessage(parts[i]);
                }
            }

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
            userMsg = ERROR_MSG_TIMEOUT;
        } else if (error.response?.status === 401) {
            console.error('   Error de autenticación (401) — verifica BACKEND_API_KEY en .env');
        } else if (error.response?.status === 429) {
            console.error('   Rate limiting (429) — mensaje descartado');
            userMsg = null; // no responder al cliente en este caso
        } else if (error.response) {
            console.error('   Status:', error.response.status);
            console.error('   Error:', JSON.stringify(error.response.data));
        } else {
            console.error('  ', error.message);
        }

        console.log('═══════════════════════════════════════════════════════\n');

        if (userMsg !== null) {
            try {
                await message.reply(userMsg || ERROR_MSG_GENERAL);
            } catch (e) {
                console.error('No se pudo enviar mensaje de error al cliente');
            }
        }
    }
});

client.on('disconnected', (reason) => {
    console.log('\n❌ WhatsApp desconectado');
    console.log('Razón:', reason);
    console.log(`🔄 Reconectando en ${RECONNECT_DELAY_MS / 1000}s...`);
    setTimeout(() => {
        console.log('🚀 Intentando reconexión...');
        client.initialize().catch(error => {
            console.error('❌ Error al reconectar:', error.message);
        });
    }, RECONNECT_DELAY_MS);
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