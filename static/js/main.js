/**
 * WhatsApp Bot Control Panel JavaScript
 * إدارة واجهة المستخدم والتفاعل مع API
 */

// ===== متغيرات النظام العامة =====
let currentSection = 'dashboard';
let refreshInterval = null;
let lastQRCode = null;

// ===== تهيئة النظام عند تحميل الصفحة =====
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

/**
 * تهيئة التطبيق
 */
function initializeApp() {
    setupNavigation();
    setupEventListeners();
    startAutoRefresh();
    loadDashboard();
    showNotification('تم تحميل لوحة التحكم', 'success');
}

// ===== إدارة التنقل =====
function setupNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    
    navItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            
            // إزالة الحالة النشطة من جميع العناصر
            navItems.forEach(nav => nav.classList.remove('active'));
            document.querySelectorAll('.section').forEach(section => {
                section.classList.remove('active');
            });
            
            // تفعيل العنصر والقسم المحدد
            this.classList.add('active');
            const sectionId = this.getAttribute('data-section');
            document.getElementById(sectionId).classList.add('active');
            
            currentSection = sectionId;
            loadSectionData(sectionId);
        });
    });
}

/**
 * إعداد مستمعي الأحداث
 */
function setupEventListeners() {
    // نموذج إرسال الرسائل
    const sendForm = document.getElementById('sendMessageForm');
    if (sendForm) {
        sendForm.addEventListener('submit', handleSendMessage);
    }
    
    // مرشحات الرسائل
    const messageFilter = document.getElementById('messageFilter');
    if (messageFilter) {
        messageFilter.addEventListener('change', loadMessages);
    }
}

/**
 * تحميل بيانات القسم المحدد
 */
function loadSectionData(sectionId) {
    switch(sectionId) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'messages':
            loadMessages();
            break;
        case 'session':
            loadSessionInfo();
            break;
        case 'qr':
            loadQRCode();
            break;
        case 'logs':
            loadLogs();
            break;
    }
}

// ===== لوحة التحكم الرئيسية =====
async function loadDashboard() {
    try {
        showLoading(true);
        const response = await fetch('/api/status');
        const data = await response.json();
        
        if (data.success) {
            updateDashboard(data.data);
            updateConnectionStatus(data.data.session.isClientReady);
        } else {
            showNotification('فشل في تحميل بيانات لوحة التحكم', 'error');
        }
    } catch (error) {
        console.error('خطأ في تحميل لوحة التحكم:', error);
        showNotification('خطأ في الاتصال بالخادم', 'error');
    } finally {
        showLoading(false);
    }
}

function updateDashboard(data) {
    const { session, stats } = data;
    
    // تحديث الإحصائيات
    document.getElementById('clientStatus').textContent = 
        session.isClientReady ? 'متصل' : 'غير متصل';
    document.getElementById('messageCount').textContent = stats.messageQueueLength || 0;
    document.getElementById('errorCount').textContent = stats.errorCount || 0;
    document.getElementById('uptime').textContent = formatUptime(stats.uptime || 0);
    
    // تحديث معلومات النظام
    updateSystemInfo(stats);
}

function updateSystemInfo(stats) {
    const systemInfo = document.getElementById('systemInfo');
    if (!systemInfo) return;
    
    const memoryMB = Math.round(stats.memoryUsage?.used / 1024 / 1024) || 0;
    
    systemInfo.innerHTML = `
        <div class="info-item">
            <span class="info-label">حالة العميل:</span>
            <span class="info-value">${stats.clientReady ? 'جاهز' : 'غير جاهز'}</span>
        </div>
        <div class="info-item">
            <span class="info-label">جلسة نشطة:</span>
            <span class="info-value">${stats.sessionActive ? 'نعم' : 'لا'}</span>
        </div>
        <div class="info-item">
            <span class="info-label">استخدام الذاكرة:</span>
            <span class="info-value">${memoryMB} MB</span>
        </div>
        <div class="info-item">
            <span class="info-label">وقت التشغيل:</span>
            <span class="info-value">${formatUptime(stats.uptime)}</span>
        </div>
        <div class="info-item">
            <span class="info-label">آخر تحديث:</span>
            <span class="info-value">${new Date().toLocaleTimeString('ar-SA')}</span>
        </div>
    `;
}

function updateConnectionStatus(isConnected) {
    const statusIndicator = document.getElementById('connectionStatus');
    const statusDot = statusIndicator.querySelector('.status-dot');
    const statusText = statusIndicator.querySelector('.status-text');
    
    if (isConnected) {
        statusDot.className = 'status-dot online';
        statusText.textContent = 'متصل';
    } else {
        statusDot.className = 'status-dot offline';
        statusText.textContent = 'غير متصل';
    }
}

// ===== إدارة الرسائل =====
async function loadMessages() {
    try {
        const filter = document.getElementById('messageFilter')?.value || 'all';
        const response = await fetch(`/api/messages?limit=50&filter=${filter}`);
        const data = await response.json();
        
        if (data.success) {
            displayMessages(data.data);
        } else {
            showNotification('فشل في تحميل الرسائل', 'error');
        }
    } catch (error) {
        console.error('خطأ في تحميل الرسائل:', error);
        showNotification('خطأ في تحميل الرسائل', 'error');
    }
}

function displayMessages(messages) {
    const messagesList = document.getElementById('messagesList');
    if (!messagesList) return;
    
    if (!messages || messages.length === 0) {
        messagesList.innerHTML = '<div class="loading">لا توجد رسائل للعرض</div>';
        return;
    }
    
    const messagesHTML = messages.map(message => `
        <div class="message-item">
            <div class="message-header">
                <span class="message-from">${formatPhoneNumber(message.from_number)}</span>
                <span class="message-time">${formatDate(message.timestamp)}</span>
            </div>
            <div class="message-body">${escapeHtml(message.message_body)}</div>
            <div class="message-status ${message.status}">${getStatusText(message.status)}</div>
        </div>
    `).join('');
    
    messagesList.innerHTML = messagesHTML;
}

async function handleSendMessage(e) {
    e.preventDefault();
    
    const phoneNumber = document.getElementById('phoneNumber').value;
    const messageText = document.getElementById('messageText').value;
    const mediaFile = document.getElementById('mediaFile').files[0];
    
    if (!phoneNumber || !messageText) {
        showNotification('يرجى إدخال رقم الهاتف ونص الرسالة', 'warning');
        return;
    }
    
    try {
        showLoading(true);
        
        const formData = new FormData();
        formData.append('phoneNumber', phoneNumber);
        formData.append('message', messageText);
        if (mediaFile) {
            formData.append('media', mediaFile);
        }
        
        const response = await fetch('/api/send-message', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('تم إرسال الرسالة بنجاح', 'success');
            document.getElementById('sendMessageForm').reset();
            if (currentSection === 'messages') {
                loadMessages();
            }
        } else {
            showNotification('فشل في إرسال الرسالة: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('خطأ في إرسال الرسالة:', error);
        showNotification('خطأ في إرسال الرسالة', 'error');
    } finally {
        showLoading(false);
    }
}

// ===== إدارة الجلسة =====
async function loadSessionInfo() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        if (data.success) {
            displaySessionInfo(data.data.session);
        }
    } catch (error) {
        console.error('خطأ في تحميل معلومات الجلسة:', error);
    }
}

function displaySessionInfo(sessionData) {
    const sessionInfo = document.getElementById('sessionInfo');
    if (!sessionInfo) return;
    
    sessionInfo.innerHTML = `
        <div class="info-item">
            <span class="info-label">حالة العميل:</span>
            <span class="info-value">${sessionData.isClientReady ? 'جاهز' : 'غير جاهز'}</span>
        </div>
        <div class="info-item">
            <span class="info-label">رمز QR:</span>
            <span class="info-value">${sessionData.hasQRCode ? 'متوفر' : 'غير متوفر'}</span>
        </div>
        <div class="info-item">
            <span class="info-label">رقم الهاتف:</span>
            <span class="info-value">${sessionData.sessionData?.phoneNumber || 'غير محدد'}</span>
        </div>
        <div class="info-item">
            <span class="info-label">حالة إعادة التشغيل:</span>
            <span class="info-value">${sessionData.isRestarting ? 'جاري إعادة التشغيل' : 'عادي'}</span>
        </div>
    `;
}

async function startSession() {
    try {
        showLoading(true);
        const response = await fetch('/api/handler', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'restart_client' })
        });
        
        const result = await response.json();
        showNotification('تم بدء تشغيل الجلسة', 'success');
        
        setTimeout(() => {
            if (currentSection === 'session') loadSessionInfo();
            if (currentSection === 'dashboard') loadDashboard();
        }, 2000);
    } catch (error) {
        showNotification('خطأ في تشغيل الجلسة', 'error');
    } finally {
        showLoading(false);
    }
}

async function restartSession() {
    if (!confirm('هل أنت متأكد من إعادة تشغيل الجلسة؟')) return;
    
    try {
        showLoading(true);
        const response = await fetch('/api/restart');
        showNotification('تم بدء إعادة تشغيل الجلسة', 'info');
        
        setTimeout(() => {
            if (currentSection === 'session') loadSessionInfo();
            if (currentSection === 'dashboard') loadDashboard();
        }, 3000);
    } catch (error) {
        showNotification('خطأ في إعادة تشغيل الجلسة', 'error');
    } finally {
        showLoading(false);
    }
}

async function disconnectSession() {
    if (!confirm('هل أنت متأكد من قطع اتصال الجلسة؟')) return;
    
    try {
        showLoading(true);
        const response = await fetch('/api/disconnect');
        showNotification('تم قطع اتصال الجلسة', 'warning');
        
        setTimeout(() => {
            if (currentSection === 'session') loadSessionInfo();
            if (currentSection === 'dashboard') loadDashboard();
        }, 1000);
    } catch (error) {
        showNotification('خطأ في قطع الاتصال', 'error');
    } finally {
        showLoading(false);
    }
}

function stopSession() {
    disconnectSession();
}

// ===== إدارة رمز QR =====
async function loadQRCode() {
    try {
        const response = await fetch('/api/qr');
        const data = await response.json();
        
        if (data.success && data.qrCode) {
            displayQRCode(data.qrCode);
        } else {
            displayQRPlaceholder();
        }
    } catch (error) {
        console.error('خطأ في تحميل رمز QR:', error);
        displayQRPlaceholder();
    }
}

function displayQRCode(qrCode) {
    const qrContainer = document.getElementById('qrContainer');
    if (!qrContainer) return;
    
    // إنشاء رمز QR كصورة
    const qrCodeURL = `https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=${encodeURIComponent(qrCode)}`;
    
    qrContainer.innerHTML = `
        <div class="qr-code">
            <img src="${qrCodeURL}" alt="رمز QR للواتساب" />
        </div>
    `;
    
    lastQRCode = qrCode;
    showNotification('تم تحميل رمز QR - امسحه بهاتفك', 'info');
}

function displayQRPlaceholder() {
    const qrContainer = document.getElementById('qrContainer');
    if (!qrContainer) return;
    
    qrContainer.innerHTML = `
        <div class="qr-placeholder">
            <i class="fas fa-qrcode"></i>
            <p>لا يوجد رمز QR متاح حالياً</p>
            <button class="btn btn-primary" onclick="refreshQR()">
                <i class="fas fa-refresh"></i> تحديث QR
            </button>
        </div>
    `;
}

async function refreshQR() {
    await restartSession();
    setTimeout(loadQRCode, 3000);
}

function showQR() {
    // تبديل إلى قسم QR
    document.querySelector('[data-section="qr"]').click();
}

// ===== إدارة السجلات =====
async function loadLogs() {
    try {
        const response = await fetch('/api/errors');
        const data = await response.json();
        
        if (data.success) {
            displayErrors(data.data);
            displayActivityLogs(data.recentErrors);
        }
    } catch (error) {
        console.error('خطأ في تحميل السجلات:', error);
    }
}

function displayErrors(errors) {
    const errorsList = document.getElementById('errorsList');
    if (!errorsList) return;
    
    if (!errors || errors.length === 0) {
        errorsList.innerHTML = '<div class="loading">لا توجد أخطاء مسجلة</div>';
        return;
    }
    
    const errorsHTML = errors.map(error => `
        <div class="log-item error">
            <div class="log-time">${formatDate(error.timestamp)}</div>
            <div class="log-message">${escapeHtml(error.error_message)}</div>
        </div>
    `).join('');
    
    errorsList.innerHTML = errorsHTML;
}

function displayActivityLogs(logs) {
    const activityLogs = document.getElementById('activityLogs');
    if (!activityLogs) return;
    
    if (!logs || logs.length === 0) {
        activityLogs.innerHTML = '<div class="loading">لا توجد أنشطة مسجلة</div>';
        return;
    }
    
    const logsHTML = logs.map(log => `
        <div class="log-item ${getLogType(log.type)}">
            <div class="log-time">${formatDate(log.timestamp)}</div>
            <div class="log-message">${log.type}: ${escapeHtml(log.message)}</div>
        </div>
    `).join('');
    
    activityLogs.innerHTML = logsHTML;
}

async function clearLogs() {
    if (!confirm('هل أنت متأكد من مسح جميع السجلات؟')) return;
    
    // هذه الوظيفة تحتاج إلى API endpoint في الخادم
    showNotification('هذه الميزة قيد التطوير', 'info');
}

// ===== التحديث التلقائي =====
function startAutoRefresh() {
    refreshInterval = setInterval(() => {
        if (currentSection === 'dashboard') {
            loadDashboard();
        }
    }, 30000); // كل 30 ثانية
}

function refreshDashboard() {
    loadDashboard();
}

// ===== وظائف الإشعارات =====
function showNotification(message, type = 'info') {
    const notifications = document.getElementById('notifications');
    if (!notifications) return;
    
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <i class="fas fa-${getNotificationIcon(type)}"></i>
        ${message}
    `;
    
    notifications.appendChild(notification);
    
    // إزالة الإشعار بعد 5 ثوانٍ
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

function getNotificationIcon(type) {
    switch(type) {
        case 'success': return 'check-circle';
        case 'error': return 'exclamation-triangle';
        case 'warning': return 'exclamation-circle';
        case 'info': return 'info-circle';
        default: return 'info-circle';
    }
}

// ===== عرض/إخفاء شاشة التحميل =====
function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.classList.toggle('active', show);
    }
}

// ===== وظائف الأدوات المساعدة =====
function formatDate(dateString) {
    if (!dateString) return 'غير محدد';
    
    try {
        const date = new Date(dateString);
        return date.toLocaleString('ar-SA', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch {
        return 'تاريخ غير صالح';
    }
}

function formatUptime(seconds) {
    if (!seconds) return '0 د';
    
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (days > 0) return `${days} أيام`;
    if (hours > 0) return `${hours} ساعات`;
    return `${minutes} دقيقة`;
}

function formatPhoneNumber(phoneNumber) {
    if (!phoneNumber) return 'غير محدد';
    
    // إزالة @c.us وتنسيق الرقم
    const cleaned = phoneNumber.replace('@c.us', '');
    if (cleaned.startsWith('966')) {
        return '+966 ' + cleaned.substring(3);
    }
    return cleaned;
}

function escapeHtml(unsafe) {
    if (!unsafe) return '';
    
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function getStatusText(status) {
    switch(status) {
        case 'sent': return 'مرسلة';
        case 'received': return 'مستقبلة';
        case 'failed': return 'فشلت';
        default: return status;
    }
}

function getLogType(type) {
    if (type.includes('ERROR')) return 'error';
    if (type.includes('WARNING')) return 'warning';
    if (type.includes('SUCCESS')) return 'success';
    return '';
}

// ===== تنظيف الموارد عند إغلاق الصفحة =====
window.addEventListener('beforeunload', function() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});

// ===== دالة تسجيل الخروج من الجلسة =====
async function logoutSession() {
    if (!confirm('هل أنت متأكد من رغبتك في تسجيل الخروج من الجلسة الحالية؟\nسيتم حذف جميع بيانات الجلسة وستحتاج لمسح رمز QR مرة أخرى.')) {
        return;
    }
    
    try {
        showNotification('جاري تسجيل الخروج من الجلسة...', 'info');
        
        const response = await fetch('/api/logout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const result = await response.json();
            showNotification('تم تسجيل الخروج بنجاح! سيتم إعادة تحميل الصفحة...', 'success');
            setTimeout(() => {
                location.reload();
            }, 2000);
        } else {
            throw new Error('فشل في تسجيل الخروج');
        }
    } catch (error) {
        console.error('خطأ في تسجيل الخروج:', error);
        showNotification('حدث خطأ أثناء تسجيل الخروج: ' + error.message, 'error');
    }
}

// ===== تصدير الوظائف للاستخدام العام =====
window.startSession = startSession;
window.restartSession = restartSession;
window.stopSession = stopSession;
window.disconnectSession = disconnectSession;
window.showQR = showQR;
window.refreshQR = refreshQR;
window.refreshDashboard = refreshDashboard;
window.loadMessages = loadMessages;
window.clearLogs = clearLogs;
window.logoutSession = logoutSession;
