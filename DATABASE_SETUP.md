# 📊 دليل إعداد قاعدة البيانات

## نظرة عامة

تم تحديث النظام لدعم **ثلاثة أنواع من قواعد البيانات**:
- ✅ **SQLite** (محلية - افتراضي)
- ✅ **MySQL** (خارجية)
- ✅ **PostgreSQL** (خارجية)

---

## 🚀 الطريقة السريعة (استخدام رابط مباشر)

### 1. افتح ملف `.env` وأضف أحد هذه الأسطر:

#### SQLite (محلي):
```bash
DATABASE_URI=sqlite:///instance/balance.db
```

#### MySQL:
```bash
DATABASE_URI=mysql+pymysql://username:password@localhost:3306/whatsapp_bot?charset=utf8mb4
```

#### PostgreSQL:
```bash
DATABASE_URI=postgresql+psycopg2://username:password@localhost:5432/whatsapp_bot
```

### 2. مثال حقيقي:
```bash
# MySQL على السيرفر المحلي
DATABASE_URI=mysql+pymysql://root:mypassword123@localhost:3306/whatsapp_bot?charset=utf8mb4

# PostgreSQL على سيرفر خارجي
DATABASE_URI=postgresql+psycopg2://admin:secret@192.168.1.100:5432/whatsapp_db

# SQLite محلي (افتراضي)
DATABASE_URI=sqlite:///instance/balance.db
```

---

## ⚙️ الطريقة التفصيلية (إعدادات منفصلة)

### 1. تحديد نوع قاعدة البيانات:
```bash
DATABASE_TYPE=mysql  # أو postgresql أو sqlite
```

### 2. إعدادات MySQL:
```bash
DATABASE_TYPE=mysql
DATABASE_HOST=localhost
DATABASE_PORT=3306
DATABASE_USER=root
DATABASE_PASSWORD=your_password
DATABASE_NAME=whatsapp_bot
DATABASE_CHARSET=utf8mb4
```

### 3. إعدادات PostgreSQL:
```bash
DATABASE_TYPE=postgresql
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=your_password
DATABASE_NAME=whatsapp_bot
```

### 4. إعدادات SQLite (افتراضي):
```bash
DATABASE_TYPE=sqlite
SQLITE_DB_PATH=instance/balance.db
```

---

## 📦 تثبيت المكتبات المطلوبة

### لجميع أنواع قواعد البيانات:
```bash
pip install -r requirements-database.txt
```

### أو يدوياً:

#### لـ SQLite (مدمج في Python):
```bash
pip install Flask-SQLAlchemy python-dotenv
```

#### لـ MySQL:
```bash
pip install Flask-SQLAlchemy pymysql python-dotenv
```

#### لـ PostgreSQL:
```bash
pip install Flask-SQLAlchemy psycopg2-binary python-dotenv
```

---

## 🧪 اختبار الاتصال

قم بتشغيل سكريبت الاختبار:
```bash
python test_database.py
```

**النتيجة المتوقعة:**
```
🧪 اختبار الاتصال بقاعدة البيانات
================================================================

📋 الإعدادات الحالية:
   type: mysql
   host: localhost
   port: 3306
   database: whatsapp_bot
   user: root

🔌 جاري اختبار الاتصال...
✅ الاتصال بقاعدة البيانات ناجح!
✅ تم إنشاء جميع الجداول بنجاح!

📊 الجداول الموجودة (2):
   • package (3 عمود)
   • query (13 عمود)
```

---

## 🗄️ الجداول المُنشأة

### 1. جدول `Package` (الباقات):
```python
- id (Integer, Primary Key)
- value (Integer) - قيمة الباقة بالريال
- volume (Float) - حجم الباقة بالجيجابايت
```

### 2. جدول `Query` (الاستعلامات):
```python
- id (Integer, Primary Key)
- phone_number (String) - رقم الهاتف
- query_time (DateTime) - وقت الاستعلام
- raw_data (Text) - البيانات الخام
- avblnce (Float) - الرصيد الحالي
- baga_amount (Float) - قيمة الباقة
- expdate (DateTime) - تاريخ الانتهاء
- remainAmount (Float) - باقي المبلغ
- minamtobill (Float) - الحد الأدنى للسداد
- daily (Boolean) - استعلام يومي؟
- consumption_since_last (Float) - الاستهلاك منذ آخر تقرير
- daily_consumption (Float) - الاستهلاك اليومي
- notes (String) - ملاحظات
- time_since_last (String) - الفرق الزمني
```

---

## 🔧 إعداد MySQL

### 1. إنشاء قاعدة البيانات:
```sql
CREATE DATABASE whatsapp_bot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. إنشاء مستخدم:
```sql
CREATE USER 'whatsapp_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON whatsapp_bot.* TO 'whatsapp_user'@'localhost';
FLUSH PRIVILEGES;
```

### 3. تحديث `.env`:
```bash
DATABASE_URI=mysql+pymysql://whatsapp_user:your_password@localhost:3306/whatsapp_bot?charset=utf8mb4
```

---

## 🐘 إعداد PostgreSQL

### 1. إنشاء قاعدة البيانات:
```sql
CREATE DATABASE whatsapp_bot;
```

### 2. إنشاء مستخدم:
```sql
CREATE USER whatsapp_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE whatsapp_bot TO whatsapp_user;
```

### 3. تحديث `.env`:
```bash
DATABASE_URI=postgresql+psycopg2://whatsapp_user:your_password@localhost:5432/whatsapp_bot
```

---

## 🔄 نقل البيانات من SQLite

إذا كانت لديك بيانات في `balance.db` القديم وتريد نقلها:

```bash
# قريباً: سكريبت النقل التلقائي
python migrate_database.py
```

---

## ⚡ إعدادات الأداء (اختياري)

في ملف `.env`:
```bash
# حجم Pool الاتصالات
DB_POOL_SIZE=10

# مهلة الاتصال (ثانية)
DB_POOL_TIMEOUT=30

# إعادة تدوير الاتصالات (ثانية)
DB_POOL_RECYCLE=3600

# الحد الأقصى للاتصالات الإضافية
DB_MAX_OVERFLOW=20
```

---

## ❓ حل المشاكل الشائعة

### المشكلة 1: "No module named 'pymysql'"
**الحل:**
```bash
pip install pymysql
```

### المشكلة 2: "Access denied for user"
**الحل:**
- تحقق من اسم المستخدم وكلمة المرور
- تأكد من منح الصلاحيات للمستخدم
- تحقق من أن الـ host صحيح

### المشكلة 3: "Can't connect to MySQL server"
**الحل:**
- تأكد من تشغيل خادم MySQL
- تحقق من رقم المنفذ (Port)
- تحقق من إعدادات Firewall

### المشكلة 4: "No such table: package"
**الحل:**
```bash
python test_database.py  # سينشئ الجداول تلقائياً
```

---

## 📝 ملاحظات مهمة

1. ⚠️ **لا تشارك ملف `.env`** - يحتوي على معلومات حساسة
2. 🔒 استخدم كلمات مرور قوية للإنتاج
3. 💾 قم بعمل نسخ احتياطية دورية
4. 🔍 راقب أداء قاعدة البيانات بانتظام

---

## 🆘 الدعم

إذا واجهت أي مشاكل:
1. راجع ملف `test_database.py` لمعرفة الخطأ
2. تحقق من سجلات التطبيق (logs)
3. تأكد من تثبيت جميع المكتبات المطلوبة
