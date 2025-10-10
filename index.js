// index.js
require('dotenv').config();
const mongoose = require('./db'); // ملف الاتصال بـ MongoDB
const initWhatsAppClient = require('./whatsapp');

async function start() {
    try {
        // التأكد من اتصال MongoDB
        await mongoose.connection;
        console.log('✅ MongoDB connected');

        // تشغيل عميل واتساب واحد
        const client = await initWhatsAppClient();

        // مثال لإرسال رسالة بعد 10 ثوانٍ
        // setTimeout(async () => {
        //     const number = '967XXXXXXXXX@c.us'; // ضع رقم الهاتف هنا
        //     const message = 'مرحباً، هذه رسالة تجريبية!';
        //     try {
        //         await client.sendMessage(number, message);
        //         console.log('Message sent!');
        //     } catch (err) {
        //         console.error('Error sending message:', err);
        //     }
        // }, 10000);

    } catch (err) {
        console.error('❌ Error starting app:', err);
    }
}

start();
