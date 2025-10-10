/**
 * نظام بوت واتساب متكامل
 * يتضمن إدارة الجلسات، الرسائل، API، ومعالجة الأخطاء
 * 
 * المطور: HASRIAN TOPTECH
 * التاريخ: 2025-09-09
 */

// ===== استيراد المكتبات المطلوبة =====
require('./db'); // تأكد أنه قبل استخدام أي نموذج

const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const fs = require('fs-extra');
const moment = require('moment');
const axios = require('axios');
const multer = require('multer');
const Session = require('./models/Session');
const cors = require('cors');
const bodyParser = require('body-parser');
const path = require('path');

// ===== إعدادات النظام الأساسية =====
const app = express();
const PORT = process.env.PORT || 3000;
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:5000'; // رابط النظام الأصلي

// إعداد middleware
app.use(cors());
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

// خدمة الملفات الثابتة من مجلد public
app.use(express.static(path.join(__dirname, 'public')));

// ===== متغيرات النظام العامة =====
let whatsappClient = null;
let isClientReady = false;
let currentQRCode = null;
let sessionData = {};
let errorLog = [];
let messageQueue = [];
let isRestarting = false;
let isClientDestroying = false; // علامة لتتبع حالة الإغلاق
let lastRestartTime = null;
let restartAttempts = 0;
const MAX_RESTART_ATTEMPTS = 5;
const MIN_RESTART_INTERVAL = 30000; // 30 ثانية كحد أدنى بين إعادة التشغيل
let lastErrorTime = null;
let connectionTimeout = null;
const CONNECTION_TIMEOUT = 180000; // مهلة الاتصال 2 دقيقة
let isLogoutInProgress = false; // متغير لتتبع عملية LOGOUT المقصودة
let isInitializing = false;
// ===== إعداد قاعدة البيانات =====
const dbPath = path.join(__dirname, 'whatsapp_sessions.db');
let db = null;

/**
 * تهيئة قاعدة البيانات
 * إنشاء الجداول المطلوبة لتخزين بيانات الجلسات والرسائل
 */
function initializeDatabase() {
    try {
        db = new sqlite3.Database(dbPath);
        
        // جدول الجلسات
        db.run(`
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                phone_number TEXT,
                status TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                qr_code TEXT,
                client_info TEXT
            )
        `);
        
        // جدول الرسائل
        db.run(`
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE,
                from_number TEXT,
                to_number TEXT,
                message_body TEXT,
                message_type TEXT,
                media_url TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT
            )
        `);
        
        // جدول سجل الأخطاء
        db.run(`
            CREATE TABLE IF NOT EXISTS error_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_message TEXT,
                error_stack TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolved BOOLEAN DEFAULT FALSE
            )
        `);
        
        console.log('✅ تم تهيئة قاعدة البيانات بنجاح');
        logMessage('DATABASE', 'تم تهيئة قاعدة البيانات بنجاح');
        
    } catch (error) {
        console.error('❌ خطأ في تهيئة قاعدة البيانات:', error);
        logError('DATABASE_INIT_ERROR', error);
    }
}

// =============================================================================
// ===== قسم إدارة الجلسة (Session Management) =====
// =============================================================================

/**
 * دالة تشغيل العميل الرئيسية
 * تقوم بإنشاء عميل واتساب جديد وتهيئة جميع المستمعين
 */
// إعدادات Chrome - يمكن تخصيصها عبر متغيرات البيئة
const chromePath = process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PUPPETEER_TIMEOUT = parseInt(process.env.PUPPETEER_TIMEOUT) || 300000; // 5 دقائق افتراضي

// require('dotenv').config();
// const mongoose = require('mongoose');
// async function connectDB() {
//   try {
//     await mongoose.connect(process.env.MONGO_URI, {
//         useNewUrlParser: true,
//         useUnifiedTopology: true
//     })
//     .then(() => console.log('✅ Connected to MongoDB'))
//     .catch(err => console.error('❌ MongoDB connection error:', err));
    
//   } catch (err) {
//     console.error('❌ MongoDB connection error:', err);
//     process.exit(1);
//   }
// }

// async function loadSession() {
//     const saved = await Session.findOne({ clientId: 'main-client' });
//     if (saved && saved.session) {
//       console.log('✅ Loaded session from MongoDB');
//       return saved.session;
//     }
//     console.log('⚠️ No valid session found, new QR required');
//     return null;
// }
// async function saveSession(session) {
//     await Session.findOneAndUpdate(
//       { clientId: 'main-client' },
//       { session, status: 'authenticated', updatedAt: new Date() },
//       { upsert: true }
//     );
//     console.log('💾 Session saved to MongoDB');
// }


async function loadSession() {
    try {
      const saved = await Session.findOne({ clientId: 'main-client' });
      if (!saved || !saved.session) {
        console.log('⚠️ No valid session found, new QR required');
        return null;
      }
  
      let sessionData = saved.session;
  
      // إذا كانت محفوظة كنص JSON، نفكها
      if (typeof sessionData === 'string') {
        try {
          sessionData = JSON.parse(sessionData);
          console.log('✅ Session parsed from JSON string');
        } catch (err) {
          console.warn('⚠️ Session not JSON, using as-is');
        }
      }
  
      // تحقق من صحة البنية
      if (sessionData.WABrowserId && sessionData.WASecretBundle) {
        console.log('✅ Loaded valid session from MongoDB');
        return sessionData;
      } else {
        console.warn('⚠️ Invalid session structure, new QR required');
        return null;
      }
    } catch (err) {
      console.error('❌ Error loading session from DB:', err);
      return null;
    }
  }
  
async function saveSession(session) {
    
    if (!session || !session.WABrowserId) {
      console.warn('⚠️ Attempted to save empty session, skipping...');
      return;
    }
  
    await Session.findOneAndUpdate(
      { clientId: 'main-client' },
      { session, status: 'authenticated', updatedAt: new Date() },
      { upsert: true }
    );
    console.log('💾 Session saved to MongoDB');
}
  
  

async function clearSession(reason = '') {
    await Session.deleteOne({ clientId: 'main-client' });
    console.log('🗑️ Session cleared from MongoDB', reason ? `(${reason})` : '');
}

async function startClient() {
    
    
    try {
        // فحص إذا كان هناك عميل يعمل بالفعل
        if (whatsappClient && !isClientDestroying) {
            console.log('⚠️ يوجد عميل يعمل بالفعل');
            return;
        }
        
        // فحص محاولات إعادة التشغيل
        if (restartAttempts >= MAX_RESTART_ATTEMPTS) {
            console.log('🛑 تم الوصول للحد الأقصى من محاولات إعادة التشغيل');
            restartAttempts = 0;
            await new Promise(resolve => setTimeout(resolve, 30000)); // انتظار 5 دقائق
        }
        
        console.log('🚀 بدء تشغيل عميل واتساب...');
        logMessage('CLIENT_START', 'بدء تشغيل عميل واتساب');
        isInitializing=true;
        const savedSession = await Session.findOne({ name: 'default' });
        const existingSession = await loadSession();
        // إنشاء عميل جديد مع إعدادات الجلسة المحلية
        whatsappClient = new Client({
            // authStrategy: new LocalAuth({
            //     clientId: 'whatsapp-bot-session',
            //     dataPath: './sessions'
            // }),
            puppeteer: {
                headless: false,

                executablePath: chromePath,  // سيبحث عن Chrome المحلي تلقائياً
                args: [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-extensions',
                    '--disable-plugins',
                    '--disable-default-apps',
                    '--disable-background-networking',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-features=TranslateUI',
                    '--disable-ipc-flooding-protection'
                ],
                ignoreDefaultArgs: ['--disable-extensions']
                
            },
            session: existingSession || undefined

            // session: savedSession ? savedSession.session : undefined
        });
        
        // إلغاء مؤقت الاتصال إذا كان موجوداً
        // if (connectionTimeout) {
        //     clearTimeout(connectionTimeout);
        //     connectionTimeout = null;
        // }
        
        // // تعيين مؤقت جديد للاتصال
        // connectionTimeout = setTimeout(() => {
        //     if (!isClientReady && !isRestarting) {
        //         console.log('⏰ انتهت مهلة الاتصال - لم يتم المسح خلال المدة المحددة');
        //         logMessage('CONNECTION_TIMEOUT', 'انتهت مهلة انتظار مسح QR Code');
        //         // لا نعيد التشغيل تلقائياً، ننتظر تدخل المستخدم أو خطأ حقيقي
        //     }
        // }, CONNECTION_TIMEOUT);
        
        // تسجيل مستمع رمز QR
        whatsappClient.on('qr', async (qr) => {
            try {
                console.log('📱 رمز QR جديد تم إنشاؤه');
                isClientReady = false;
                currentQRCode = qr;
                await Session.findOneAndUpdate(
                    { clientId: 'main-client' },
                    { status: 'waiting_qr', qr, updatedAt: new Date() },
                    { upsert: true }
                );
                
                
                // عرض رمز QR في الطرفية
                // qrcode.generate(qr, { small: true });
                
                // حفظ رمز QR في قاعدة البيانات
                // saveQRCodeToDatabase(qr);
                
                // إرسال رمز QR للنظام الأصلي (معطل مؤقتاً)
                // sendQRToAPI(qr);
                
                logMessage('QR_GENERATED', 'تم إنشاء رمز QR جديد');
            } catch(error) {
                console.error('❌ خطأ في معالجة رمز QR:', error);
                logError('QR_HANDLER_ERROR', error);
            }
        });
        
        // تسجيل مستمع جاهزية العميل
        whatsappClient.on('ready', async () => {
            // إلغاء مؤقت الاتصال عند نجاح الاتصال
            if (connectionTimeout) {
                clearTimeout(connectionTimeout);
                connectionTimeout = null;
            }
            console.log('✅ عميل واتساب جاهز للاستخدام!');
            isClientReady = true;
            isRestarting = false;
            isLogoutInProgress = false; // إعادة تعيين حالة logout
            restartAttempts = 0; // إعادة تعيين عداد المحاولات عند النجاح
            lastRestartTime = null;
            lastErrorTime = null; // مسح وقت الخطأ عند النجاح
            
            // الحصول على معلومات العميل
            const clientInfo = whatsappClient.info;
            sessionData = {
                phoneNumber: clientInfo.wid.user,
                pushname: clientInfo.pushname,
                platform: clientInfo.platform,
                status: 'ready',
                connectedAt: moment().format(),
                phone_number: clientInfo.wid.user,
                connected_at: new Date().toISOString(),
               // status: 'connected'
            };
            await Session.findOneAndUpdate(
                { clientId: 'main-client' },
                { status: 'ready', lastConnected: new Date(), updatedAt: new Date() },
                { upsert: true }
            );
            
            // حفظ بيانات الجلسة في قاعدة البيانات
            // await saveSessionToDatabase(sessionData);
            
            // إرسال حالة الجلسة للنظام الأصلي (معطل مؤقتاً)
            // await sendSessionStatusToAPI('ready', sessionData);
            
            logMessage('CLIENT_READY', `عميل واتساب جاهز - رقم الهاتف: ${sessionData.phoneNumber}`);
        });
        
        // تسجيل مستمع الرسائل الواردة
        whatsappClient.on('message', async (message) => {
            await handleIncomingMessage(message);
        });
        
        // تسجيل مستمع قطع الاتصال
        whatsappClient.on('disconnected', async (reason) => {
            console.log('⚠️ تم قطع الاتصال:', reason);
            isClientReady = false;
            await clearSession(reason);
            // await Session.findOneAndUpdate(
            //     { clientId: 'main-client' },
            //     { status: 'disconnected', reason, updatedAt: new Date() },
            //     { upsert: true }
            // );
            // لا تحذف كل الجلسات — حدّث الحالة فقط:
            await Session.findOneAndUpdate(
                { clientId: 'main-client' },
                { status: 'disconnected', reason, updatedAt: new Date() },
                { upsert: true }
            );

            // Session.deleteMany({});

            if (reason === 'LOGOUT') {
                console.log('👋 تم تسجيل الخروج من الجهاز الأصلي');
                isLogoutInProgress = true; // تعيين حالة LOGOUT
                lastErrorTime = null; // مسح وقت الخطأ لأن هذا logout مقصود
                await handleSessionDeletion('logout');
                logMessage('CLIENT_LOGOUT', 'تم تسجيل الخروج وإعادة تهيئة الجلسة');
            } else {
                console.log('🔄 قطع اتصال غير متوقع - سيتم إعادة المحاولة عند الحاجة');
                lastErrorTime = Date.now(); // تسجيل وقت الخطأ
                await handleSessionDeletion(reason);
                logMessage('CLIENT_DISCONNECTED', `تم قطع الاتصال: ${reason}`);
            }
        });
        
        // تسجيل مستمع الأخطاء
        whatsappClient.on('auth_failure', async (message) => {
            console.error('❌ فشل في المصادقة:', message);
            lastErrorTime = Date.now(); // تسجيل وقت الخطأ
            logError('AUTH_FAILURE', new Error(message));
            await clearSession('auth_failure');
            handleSessionDeletion('auth_failure');
        });
        // عند الحصول على session جديدة، احفظها في MongoDB
        whatsappClient.on('authenticated', async session => {
            await saveSession(session); // لا JSON.stringify هنا
            console.log('Session saved to MongoDB');
        });
        
        
        // بدء تشغيل العميل
        await whatsappClient.initialize();
        
    } catch (error) {
        console.error('❌ خطأ في تشغيل العميل:', error);
        logError('CLIENT_START_ERROR', error);
        
        // تسجيل وقت الخطأ وإعادة المحاولة فقط عند الضرورة
        lastErrorTime = Date.now();
        setTimeout(() => {
            if (!isRestarting && shouldAttemptRestart()) {
                console.log('🔄 محاولة إعادة التشغيل بعد خطأ في البدء...');
                restartClient();
            }
        }, 30000); // انتظار 30 ثانية بعد خطأ البدء
    }
}
// (async () => {
   
//     await connectDB(); // ✅ نضمن الاتصال أولاً
//     await startClient(); // ✅ بعد نجاح الاتصال نبدأ العميل فقط
// })();

/**
 * دالة تحديد ما إذا كان يجب إعادة التشغيل
 * تعتمد على وجود أخطاء فعلية وليس على الوقت فقط
 */
function shouldAttemptRestart() {
    // لا تعيد التشغيل إذا كان العميل يعمل بشكل طبيعي
    if (!isClientReady && isRestarting) {
        return false;
    }
    
    // لا تعيد التشغيل إذا كان هناك عملية logout مقصودة جارية
    if (isLogoutInProgress) {
        console.log('🚪 عملية تسجيل خروج مقصودة - لا حاجة لإعادة التشغيل');
        return false;
    }
    
    // لا تعيد التشغيل إذا تجاوزنا الحد الأقصى للمحاولات
    if (restartAttempts >= MAX_RESTART_ATTEMPTS) {
        console.log('🛑 تم الوصول للحد الأقصى من محاولات إعادة التشغيل');
        return false;
    }
    
    // أعد التشغيل فقط إذا:
    // 1. حدث خطأ مؤخراً (خلال آخر 5 دقائق)
    // 2. أو كان هناك قطع اتصال غير متوقع
    // 3. أو فشل في المصادقة
    const now = Date.now();
    const hasRecentError = lastErrorTime && (now - lastErrorTime) < 300000; // 5 دقائق
    
    if (hasRecentError) {
        console.log('⚠️ إعادة التشغيل بسبب خطأ حديث');
        return true;
    }
    
    // لا تعيد التشغيل إذا كان النظام في حالة انتظار QR code عادية
    if (currentQRCode && !isClientReady) {
        console.log('📱 النظام في انتظار مسح QR code - لا حاجة لإعادة التشغيل');
        return false;
    }
    
    return false;
}

/**
 * دالة إعادة تشغيل العميل
 */
async function restartClient() {
    try {
        if (isRestarting) {
            console.log('⏳ إعادة التشغيل قيد التنفيذ بالفعل...');
            return;
        }
        
        // التحقق من المدة الزمنية منذ آخر إعادة تشغيل
        const now = Date.now();
        // if (lastRestartTime && (now - lastRestartTime) < MIN_RESTART_INTERVAL) {
        //     const waitTime = MIN_RESTART_INTERVAL - (now - lastRestartTime);
        //     console.log(`⏱️ انتظار ${Math.round(waitTime/1000)} ثانية قبل إعادة التشغيل...`);
        //     await new Promise(resolve => setTimeout(resolve, waitTime));
        // }
        
        isRestarting = true;
        lastRestartTime = now;
        restartAttempts++;
        
        console.log(`🔄 بدء إعادة تشغيل العميل (المحاولة ${restartAttempts})...`);
        logMessage('CLIENT_RESTART', `بدء إعادة تشغيل العميل (المحاولة ${restartAttempts})`);
        
        await disconnectClient();
        await new Promise(resolve => setTimeout(resolve, 3000));
        await startClient();
        
        console.log('✅ تم إعادة تشغيل العميل بنجاح');
        logMessage('CLIENT_RESTARTED', 'تم إعادة تشغيل العميل بنجاح');
        
    } catch (error) {
        console.error('❌ خطأ في إعادة تشغيل العميل:', error);
        logError('CLIENT_RESTART_ERROR', error);
        isRestarting = false;
        try {
            await handleSessionDeletion('restart_error');
            await deleteSessionFilesWithRetry(path.join(__dirname, 'sessions', 'session-whatsapp-bot-session'));
        } catch (cleanupError) {
            console.error('❌ خطأ في تنظيف الجلسة:', cleanupError);
        }
        
        // إعادة المحاولة فقط إذا كان هناك خطأ حقيقي
        setTimeout(() => {
            if (!isRestarting && shouldAttemptRestart()) {
                restartClient();
            }
        }, 120000); // انتظار دقيقة واحدة
    }
}

/**
 * دالة قطع الاتصال بالعميل
 */
async function disconnectClient() {
    try {
        console.log('🔌 قطع الاتصال بالعميل...');
        
        if (whatsappClient && !isClientDestroying) {
            isClientReady = false;
            try {
                isClientDestroying = true;
                
                // إزالة جميع المستمعين لمنع تشغيل المزيد من العمليات
                whatsappClient.removeAllListeners();
                console.log('🔌 إغلاق العميل...');
                
                // محاولة الحصول على حالة العميل مع timeout قصير
                const statePromise = whatsappClient.getState();
                const timeoutPromise = new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('TIMEOUT')), 5000)
                );
                
                const clientState = await Promise.race([statePromise, timeoutPromise])
                    .catch(() => 'UNKNOWN');
                
                if (clientState !== 'UNKNOWN') {
                    try {
                        await whatsappClient.destroy();
                        console.log('🔌 تم إغلاق العميل بنجاح');
                    } catch (destroyError) {
                        console.log('⚠️ خطأ في إغلاق العميل:', destroyError.message);
                    }
                } else {
                    console.log('🔌 العميل مغلق بالفعل أو غير متاح');
                }
            } catch (destroyError) {
                // معالجة شاملة لجميع أنواع أخطاء Puppeteer
                if (destroyError.message.includes('Protocol error') || 
                    destroyError.message.includes('Target closed') ||
                    destroyError.message.includes('Session closed') ||
                    destroyError.message.includes('TIMEOUT') ||
                    destroyError.name === 'ProtocolError') {
                    console.log('🔌 العميل مغلق بالفعل أو انتهت المهلة');
                } else {
                    console.log('⚠️ تحذير في إغلاق العميل:', destroyError.message);
                }
            } finally {
                whatsappClient = null;
                isClientDestroying = false;
            }
        }
        
        await updateSessionStatus('disconnected');
        // await sendSessionStatusToAPI('disconnected', { reason: 'manual_disconnect' });
        
        console.log('✅ تم قطع الاتصال بنجاح');
        logMessage('CLIENT_DISCONNECTED', 'تم قطع الاتصال بالعميل يدوياً');
        
        // تنظيف المتغيرات
        isClientReady = false;
        currentQRCode = null;
        sessionData = {};
        isRestarting = false;
        // لا نمسح isLogoutInProgress هنا لأنه سيُمسح عند اكتمال العملية
    } catch (error) {
        console.error('❌ خطأ في قطع الاتصال:', error);
        logError('CLIENT_DISCONNECT_ERROR', error);
    }
}

/**
 * دالة التحقق من حالة الجلسة
 */
async function checkSession() {
    try {
        const sessionStatus = {
            isClientReady: isClientReady,
            hasQRCode: currentQRCode,
            sessionData: sessionData,
            clientState: whatsappClient ? whatsappClient.info : null,
            timestamp: moment().format(),
            isRestarting: isRestarting
        };
        
        console.log('📊 حالة الجلسة:', sessionStatus);
        return sessionStatus;
        
    } catch (error) {
        console.error('❌ خطأ في التحقق من حالة الجلسة:', error);
        logError('SESSION_CHECK_ERROR', error);
        return { error: error.message };
    }
}

/**
 * دالة معالجة حذف الجلسة
 */
async function handleSessionDeletion(reason = 'unknown') {
    try {
        console.log('🗑️ معالجة حذف الجلسة - السبب:', reason);
        logMessage('SESSION_DELETION', `معالجة حذف الجلسة - السبب: ${reason}`);
        
        isClientReady = false;
        currentQRCode = null;
        sessionData = {};
        
        // إغلاق العميل بشكل صحيح أولاً
        if (whatsappClient && !isClientDestroying) {
            try {
                isClientDestroying = true;
                
                // إزالة جميع المستمعين لمنع تشغيل المزيد من العمليات
                whatsappClient.removeAllListeners();
                
                // محاولة إغلاق العميل بشكل آمن مع معالجة شاملة للأخطاء
                try {
                    const statePromise = whatsappClient.getState();
                    const timeoutPromise = new Promise((_, reject) => 
                        setTimeout(() => reject(new Error('TIMEOUT')), 10000)
                    );
                    
                    const clientState = await Promise.race([statePromise, timeoutPromise])
                        .catch(() => 'UNKNOWN');
                    
                    if (clientState !== 'UNKNOWN') {
                        await whatsappClient.destroy();
                        console.log('🔌 تم إغلاق العميل بنجاح');
                    } else {
                        console.log('🔌 العميل مغلق بالفعل');
                    }
                } catch (destroyError) {
                    // تجاهل جميع أخطاء إغلاق Puppeteer
                    console.log('🔌 تم تجاهل خطأ إغلاق Puppeteer:', destroyError.message.substring(0, 100));
                }
            } catch (clientError) {
                // تجاهل جميع أخطاء العميل
                console.log('🔌 تم تجاهل خطأ العميل:', clientError.message.substring(0, 100));
            } finally {
                // تنظيف شامل
                whatsappClient = null;
                isClientDestroying = false;
            }
        }
        
        // انتظار قصير للتأكد من إغلاق العمليات
        await new Promise(resolve => setTimeout(resolve, 3000));
        
        // حذف ملفات الجلسة مع معالجة أخطاء EBUSY
        const sessionPath = path.join(__dirname, 'sessions');
        await deleteSessionFilesWithRetry(sessionPath);
        
        await updateSessionStatus('deleted', reason);
        // await sendSessionStatusToAPI('deleted', { reason: reason });
        
        setTimeout(() => {
            if (reason !== 'logout') {
                console.log('🔄 إعادة تشغيل العميل تلقائياً بعد حذف الجلسة...');
                if (!isRestarting) {
                    restartClient();
                }
            } else {
                console.log('🔄 إعادة تشغيل العميل بعد تسجيل الخروج...');
                isLogoutInProgress = false; // انتهاء عملية logout
                if (!isRestarting) {
                    restartClient();
                }
            }
        }, 6000);
        
    } catch (error) {
        console.error('❌ خطأ في معالجة حذف الجلسة:', error);
        logError('SESSION_DELETION_ERROR', error);
        
        // تسجيل وقت الخطأ ومحاولة إعادة التشغيل عند الحاجة فقط
        lastErrorTime = Date.now();
        setTimeout(() => {
            if (!isRestarting && shouldAttemptRestart()) {
                console.log('🔄 إعادة تشغيل العميل بعد خطأ في حذف الجلسة...');
                restartClient();
            }
        }, 10000); // انتظار 10 ثوان
    }
}

/**
 * حذف ملفات الجلسة مع إعادة المحاولة في حالة EBUSY
 */
async function deleteSessionFilesWithRetry(sessionPath, maxRetries = 3) {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            if (await fs.pathExists(sessionPath)) {
                await fs.remove(sessionPath);
                console.log('🗑️ تم حذف ملفات الجلسة المحلية بنجاح');
                return;
            }
            return; // المجلد غير موجود
        } catch (error) {
            if (error.code === 'EBUSY' || error.code === 'ENOTEMPTY') {
                console.warn(`⚠️ المحاولة ${attempt}: ملفات الجلسة مقفلة، انتظار وإعادة المحاولة...`);
                
                if (attempt < maxRetries) {
                    // انتظار أطول مع كل محاولة
                    await new Promise(resolve => setTimeout(resolve, attempt * 2000));
                    continue;
                } else {
                    console.warn('⚠️ فشل في حذف ملفات الجلسة - ستحذف تلقائياً عند إعادة التشغيل');
                    // محاولة حذف يدوية للملفات المهمة فقط
                    await forceDeleteCriticalFiles(sessionPath);
                }
            } else {
                console.error(`❌ خطأ في حذف ملفات الجلسة (المحاولة ${attempt}):`, error.message);
                if (attempt === maxRetries) {
                    throw error;
                }
            }
        }
    }
}

/**
 * حذف قسري للملفات الحرجة
 */
async function forceDeleteCriticalFiles(sessionPath) {
    try {
        const criticalFiles = [
            'session.json',
            'LocalStorage',
            'IndexedDB',
            'databases'
        ];
        
        for (const file of criticalFiles) {
            const filePath = path.join(sessionPath, 'session-whatsapp-bot-session', file);
            try {
                if (await fs.pathExists(filePath)) {
                    await fs.remove(filePath);
                    console.log(`🗑️ تم حذف: ${file}`);
                }
            } catch (fileError) {
                console.warn(`⚠️ لم يتم حذف ${file}: ${fileError.message}`);
            }
        }
    } catch (error) {
        console.warn('⚠️ خطأ في الحذف القسري:', error.message);
    }
}

// =============================================================================
// ===== قسم التعامل مع الرسائل (Messaging) =====
// =============================================================================

/**
 * دالة إرسال الرسائل
 */
async function sendMessage(phoneNumber, message, mediaPath = null) {
    try {
        if (!isClientReady) {
            throw new Error('العميل غير جاهز لإرسال الرسائل');
        }
        
        const formattedNumber = formatPhoneNumber(phoneNumber);
        console.log(`📤 إرسال رسالة إلى: ${formattedNumber}`);
        
        let sentMessage;
        
        if (mediaPath && await fs.pathExists(mediaPath)) {
            const media = MessageMedia.fromFilePath(mediaPath);
            sentMessage = await whatsappClient.sendMessage(formattedNumber, media, { caption: message });
            console.log('📎 تم إرسال رسالة مع ملف مرفق');
        } else {
            sentMessage = await whatsappClient.sendMessage(formattedNumber, message);
            console.log('💬 تم إرسال رسالة نصية');
        }
        
        await saveMessageToDatabase({
            messageId: sentMessage.id._serialized,
            fromNumber: sessionData.phoneNumber,
            toNumber: phoneNumber,
            messageBody: message,
            messageType: mediaPath ? 'media' : 'text',
            mediaUrl: mediaPath || null,
            status: 'sent'
        });
        
        logMessage('MESSAGE_SENT', `تم إرسال رسالة إلى ${phoneNumber}`);
        return { success: true, messageId: sentMessage.id._serialized };
        
    } catch (error) {
        console.error('❌ خطأ في إرسال الرسالة:', error);
        logError('MESSAGE_SEND_ERROR', error);
        return { success: false, error: error.message };
    }
}

/**
 * دالة معالجة الرسائل الواردة
 */
async function handleIncomingMessage(message) {
    try {
        const fromRaw = message.from || '';
            let from = fromRaw;
            if (fromRaw.includes('@c.us')) {
              from = '+' + fromRaw.replace(/@c\.us$/, '');
              if (!from.startsWith('+')) from = '+' + from;
            }
        console.log('📥 رسالة واردة من:', message.from);
        
        const messageData = {
            messageId: message.id._serialized,
            fromNumber: from,
            toNumber: message.to,
            messageBody: message.body,
            messageType: message.type,
            timestamp: moment(message.timestamp * 1000).format(),
            isGroup: message.from.includes('@g.us'),
            contact: await message.getContact()
            
        };
        
        if (message.hasMedia) {
            try {
                const media = await message.downloadMedia();
                const fileName = `media_${Date.now()}.${media.mimetype.split('/')[1]}`;
                const filePath = path.join(__dirname, 'downloads', fileName);
                
                await fs.ensureDir(path.dirname(filePath));
                await fs.writeFile(filePath, media.data, 'base64');
                messageData.mediaUrl = filePath;
                messageData.mediaType = media.mimetype;
                
                console.log('📎 تم تحميل ملف مرفق:', fileName);
            } catch (mediaError) {
                console.error('❌ خطأ في تحميل الملف المرفق:', mediaError);
                messageData.mediaError = mediaError.message;
            }
        }
        
        // await saveMessageToDatabase({
        //     messageId: messageData.messageId,
        //     fromNumber: messageData.fromNumber,
        //     toNumber: messageData.toNumber,
        //     messageBody: messageData.messageBody,
        //     messageType: messageData.messageType,
        //     mediaUrl: messageData.mediaUrl || null,
        //     status: 'received'
        // });
        
        await sendMessageToAPI(messageData);
        logMessage('MESSAGE_RECEIVED', `تم استقبال رسالة من ${messageData.fromNumber}`);
        
    } catch (error) {
        console.error('❌ خطأ في معالجة الرسالة الواردة:', error);
        logError('MESSAGE_HANDLE_ERROR', error);
    }
}

/**
 * دالة تسجيل مستمع الرسائل الواردة
 */
function onMessageReceived(callback) {
    if (typeof callback !== 'function') {
        throw new Error('callback يجب أن يكون دالة');
    }
    
    if (!whatsappClient._messageCallbacks) {
        whatsappClient._messageCallbacks = [];
    }
    
    whatsappClient._messageCallbacks.push(callback);
    console.log('✅ تم تسجيل مستمع جديد للرسائل الواردة');
}

// =============================================================================
// ===== قسم التكامل مع النظام الأصلي (API Integration) =====
// =============================================================================

/**
 * دالة معالج API الرئيسي
 */
async function apiHandler(data) {
    try {
        console.log('🔄 معالجة طلب API:', data.type);
        
        switch (data.type) {
            case 'session_status':
                return await checkSession();
                
            case 'send_message':
                return await sendMessage(data.phoneNumber, data.message, data.mediaPath);
                
            case 'restart_client':
                restartClient();
                return { success: true, message: 'تم بدء إعادة تشغيل العميل' };
                
            case 'disconnect_client':
                await disconnectClient();
                return { success: true, message: 'تم قطع الاتصال بالعميل' };
                
            case 'logout_session':
                if (!whatsappClient || !isClientReady) {
                    throw new Error('لا يوجد عميل نشط لتسجيل الخروج منه');
                }
                await whatsappClient.logout();
                return { success: true, message: 'تم تسجيل الخروج من الجلسة' };
                
            case 'get_qr':
                return { qrCode: currentQRCode, hasQR: !!currentQRCode };
                
            default:
                throw new Error(`نوع طلب غير مدعوم: ${data.type}`);
        }
        
    } catch (error) {
        console.error('❌ خطأ في معالج API:', error);
        logError('API_HANDLER_ERROR', error);
        return { success: false, error: error.message };
    }
}

async function sendQRToAPI(qrCode) {
    try {
        const response = await axios.post(`${API_BASE_URL}/webhook/qr`, {
            qrCode: qrCode,
            timestamp: moment().format(),
            botId: 'whatsapp-bot-1'
        });
        
        console.log('📱 تم إرسال رمز QR للنظام الأصلي');
        
    } catch (error) {
        console.error('❌ خطأ في إرسال رمز QR:', error);
    }
}

async function sendSessionStatusToAPI(status, data = {}) {
    try {
        const payload = {
            status: status,
            sessionData: data,
            timestamp: moment().format(),
            botId: 'whatsapp-bot-1'
        };
        
        const response = await axios.post(`${API_BASE_URL}/webhook/session-status`, payload);
        console.log('📊 تم إرسال حالة الجلسة للنظام الأصلي');
        
    } catch (error) {
        console.error('❌ خطأ في إرسال حالة الجلسة:', error);
    }
}

async function sendMessageToAPI(messageData) {
    try {
        const response = await axios.post(`${API_BASE_URL}/webhook/whatsapp`, {
            ...messageData,
            botId: 'whatsapp-bot-1'
        });
        
        console.log('💬 تم إرسال الرسالة للنظام الأصلي للمعالجة');
        
    } catch (error) {
        console.error('❌ خطأ في إرسال الرسالة للنظام الأصلي:', error);
    }
}

// =============================================================================
// ===== قسم معالجة الأخطاء والمراقبة (Error Handling & Monitoring) =====
// =============================================================================

/**
 * دالة تسجيل الأخطاء
 */
function logError(errorType, error) {
    const errorData = {
        type: errorType,
        message: error.message,
        stack: error.stack,
        timestamp: moment().format()
    };
    
    errorLog.push(errorData);
    
    // حفظ الخطأ في قاعدة البيانات
    if (db) {
        db.run(
            'INSERT INTO error_logs (error_message, error_stack) VALUES (?, ?)',
            [error.message, error.stack],
            function(err) {
                if (err) {
                    console.error('خطأ في حفظ سجل الخطأ:', err);
                }
            }
        );
    }
    
    // إرسال الخطأ للنظام الأصلي
    sendErrorToAPI(errorData);
}

/**
 * دالة تسجيل الرسائل العامة
 */
function logMessage(type, message) {
    const logData = {
        type: type,
        message: message,
        timestamp: moment().format()
    };
    
    console.log(`[${logData.timestamp}] ${type}: ${message}`);
}

/**
 * دالة إرسال الأخطاء للنظام الأصلي
 */
async function sendErrorToAPI(errorData) {
    try {
        // تعطيل الاتصال بالنظام الأصلي مؤقتاً لتجنب الأخطاء
        // await axios.post(`${API_BASE_URL}/webhook/error`, {
        //     ...errorData,
        //     botId: 'whatsapp-bot-1'
        // });
        
        console.log('📝 تم تسجيل الخطأ محلياً:', errorData.type);
        
    } catch (error) {
        console.error('❌ فشل في إرسال الخطأ للنظام الأصلي:', error);
    }
}

/**
 * دالة مراقبة الأخطاء والنظام
 */
function monitorErrors() {
    const interval = setInterval(async () => {
        try {
            // التحقق من حالة العميل - فقط إذا كان هناك خطأ حقيقي
            if (!isClientReady && !isRestarting && whatsappClient && shouldAttemptRestart()) {
                console.log('⚠️ العميل غير جاهز بسبب خطأ - محاولة إعادة التشغيل...');
                await restartClient();
            }
            
            // التحقق من طول قائمة انتظار الرسائل
            if (messageQueue.length > 100) {
                console.log('⚠️ قائمة انتظار الرسائل ممتلئة - تنظيف القائمة...');
                messageQueue = messageQueue.slice(-50);
            }
            
            // التحقق من طول سجل الأخطاء
            if (errorLog.length > 500) {
                console.log('⚠️ سجل الأخطاء ممتلئ - تنظيف السجل...');
                errorLog = errorLog.slice(-100);
            }
            
            // إرسال تقرير حالة دوري للنظام الأصلي
            const healthReport = {
                isClientReady: isClientReady,
                errorCount: errorLog.length,
                messageQueueLength: messageQueue.length,
                memoryUsage: process.memoryUsage(),
                uptime: process.uptime(),
                timestamp: moment().format()
            };
            
            // await sendHealthReportToAPI(healthReport);
            
        } catch (error) {
            console.error('❌ خطأ في مراقبة النظام:', error);
            logError('MONITOR_ERROR', error);
        }
    }, 60000); // كل دقيقة
    
    return interval;
}

/**
 * دالة إرسال تقرير الحالة للنظام الأصلي
 */
async function sendHealthReportToAPI(healthData) {
    try {
        await axios.post(`${API_BASE_URL}/webhook/health`, {
            ...healthData,
            botId: 'whatsapp-bot-1'
        });
        
    } catch (error) {
        console.error('❌ فشل في إرسال تقرير الحالة:', error);
    }
}

// =============================================================================
// ===== قسم قاعدة البيانات (Database Functions) =====
// =============================================================================

/**
 * حفظ بيانات الجلسة في قاعدة البيانات
 */
async function saveSessionToDatabase(sessionData) {
    return new Promise((resolve, reject) => {
        if (!db) {
            reject(new Error('قاعدة البيانات غير متاحة'));
            return;
        }
        
        const query = `
            INSERT OR REPLACE INTO sessions 
            (session_id, phone_number, status, client_info, updated_at) 
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        `;
        
        db.run(query, [
            'whatsapp-bot-session',
            sessionData.phoneNumber,
            sessionData.status,
            JSON.stringify(sessionData)
        ], function(err) {
            if (err) {
                reject(err);
            } else {
                resolve(this.lastID);
            }
        });
    });
}

/**
 * حفظ رمز QR في قاعدة البيانات
 */
async function saveQRCodeToDatabase(qrCode) {
    return new Promise((resolve, reject) => {
        if (!db) {
            reject(new Error('قاعدة البيانات غير متاحة'));
            return;
        }
        
        const query = `
            UPDATE sessions 
            SET qr_code = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE session_id = 'whatsapp-bot-session'
        `;
        
        db.run(query, [qrCode], function(err) {
            if (err) {
                reject(err);
            } else {
                resolve(this.changes);
            }
        });
    });
}

/**
 * تحديث حالة الجلسة
 */
async function updateSessionStatus(status, reason = null) {
    return new Promise((resolve, reject) => {
        if (!db) {
            reject(new Error('قاعدة البيانات غير متاحة'));
            return;
        }
        
        const clientInfo = JSON.stringify({ status, reason, timestamp: moment().format() });
        const query = `
            UPDATE sessions 
            SET status = ?, client_info = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE session_id = 'whatsapp-bot-session'
        `;
        
        db.run(query, [status, clientInfo], function(err) {
            if (err) {
                reject(err);
            } else {
                resolve(this.changes);
            }
        });
    });
}

/**
 * حفظ الرسالة في قاعدة البيانات
 */
async function saveMessageToDatabase(messageData) {
    return new Promise((resolve, reject) => {
        if (!db) {
            reject(new Error('قاعدة البيانات غير متاحة'));
            return;
        }
        
        const query = `
            INSERT INTO messages 
            (message_id, from_number, to_number, message_body, message_type, media_url, status) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        `;
        
        db.run(query, [
            messageData.messageId,
            messageData.fromNumber,
            messageData.toNumber,
            messageData.messageBody,
            messageData.messageType,
            messageData.mediaUrl,
            messageData.status
        ], function(err) {
            if (err) {
                reject(err);
            } else {
                resolve(this.lastID);
            }
        });
    });
}

// =============================================================================
// ===== قسم الوظائف المساعدة (Helper Functions) =====
// =============================================================================

/**
 * تنسيق رقم الهاتف
 */
function formatPhoneNumber(phoneNumber) {
    if (!phoneNumber) {
        throw new Error('رقم الهاتف مطلوب');
    }
    
    // إزالة جميع الأحرف غير الرقمية
    let formatted = phoneNumber.replace(/\D/g, '');
    
    // إزالة رمز البلد إذا كان موجود
    if (formatted.startsWith('966')) {
        formatted = formatted.substring(3);
    } else if (formatted.startsWith('967')) {
        formatted = formatted.substring(3);
    } else if (formatted.startsWith('+966')) {
        formatted = formatted.substring(4);
    } else if (formatted.startsWith('+967')) {
        formatted = formatted.substring(4);
    }
    
    // التحقق من صحة الرقم للسعودية أو اليمن
    if (formatted.startsWith('5') && formatted.length === 9) {
        return `966${formatted}@c.us`; // رقم سعودي
    } else if ((formatted.startsWith('7') || formatted.startsWith('1')) && formatted.length === 9) {
        return `967${formatted}@c.us`; // رقم يمني
    } else if (formatted.length >= 8 && formatted.length <= 15) {
        // رقم دولي آخر - نحاول تخمين رمز البلد
        if (formatted.length === 9 && formatted.startsWith('5')) {
            return `966${formatted}@c.us`;
        } else if (formatted.length === 9 && (formatted.startsWith('7') || formatted.startsWith('1'))) {
            return `967${formatted}@c.us`;
        } else {
            return `${formatted}@c.us`;
        }
    } else {
        throw new Error('تنسيق رقم الهاتف غير مدعوم. يرجى استخدام التنسيق الصحيح');
    }
}

/**
 * التحقق من صحة رقم الهاتف
 */
function validatePhoneNumber(phoneNumber) {
    const cleaned = phoneNumber.replace(/\D/g, '');
    return cleaned.length >= 9 && cleaned.length <= 15;
}

/**
 * تنظيف النص
 */
function sanitizeText(text) {
    if (typeof text !== 'string') return '';
    return text.trim().replace(/[\u200B-\u200D\uFEFF]/g, '');
}

/**
 * حصول على إحصائيات النظام
 */
async function getSystemStats() {
    try {
        return {
            clientReady: isClientReady,
            sessionActive: !!sessionData.phoneNumber,
            errorCount: errorLog.length,
            messageQueueLength: messageQueue.length,
            uptime: process.uptime(),
            memoryUsage: process.memoryUsage(),
            timestamp: moment().format()
        };
    } catch (error) {
        logError('STATS_ERROR', error);
        return { error: error.message };
    }
}

// =============================================================================
// ===== قسم API Routes والخادم =====
// =============================================================================

// تكوين multer لرفع الملفات
const storage = multer.diskStorage({
    destination: function (req, file, cb) {
        const uploadPath = path.join(__dirname, 'uploads');
        fs.ensureDirSync(uploadPath);
        cb(null, uploadPath);
    },
    filename: function (req, file, cb) {
        cb(null, `${Date.now()}-${file.originalname}`);
    }
});

const upload = multer({ storage: storage });

// ===== API Routes =====

/**
 * الصفحة الرئيسية - عرض حالة النظام
 */
app.get('/', async (req, res) => {
    try {
        const stats = await getSystemStats();
        const sessionStatus = await checkSession();
        
        const html = `
        <!DOCTYPE html>
        <html dir="rtl" lang="ar">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>WhatsApp Bot Status</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
                .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
                .ready { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
                .error { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
                .warning { background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; }
                .btn { padding: 10px 20px; margin: 5px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; }
                .btn-primary { background: #007bff; color: white; }
                .btn-danger { background: #dc3545; color: white; }
                .btn-warning { background: #ffc107; color: black; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 WhatsApp Bot Status</h1>
                
                <div class="status ${sessionStatus.isClientReady ? 'connected' : 'error'}">
                    <strong>حالة العميل:</strong> ${sessionStatus.isClientReady ? '✅ جاهز' : '❌ غير جاهز'}
                </div>
                
                <div class="status ${sessionStatus.hasQRCode ? 'warning' : 'ready'}">
                    <strong>رمز QR:</strong> ${sessionStatus.hasQRCode ? '⚠️ في انتظار المسح' : '✅ تم التفعيل'}
                </div>
                
                <h3>📊 الإحصائيات:</h3>
                <ul>
                    <li><strong>الأخطاء:</strong> ${stats.errorCount}</li>
                    <li><strong>قائمة الرسائل:</strong> ${stats.messageQueueLength}</li>
                    <li><strong>وقت التشغيل:</strong> ${Math.floor(stats.uptime / 60)} دقيقة</li>
                    <li><strong>استخدام الذاكرة:</strong> ${Math.round(stats.memoryUsage.used / 1024 / 1024)} MB</li>
                </ul>
                
                <h3>🎮 التحكم:</h3>
                <button onclick="restartClient()" class="btn btn-warning">🔄 إعادة تشغيل</button>
                <button onclick="disconnectClient()" class="btn btn-danger">🔌 قطع الاتصال</button>
                <button onclick="showQR()" class="btn btn-primary">📱 عرض QR</button>
                <button onclick="logoutSession()" class="btn btn-danger" style="background: #dc143c;">🚪 تسجيل خروج</button>
                
                <h3>📝 آخر الأخطاء:</h3>
                <div style="max-height: 200px; overflow-y: auto; background: #f8f9fa; padding: 10px; border-radius: 5px;">
                    ${errorLog.slice(-5).map(error => 
                        `<div><small>[${error.timestamp}]</small> <strong>${error.type}:</strong> ${error.message}</div>`
                    ).join('')}
                </div>
                
                <script>
                    // دوال التحكم في النظام
                    function restartClient() {
                        if (confirm('هل أنت متأكد من إعادة تشغيل العميل؟')) {
                            fetch('/api/restart')
                                .then(response => response.json())
                                .then(data => {
                                    alert(data.message || 'تم بدء إعادة التشغيل');
                                    setTimeout(() => location.reload(), 2000);
                                })
                                .catch(error => alert('خطأ: ' + error.message));
                        }
                    }
                    
                    function disconnectClient() {
                        if (confirm('هل أنت متأكد من قطع الاتصال؟')) {
                            fetch('/api/disconnect')
                                .then(response => response.json())
                                .then(data => {
                                    alert(data.message || 'تم قطع الاتصال');
                                    setTimeout(() => location.reload(), 2000);
                                })
                                .catch(error => alert('خطأ: ' + error.message));
                        }
                    }
                    
                    function showQR() {
                        fetch('/api/qr')
                            .then(response => response.json())
                            .then(data => {
                                if (data.success && data.qrCode) {
                                    const qrWindow = window.open('', 'QR Code', 'width=400,height=400');
                                    const htmlContent = '<html>' +
                                        '<head><title>QR Code</title></head>' +
                                        '<body style="text-align: center; padding: 20px;">' +
                                        '<h3>امسح الكود بهاتفك</h3>' +
                                        '<div id="qrcode"></div>' +
                                        '<script src="https://cdn.jsdelivr.net/npm/qrcode@1.5.3/build/qrcode.min.js"></script>' +
                                        '<script>' +
                                        'QRCode.toCanvas(document.getElementById("qrcode"), "' + data.qrCode + '", function (error) {' +
                                        'if (error) console.error(error);' +
                                        '});' +
                                        '</script>' +
                                        '</body>' +
                                        '</html>';
                                    qrWindow.document.write(htmlContent);
                                } else {
                                    alert(data.message || 'لا يوجد رمز QR متاح حالياً');
                                }
                            })
                            .catch(error => alert('خطأ: ' + error.message));
                    }
                    
                    function logoutSession() {
                        if (confirm('هل أنت متأكد من تسجيل الخروج من الجلسة الحالية؟\nسيتم حذف الجلسة وإظهار QR code جديد.')) {
                            fetch('/api/logout', { method: 'POST' })
                                .then(response => response.json())
                                .then(data => {
                                    if (data.success) {
                                        alert(data.message);
                                        setTimeout(() => location.reload(), 3000);
                                    } else {
                                        alert('خطأ: ' + data.error);
                                    }
                                })
                                .catch(error => alert('خطأ في الشبكة: ' + error.message));
                        }
                    }
                    
                    // تحديث تلقائي للصفحة كل 30 ثانية
                    setInterval(() => {
                        location.reload();
                    }, 30000);
                </script>
            </div>
        </body>
        </html>
        `;
        
        res.send(html);
        
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

/**
 * عرض حالة النظام
 */

// Health check endpoint سريع للمراقبة
app.get('/api/health', (req, res) => {
    res.status(200).json({
        status: 'ok',
        timestamp: new Date().toISOString(),
        server: 'running'
    });
});

app.get('/api/status', async (req, res) => {
    try {
        const clientState= whatsappClient ? whatsappClient.info : null;
        const status = await checkSession();
        const stats = await getSystemStats();
        let actualStatus = 'disconnected';
        let qrCode = null;
        let clientInfo=clientState;
        
        if (isClientReady && clientInfo) {
            actualStatus = 'connected';
        } else if (currentQRCode) {
            actualStatus = 'qr';
            qrCode = currentQRCode;
        } else if (isInitializing) {
            actualStatus = 'initializing';
        }
        res.json({
            success: true,
            data: {
                session: status,
                stats: stats,
                timestamp: moment().format()
            },
            status: actualStatus,
            isConnected: isClientReady,
            sessionId: 'whatsapp_main_session',
            client_info: clientInfo,
            qr: qrCode,
            timestamp: new Date().toISOString(),
            quick_response: true
        });
        
    } catch (error) {
        logError('API_STATUS_ERROR', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

/**
 * الحصول على رمز QR
 */
app.get('/api/qr', async (req, res) => {
    try {
        if (!currentQRCode) {
            return res.json({
                success: false,
                message: 'لا يوجد رمز QR متاح حالياً'
            });
        }
        
        res.json({
            success: true,
            qrCode: currentQRCode,
            timestamp: moment().format()
        });
        
    } catch (error) {
        logError('API_QR_ERROR', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});
// app.get('/api/status', async (req, res) => {
//     // إعداد الاستجابة السريعة
   
//     const sendQuickResponse = () => {
//         let actualStatus = 'disconnected';
//         let qrCode = null;
//         let clientInfo=clientState;
        
//         if (isClientReady && clientInfo) {
//             actualStatus = 'connected';
//         } else if (currentQR) {
//             actualStatus = 'qr';
//             qrCode = currentQRCode;
//         } else if (isInitializing) {
//             actualStatus = 'initializing';
//         }
        
//         return res.json({
//             success: true,
//             status: actualStatus,
//             isConnected: isClientReady,
//             sessionId: SESSION_ID,
//             client_info: clientInfo,
//             qr: qrCode,
//             timestamp: new Date().toISOString(),
//             quick_response: true
//         });
//     };
    
//     try {
//         // إرسال استجابة فورية في حالة التهيئة لتجنب timeout
//         if (isInitializing) {
//             console.log('⚡ إرسال استجابة سريعة - العميل قيد التهيئة');
//             return sendQuickResponse();
//         }
        
//         let actualStatus = 'disconnected';
//         let qrCode = null;
        
//         // التحقق من حالة العميل في الذاكرة أولاً
//         if (isClientReady && clientInfo) {
//             actualStatus = 'connected';
//         } else if (currentQR) {
//             actualStatus = 'qr';
//             qrCode = currentQR;
//         }
        
//         // محاولة الحصول على حالة الجلسة من قاعدة البيانات مع timeout قصير
//         let realSessionStatus;
//         try {
//             const dbPromise = sessionManager.getRealSessionStatus(SESSION_ID);
//             const timeoutPromise = new Promise((_, reject) => 
//                 setTimeout(() => reject(new Error('Database timeout')), 3000)
//             );
            
//             realSessionStatus = await Promise.race([dbPromise, timeoutPromise]);
//         } catch (dbError) {
//             console.log('⚠️ تجاهل قاعدة البيانات واستخدام البيانات من الذاكرة:', dbError.message);
//             return sendQuickResponse();
//         }
        
//         // معالجة رمز QR من قاعدة البيانات إذا لم يكن موجود في الذاكرة
//         if (!currentQR && realSessionStatus && realSessionStatus.qr_code) {
//             actualStatus = 'qr';
//             qrCode = realSessionStatus.qr_code;
//             currentQR = realSessionStatus.qr_code;
//         }
        
//         console.log(`🔍 حالة API: ${actualStatus} | QR: ${!!qrCode} | Connected: ${isClientReady} | Init: ${isInitializing}`);
        
//         res.json({
//             success: true,
//             status: actualStatus,
//             isConnected: isClientReady,
//             sessionId: SESSION_ID,
//             session: realSessionStatus,
//             client_info: clientInfo,
//             qr: qrCode,
//             timestamp: new Date().toISOString()
//         });
//     } catch (error) {
//         console.error('❌ خطأ في الحصول على الحالة:', error);
//         // إرسال استجابة أساسية في حالة الخطأ
//         sendQuickResponse();
//     }
// });

app.post('/api/connect', async (req, res) => {
    try {
        // التحقق من حالة التهيئة
        if (isInitializing) {
            console.log('⏳ العميل قيد التهيئة - يرجى الانتظار');
            return res.json({ 
                success: false, 
                message: 'العميل قيد التهيئة - يرجى الانتظار قليلاً' 
            });
        }

        if (isClientReady && clientInfo) {
            console.log('✅ البوت متصل بالفعل');
            return res.json({ 
                success: true, 
                message: 'البوت متصل بالفعل',
                status: 'already_connected'
            });
        }

        console.log('🔌 طلب اتصال جديد من الواجهة');
        isInitializing = true; // منع طلبات متزامنة
        
        try {
            // تنظيف أي جلسات قديمة أولاً
            await sessionManager.clearAllSessions();
            console.log('✅ تم تنظيف الجلسات القديمة');
            
            // بدء الاتصال
            await initializeClient();
            
            res.json({ 
                success: true, 
                message: 'تم بدء عملية الاتصال - يرجى انتظار رمز QR' 
            });
        } catch (initError) {
            console.error('❌ خطأ في تهيئة الاتصال:', initError);
            res.json({ 
                success: false, 
                message: `خطأ في بدء الاتصال: ${initError.message}` 
            });
        } finally {
            // إلغاء حالة التهيئة بعد 10 ثوانِ
            setTimeout(() => {
                isInitializing = false;
                console.log('⏳ تم إلغاء حالة التهيئة');
            }, 10000);
        }
    } catch (error) {
        console.error('❌ خطأ في بدء الاتصال:', error);
        isInitializing = false;
        res.json({ 
            success: false, 
            message: `خطأ في بدء الاتصال: ${error.message}` 
        });
    }
});
/**
 * إرسال رسالة
 */
app.post('/send', async (req, res) => {
    try {
      const { to, message } = req.body;
      // تحويل رقم الهاتف من "+9677xxxxxx" إلى "9677xxxxxx@c.us"
      const jid = to.replace(/^\+/, '') + '@c.us';
      
      // إرسال الرسالة عبر واتساب
        await whatsappClient.sendMessage(jid, message);
        res.json({ ok: true });
         console.log(`تم إرسال رسالة إلى ${to}: ${message.substring(0, 50)}...`);
  
    } catch (e) {
      console.error('خطأ في إرسال الرسالة:', e);
      res.status(500).json({ ok: false, error: e.message });
    }
  });
app.post('/api/send-message', upload.single('media'), async (req, res) => {
    try {
        const { phoneNumber, message } = req.body;
        
        if (!phoneNumber || !message) {
            return res.status(400).json({
                success: false,
                error: 'رقم الهاتف والرسالة مطلوبان'
            });
        }
        
        const mediaPath = req.file ? req.file.path : null;
        const result = await sendMessage(phoneNumber, message, mediaPath);
        
        res.json(result);
        
    } catch (error) {
        logError('API_SEND_MESSAGE_ERROR', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

/**
 * إعادة تشغيل العميل
 */
app.get('/api/restart', async (req, res) => {
    try {
        restartClient();
        res.json({
            success: true,
            message: 'تم بدء إعادة تشغيل العميل'
        });
        
    } catch (error) {
        logError('API_RESTART_ERROR', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

/**
 * قطع الاتصال
 */
app.get('/api/disconnect', async (req, res) => {
    try {
        await disconnectClient();
        res.json({
            success: true,
            message: 'تم قطع الاتصال بالعميل'
        });
        
    } catch (error) {
        logError('API_DISCONNECT_ERROR', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

/**
 * تسجيل الخروج من الجلسة الحالية
 */
app.post('/api/logout', async (req, res) => {
    try {
        if (!whatsappClient || !isClientReady) {
            return res.status(400).json({
                success: false,
                error: 'لا يوجد عميل نشط لتسجيل الخروج منه'
            });
        }
        
        console.log('🚪 بدء عملية تسجيل الخروج من الجلسة...');
        logMessage('LOGOUT_REQUEST', 'تم طلب تسجيل الخروج من الواجهة');
        
        // تعيين حالة logout مقصود
        isLogoutInProgress = true;
        lastErrorTime = null; // مسح وقت الخطأ
        
        // تسجيل الخروج من واتساب ويب
        await whatsappClient.logout();
        
        res.json({
            success: true,
            message: 'تم تسجيل الخروج بنجاح. سيتم إعادة تشغيل النظام وإظهار QR code جديد'
        });
        
    } catch (error) {
        console.error('❌ خطأ في تسجيل الخروج:', error);
        logError('API_LOGOUT_ERROR', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

/**
 * معالج API العام
 */
app.post('/api/handler', async (req, res) => {
    try {
        const result = await apiHandler(req.body);
        res.json(result);
        
    } catch (error) {
        logError('API_HANDLER_ERROR', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

/**
 * الحصول على الرسائل
 */
app.get('/api/messages', async (req, res) => {
    try {
        const limit = parseInt(req.query.limit) || 50;
        const offset = parseInt(req.query.offset) || 0;
        
        db.all(
            'SELECT * FROM messages ORDER BY timestamp DESC LIMIT ? OFFSET ?',
            [limit, offset],
            (err, rows) => {
                if (err) {
                    logError('API_MESSAGES_ERROR', err);
                    return res.status(500).json({
                        success: false,
                        error: err.message
                    });
                }
                
                res.json({
                    success: true,
                    data: rows,
                    count: rows.length
                });
            }
        );
        
    } catch (error) {
        logError('API_MESSAGES_ERROR', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

/**
 * الحصول على سجل الأخطاء
 */
app.get('/api/errors', async (req, res) => {
    try {
        const limit = parseInt(req.query.limit) || 50;
        
        db.all(
            'SELECT * FROM error_logs ORDER BY timestamp DESC LIMIT ?',
            [limit],
            (err, rows) => {
                if (err) {
                    return res.status(500).json({
                        success: false,
                        error: err.message
                    });
                }
                
                res.json({
                    success: true,
                    data: rows,
                    recentErrors: errorLog.slice(-10)
                });
            }
        );
        
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

// =============================================================================
// ===== تهيئة وتشغيل النظام =====
// =============================================================================

/**
 * دالة تهيئة النظام الرئيسية
 */
async function initializeSystem() {
    try {
        console.log('🚀 بدء تهيئة نظام بوت واتساب...');
        
        // تهيئة قاعدة البيانات
        initializeDatabase();
        
        // إنشاء المجلدات المطلوبة
        await fs.ensureDir(path.join(__dirname, 'downloads'));
        await fs.ensureDir(path.join(__dirname, 'uploads'));
        await fs.ensureDir(path.join(__dirname, 'sessions'));
        
        // بدء مراقبة الأخطاء
        const monitorInterval = monitorErrors();
        
        // التعامل مع إشارات إيقاف النظام
        const gracefulShutdown = async (signal) => {
            console.log(`\n⏹️ تم استلام إشارة ${signal}...`);
            clearInterval(monitorInterval);
            
            // إيقاف عمليات إعادة التشغيل
            isRestarting = true;
            
            if (whatsappClient && !isClientDestroying) {
                try {
                    await disconnectClient();
                } catch (error) {
                    console.error('❌ خطأ في إغلاق العميل:', error);
                }
            }
            
            if (db) {
                try {
                    db.close();
                    console.log('✅ تم إغلاق قاعدة البيانات');
                } catch (error) {
                    console.error('❌ خطأ في إغلاق قاعدة البيانات:', error);
                }
            }
            
            console.log('✅ تم إيقاف النظام بأمان');
            process.exit(0);
        };
        
        process.on('SIGINT', () => gracefulShutdown('SIGINT'));
        process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
        process.on('uncaughtException', (error) => {
            const errorMsg = error.message || '';
            
            // تجاهل أخطاء Puppeteer المتوقعة ولا تغلق النظام
            const isPuppeteerError = errorMsg.includes('Protocol error') ||
                                   errorMsg.includes('Session closed') ||
                                   errorMsg.includes('Target closed') ||
                                   errorMsg.includes('Page has been closed') ||
                                   errorMsg.includes('Runtime.callFunctionOn');
            
            if (isPuppeteerError) {
                console.log('⚠️ خطأ Puppeteer متوقع (لا يتطلب إغلاق النظام):', errorMsg);
                logError('PUPPETEER_PROTOCOL_ERROR', error);
                
                // لا تعيد التشغيل إذا كان هناك عملية logout جارية
                if (!isLogoutInProgress && !isRestarting && restartAttempts < MAX_RESTART_ATTEMPTS) {
                    setTimeout(() => {
                        console.log('🔄 إعادة تشغيل العميل بعد خطأ Puppeteer...');
                        restartClient();
                    }, 3000);
                }
                return;
            }
            
            // للأخطاء الحقيقية فقط
            console.error('❌ خطأ غير متوقع (حرج):', error);
            logError('UNCAUGHT_EXCEPTION', error);
            gracefulShutdown('UNCAUGHT_EXCEPTION');
        });
        
        // بدء تشغيل العميل
        await startClient();
        
        console.log('✅ تم تهيئة النظام بنجاح');
        logMessage('SYSTEM_INIT', 'تم تهيئة نظام بوت واتساب بنجاح');
        
    } catch (error) {
        console.error('❌ خطأ في تهيئة النظام:', error);
        logError('SYSTEM_INIT_ERROR', error);
        process.exit(1);
    }
}

// بدء تشغيل الخادم
app.listen(PORT, async() => {
    console.log(`🌐 خادم API يعمل على المنفذ ${PORT}`);
    console.log(`📱 الواجهة الرئيسية: http://localhost:${PORT}`);
    console.log(`🔗 API Endpoint: http://localhost:${PORT}/api`);
    // await connectDB()
    // تهيئة النظام
    initializeSystem();
});

// تصدير الوظائف للاستخدام الخارجي
module.exports = {
    startClient,
    restartClient,
    disconnectClient,
    checkSession,
    sendMessage,
    onMessageReceived,
    apiHandler,
    getSystemStats,
    formatPhoneNumber,
    validatePhoneNumber
};
