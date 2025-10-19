# 🚀 دليل البدء السريع - النظام المحدث

## ✅ ما تم إنجازه

### 1. الجداول الجديدة

#### ✨ جدول `numbers` (محدث):
```
- معلومات الرقم الأساسية
- آخر بيانات استعلام يومي
- الاستهلاك اليومي (الفرق من الأمس)
- current_query_time + previous_query_time
```

#### ✨ جدول `daily_queries` (جديد):
```
- سجل تاريخي يومي لكل استعلام
- سجل واحد لكل رقم في اليوم
- يحتوي على raw_data للرجوع
```

### 2. الدوال الجديدة

**في `number_daily_updater.py`**:
- ✅ `update_number_and_save_daily()` - دالة شاملة
- ✅ `format_daily_report_from_numbers()` - تقرير من البيانات المخزنة
- ✅ `get_consumption_trend()` - تحليل الاتجاه
- ✅ `compare_consumption_with_yesterday()` - مقارنة يومية
- ✅ `get_number_history()` - التاريخ الكامل

### 3. الاستعلام التلقائي (محدث)

**في `app.py` → `auto_query_scheduler()`**:
```
✅ يستعلم الأرقام من API
✅ يحدث جدول numbers
✅ يحفظ في daily_queries
✅ يرسل تقرير من البيانات المخزنة
```

---

## 🎬 خطوات التشغيل

### الخطوة 1: تشغيل Migrations

```bash
# في terminal
cd c:\Users\HASRIAN TOPTECH\Desktop\systems\whatsappnewbot1

# تحديث جدول numbers
python migrate_numbers_table.py

# إنشاء جدول daily_queries
python create_daily_queries_table.py
```

**النتيجة المتوقعة**:
```
✅ تمت إضافة X أعمدة جديدة لجدول numbers
✅ تم إنشاء جدول daily_queries بنجاح
```

### الخطوة 2: تشغيل التطبيق

```bash
python app.py
```

**سيحدث تلقائياً**:
- 🔄 بدء الاستعلام التلقائي
- ⏰ التحقق كل دقيقة
- 📊 تحديث البيانات عند الموعد المحدد
- 📤 إرسال التقارير للعملاء

---

## 📖 كيف يعمل النظام الآن؟

### عند الاستعلام التلقائي اليومي:

```
1️⃣ الساعة تضرب موعد العميل (مثلاً 8:00 ص)
    ↓
2️⃣ النظام يستعلم كل أرقام العميل من API
    ↓
3️⃣ لكل رقم:
    • نقل الرصيد الحالي → previous_balance_gb
    • حفظ الرصيد الجديد → current_balance_gb
    • حساب الاستهلاك = previous - current
    • تحديد الحالة (active/warning/critical)
    ↓
4️⃣ حفظ سجل في daily_queries:
    • التاريخ: اليوم
    • البيانات: الرصيد، الاستهلاك، الحالة
    • raw_data: البيانات الخام
    ↓
5️⃣ إنشاء تقرير من جدول numbers
    ↓
6️⃣ إرسال التقرير عبر واتساب
    ↓
✅ تم!
```

---

## 🧪 اختبار النظام

### اختبار يدوي:

```python
from app import app, db, Number, Customer
from number_daily_updater import update_number_and_save_daily, get_number_history

with app.app_context():
    # 1. اختيار رقم
    number = Number.query.first()
    print(f"الرقم: {number.number}")
    
    # 2. استعلام
    from app import query_number
    result = query_number(number.number)
    
    # 3. تحديث النظام الجديد
    number, daily_record = update_number_and_save_daily(
        number,
        result.get('query', {}),
        raw_data=result
    )
    
    print(f"✅ الرصيد: {number.current_balance_gb} GB")
    print(f"✅ الاستهلاك: {number.daily_consumption_gb} GB")
    print(f"✅ السجل: {daily_record.query_date}")
    
    # 4. عرض التاريخ
    history = get_number_history(number.id, days=7)
    for record in history:
        print(f"{record.query_date}: {record.balance_gb} GB")
```

---

## 📊 عرض البيانات

### من لوحة التحكم (Dashboard):

#### الحالة الحالية:
```python
# عرض جميع الأرقام مع آخر بيانات
numbers = Number.query.all()
for num in numbers:
    print(f"{num.number}: {num.current_balance_gb} GB - {num.status}")
```

#### التاريخ والتحليل:
```python
from number_daily_updater import get_consumption_trend

# اتجاه الاستهلاك لآخر 7 أيام
trend = get_consumption_trend(number_id, days=7)
print(f"المتوسط اليومي: {trend['average_daily']} GB")
print(f"الاتجاه: {trend['trend']}")  # increasing/decreasing/stable
```

---

## 🎯 الفرق بين القديم والجديد

### ❌ النظام القديم:
```python
# استعلام
result = query_number(number)

# حفظ في Query فقط
add_query(number, result, is_daily=True)

# تقرير: يحتاج استعلام جديد أو البحث في Query
```

### ✅ النظام الجديد:
```python
# استعلام + تحديث + حفظ (كله في دالة واحدة!)
number_obj, daily_record = update_number_and_save_daily(
    number_obj, result, raw_data=result
)

# تقرير: مباشرة من البيانات المخزنة (سريع!)
report = format_daily_report_from_numbers(client_id)
```

---

## 🔍 استعلامات مفيدة

### الأرقام التي تحتاج انتباه:
```python
# الأرقام المنتهية أو القريبة من الانتهاء
critical = Number.query.filter(
    (Number.status == 'critical') | (Number.status == 'expired')
).all()

for num in critical:
    print(f"⚠️ {num.number}: {num.days_remaining} يوم متبقي")
```

### أعلى استهلاك يومي:
```python
top_consumers = Number.query.order_by(
    Number.daily_consumption_gb.desc()
).limit(5).all()

for num in top_consumers:
    print(f"📊 {num.number}: {num.daily_consumption_gb} GB/يوم")
```

### إحصائيات عميل:
```python
from number_daily_updater import get_daily_consumption_summary

summary = get_daily_consumption_summary(client_id)
print(f"إجمالي الاستهلاك: {summary['total_daily_consumption']} GB")
print(f"خطوط نشطة: {summary['active_count']}")
print(f"خطوط حرجة: {summary['critical_count']}")
```

---

## 🐛 حل المشاكل

### المشكلة: الاستعلام التلقائي لا يعمل

**الحل**:
```python
# التحقق من الحالة
from app import auto_query_running
print(f"الحالة: {auto_query_running}")

# التحقق من العملاء المفعلين
customers = Customer.query.filter_by(auto_query_enabled=True).all()
print(f"عملاء مفعلين: {len(customers)}")

for c in customers:
    print(f"  {c.name}: {c.auto_query_time}")
```

### المشكلة: خطأ في الاستيراد

**الحل**:
```bash
# تأكد من أن الملف موجود
ls number_daily_updater.py

# أعد تشغيل التطبيق
python app.py
```

---

## ✨ الميزات الجديدة المتاحة

1. **📊 تحليل الاتجاه**: معرفة إذا كان الاستهلاك يزيد أو يقل
2. **📈 الرسوم البيانية**: يمكن بناءها من `daily_queries`
3. **⚡ تقارير سريعة**: من البيانات المخزنة بدون استعلام
4. **🔍 مقارنات**: اليوم مع الأمس، هذا الأسبوع مع الماضي
5. **💾 أرشيف منظم**: سجل يومي واضح وسهل البحث

---

## 📞 الدعم

**في حالة وجود مشاكل**:
1. تحقق من الـ console للأخطاء
2. تأكد من تشغيل migrations
3. تحقق من وجود البيانات في الجداول

**ملاحظة**: النظام القديم (جدول Query) ما زال يعمل للتوافق، لكن يُفضل استخدام النظام الجديد.

---

**تم التحديث**: 2025-10-19
**الإصدار**: 2.1
