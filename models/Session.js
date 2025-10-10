// models/Session.js
const mongoose = require('mongoose');

const sessionSchema = new mongoose.Schema({
  clientId: { type: String, required: true, unique: true },
  session: { type: Object }, // استخدم Object لتخزين الجلسة مباشرة
  qr: { type: String },
  status: { type: String, default: 'idle' },
  lastConnected: { type: Date },
  updatedAt: { type: Date, default: Date.now }
});

module.exports = mongoose.model('Session', sessionSchema);
