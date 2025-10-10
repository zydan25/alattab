// singleClient.js
const { Client } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const Session = require('./models/Session');

async function initWhatsAppClient() {
    const clientId = 'main'; // معرف ثابت للعميل الواحد

    // جلب الجلسة من MongoDB
    let sessionDoc = await Session.findOne({ clientId });
    let sessionData = null;

    if (sessionDoc && sessionDoc.session) {
        try {
            sessionData = JSON.parse(sessionDoc.session); // تحويل النص مرة أخرى إلى كائن
        } catch (err) {
            console.error('❌ Error parsing session JSON:', err);
        }
    }

    const client = new Client({
        session: sessionData || undefined,
        puppeteer: {
            executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', // المسار الصحيح لمتصفح Chrome
            headless: false
        }
    });

    // حدث ظهور QR
    client.on('qr', async (qr) => {
        console.log('QR RECEIVED');
        qrcode.generate(qr, { small: true });

        if (!sessionDoc) {
            sessionDoc = new Session({ clientId });
        }
        sessionDoc.qr = qr;
        sessionDoc.status = 'qr';
        await sessionDoc.save();
    });

    // حدث جاهزية العميل
    client.on('ready', async () => {
        console.log('Client is ready!');
    
        let session;
        if (typeof client.base64EncodedAuthInfo === 'function') {
            session = client.base64EncodedAuthInfo(); // whatsapp-web.js الحديثة
        } else if (typeof client.getSession === 'function') {
            
            session = await client.getSession(); // wppconnect
        } else {
            console.error('❌ Cannot get session info, update your library!');
         
           
        }
    
        if (!sessionDoc) sessionDoc = new Session({ clientId });
        sessionDoc.session = JSON.stringify(session);
        sessionDoc.status = 'connected';
        sessionDoc.lastConnected = new Date();
        await sessionDoc.save();
        console.log('Session saved successfully in MongoDB.');
    });
    

    // حدث فشل المصادقة
    client.on('auth_failure', async () => {
        console.log('Auth failure, deleting session...');
        await Session.deleteOne({ clientId });
    });

    // حدث نجاح المصادقة
    client.on('auth_success', async () => {
        console.log('Auth success, saving session...');
        const session = client.base64EncodedAuthInfo();

        if (!sessionDoc) {
            sessionDoc = new Session({ clientId });
        }
        sessionDoc.session = JSON.stringify(session); // حفظ كنص
        sessionDoc.status = 'connected';
        sessionDoc.lastConnected = new Date();
        await sessionDoc.save();
    });

    client.initialize();
    return client;
}

module.exports = initWhatsAppClient;
