const express = require('express');
const cors = require('cors');
const createWhatsAppClient = require('./whatsappClient');
const Message = require('./models/Message');
require('dotenv').config();

const app = express();
app.use(cors());
app.use(express.json());

// إعداد WhatsApp client
let client;
createWhatsAppClient().then(c => client = c);

// API لإرسال الرسائل
app.post('/api/send-message', async (req, res) => {
    const { phoneNumber, message } = req.body;

    if (!phoneNumber || !message) {
        return res.status(400).json({ success: false, error: 'رقم الهاتف والرسالة مطلوبان' });
    }

    try {
        const chatId = phoneNumber.includes('@c.us') ? phoneNumber : `${phoneNumber}@c.us`;
        await client.sendMessage(chatId, message);
        res.json({ success: true, message: 'تم الإرسال بنجاح' });
    } catch (err) {
        console.error(err);
        res.status(500).json({ success: false, error: err.message });
    }
});

// API لجلب الرسائل المخزنة
app.get('/api/messages', async (req, res) => {
    const messages = await Message.find().sort({ timestamp: -1 });
    res.json(messages);
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
