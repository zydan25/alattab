// whatsappClient.js
const { Client } = require('whatsapp-web.js');
// const Message = require('./models/Message');
const Session = require('./models/Session');
const qrcode = require('qrcode-terminal');

async function createWhatsAppClient() {
    // جلب الجلسة من MongoDB
    const savedSession = await Session.findOne({ name: 'default' });

    const client = new Client({
        puppeteer: {
            executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', // المسار الصحيح لمتصفح Chrome
            headless: true},
        session: savedSession ? savedSession.session : undefined
    });

    // إذا لم يكن هناك جلسة، أظهر QR
    client.on('qr', qr => {
        console.log('Scan QR code:');
        qrcode.generate(qr, { small: true });
    });

    client.on('ready', () => {
        console.log('✅ WhatsApp client is ready!');
    });

    // استقبال الرسائل وتخزينها في MongoDB
    client.on('message', async msg => {
        console.log(`Message from ${msg.from}: ${msg.body}`);
        // const newMessage = new Message({ from: msg.from, body: msg.body });
        // await newMessage.save();
    });

    // عند الحصول على session جديدة، احفظها في MongoDB
    client.on('authenticated', async session => {
        await Session.findOneAndUpdate(
            { name: 'default' },
            { session },
            { upsert: true }
        );
        console.log('Session saved to MongoDB');
    });

    client.initialize();
    return client;
}

module.exports = createWhatsAppClient;
