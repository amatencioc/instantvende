const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');

const BACKEND_URL = 'http://localhost:8000';
const BUSINESS_NAME = 'InstantVende';

console.log('═══════════════════════════════��═══════════════════════');
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
        console.log('📨 NUEVO MENSAJE');
        console.log('═══════════════════════════════════════════════════════');
        console.log('De:', contactName);
        console.log('Número:', message.from);
        console.log('Mensaje:', message.body);
        console.log('Hora:', new Date().toLocaleTimeString());
        
        console.log('\n🤖 Procesando con IA...');
        
        const response = await axios.post(`${BACKEND_URL}/api/process-message`, {
            phone: message.from,
            message: message.body
        }, {
            timeout: 120000
        });
        
        const data = response.data;
        
        if (data.bot_enabled && data.reply) {
            console.log('✅ Respuesta IA:');
            console.log('  ', data.reply);
            console.log('\n📤 Enviando...');
            
            await message.reply(data.reply);
            
            console.log('✅ Enviado exitosamente');
        } else {
            console.log('👤 Bot desactivado - Respuesta manual requerida');
        }
        
        console.log('═══════════════════════════════════════════════════════\n');
        console.log('💬 Esperando más mensajes...\n');
        
    } catch (error) {
        console.error('\n❌ ERROR:');
        
        if (error.code === 'ECONNREFUSED') {
            console.error('   Backend no responde en', BACKEND_URL);
            console.error('   ¿Está corriendo el backend? (python main.py)');
        } else if (error.response) {
            console.error('   Status:', error.response.status);
            console.error('   Error:', error.response.data);
        } else {
            console.error('  ', error.message);
        }
        
        console.log('═══════════════════════════════════════════════════════\n');
        
        try {
            await message.reply('Disculpa, tuve un problema técnico. Intenta de nuevo. 🙏');
        } catch (e) {
            console.error('No se pudo enviar mensaje de error');
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