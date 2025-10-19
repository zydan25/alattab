# 📚 دليل الاستخدام - نظام الاستعلام اليومي المحسّن

## 🎯 نظرة عامة

النظام الجديد يتكون من:
1. **جدول `numbers`**: يحتوي على آخر بيانات استعلام يومي (الحالة الحالية)
2. **جدول `daily_queries`**: سجل تاريخي يومي لكل الاستعلامات (أرشيف كامل)

## 📋 البنية الجديدة

### جدول الأرقام (numbers)

```
المعلومات الأساسية:
├── id
├── client_id
├── number
└── type

بيانات الباقة والرصيد:
├── package_value (قيمة الباقة بالريال)
└── current_balance_gb (الرصيد الحالي بالجيجا)

التواريخ والوقت:
├── expiry_date (تاريخ الانتهاء)
├── days_remaining (الأيام المتبقية)
├── current_query_time (وقت الاستعلام الحالي)
└── previous_query_time (وقت الاستعلام السابق)

الاستهلاك اليومي:
├── previous_balance_gb (الرصيد الأمس)
└── daily_consumption_gb (الاستهلاك اليومي)

المبالغ المالية:
├── amount_consumed (المبلغ المستهلك)
└── amount_remaining (المبلغ المتبقي)

الحالة:
├── status (active, warning, critical, expired)
└── notes (ملاحظات تلقائية)
```

### جدول الاستعلامات اليومية (daily_queries)

```
المعلومات الأساسية:
├── id
├── number_id (FK → numbers.id)
├── query_date (تاريخ اليوم فقط)
└── query_time (الوقت الكامل)

البيانات اليومية:
├── package_value
├── balance_gb
├── daily_consumption_gb
├── expiry_date
├── days_remaining
├── amount_consumed
├── amount_remaining
├── status
├── notes
└── raw_data (البيانات الخام للرجوع)

القيود:
└── UNIQUE(number_id, query_date) ← سجل واحد فقط لكل رقم في اليوم
```

## 🚀 خطوات التطبيق

### 1. تشغيل Migrations

```bash
# الخطوة 1: تحديث جدول numbers
python migrate_numbers_table.py

# الخطوة 2: إنشاء جدول daily_queries
python create_daily_queries_table.py
```

هذا سيقوم بـ:
- إضافة الحقول الجديدة لجدول `numbers` الموجود
- إنشاء جدول `daily_queries` الجديد مع الفهارس

### 2. استخدام في الاستعلام اليومي

#### قبل (الطريقة القديمة):
```python
# كان يتم الاستعلام ثم الحفظ في Query فقط
result = query_number(number)
query_obj = add_query(number, result, is_daily=True)
```

#### بعد (الطريقة الجديدة - مع جدول DailyQuery):
```python
from number_daily_updater import update_number_and_save_daily

# 1. استعلام الرقم
result = query_number(number)

# 2. البحث عن الرقم في جدول numbers
number_obj = Number.query.filter_by(number=number).first()

# 3. تحديث numbers + حفظ في daily_queries (دالة واحدة!)
if number_obj:
    number_obj, daily_record = update_number_and_save_daily(
        number_obj, 
        result,
        raw_data=result  # البيانات الخام للرجوع
    )
    
    print(f"✅ تم التحديث - الاستهلاك اليومي: {number_obj.daily_consumption_gb} GB")
    print(f"📝 تم حفظ السجل اليومي: {daily_record.query_date}")

# 4. (اختياري) حفظ في Query للسجل الكامل
# query_obj = add_query(number, result, is_daily=True)
```

#### أو خطوة بخطوة:
```python
from number_daily_updater import (
    update_number_from_daily_query,
    save_daily_query_record
)

# 1. تحديث جدول numbers
number_obj = update_number_from_daily_query(number_obj, result)
db.session.commit()

# 2. حفظ السجل اليومي
daily_record = save_daily_query_record(number_obj, result, raw_data=result)
```

### 3. إنشاء تقرير من جدول الأرقام

#### بدلاً من استعلام الأرقام كل مرة:
```python
from number_daily_updater import format_daily_report_from_numbers

# مباشرة من البيانات المحفوظة
report = format_daily_report_from_numbers(client_id)
send_whatsapp(phone, report)
```

### 4. الحصول على ملخص الاستهلاك

```python
from number_daily_updater import get_daily_consumption_summary

summary = get_daily_consumption_summary(client_id)

print(f"إجمالي الأرقام: {summary['total_numbers']}")
print(f"الاستهلاك اليومي: {summary['total_daily_consumption']} GB")
print(f"الخطوط النشطة: {summary['active_count']}")
print(f"الخطوط الحرجة: {summary['critical_count']}")
```

### 5. العمل مع السجلات اليومية (DailyQuery)

#### الحصول على تاريخ رقم لآخر 7 أيام:
```python
from number_daily_updater import get_number_history

history = get_number_history(number_id, days=7)

for record in history:
    print(f"{record.query_date}: {record.balance_gb} GB - استهلاك: {record.daily_consumption_gb} GB")
```

#### تحليل اتجاه الاستهلاك:
```python
from number_daily_updater import get_consumption_trend

trend = get_consumption_trend(number_id, days=7)

print(f"متوسط الاستهلاك اليومي: {trend['average_daily']} GB")
print(f"أعلى استهلاك: {trend['max_daily']} GB")
print(f"أقل استهلاك: {trend['min_daily']} GB")
print(f"الإجمالي: {trend['total']} GB")
print(f"الاتجاه: {trend['trend']}")  # increasing, decreasing, stable
```

#### مقارنة اليوم مع الأمس:
```python
from number_daily_updater import compare_consumption_with_yesterday

comparison = compare_consumption_with_yesterday(number_id)

print(f"استهلاك اليوم: {comparison['today']} GB")
print(f"استهلاك الأمس: {comparison['yesterday']} GB")
print(f"الفرق: {comparison['difference']} GB")
print(f"نسبة التغيير: {comparison['percentage_change']}%")
print(f"الحالة: {comparison['status']}")  # increased, decreased, same
```

#### الحصول على سجلات يوم معين لجميع أرقام عميل:
```python
from number_daily_updater import get_client_daily_records
from datetime import date

# سجلات اليوم
today_records = get_client_daily_records(client_id)

# سجلات تاريخ محدد
specific_date = date(2025, 10, 15)
records = get_client_daily_records(client_id, query_date=specific_date)

for record in records:
    print(f"الرقم {record.number_id}: {record.balance_gb} GB")
```

## 🔄 منطق حساب الاستهلاك اليومي

### حالة الاستهلاك العادي:
```
الرصيد الأمس: 50 GB
الرصيد اليوم: 45 GB
الاستهلاك = 50 - 45 = 5 GB ✅
```

### حالة التعبئة:
```
الرصيد الأمس: 5 GB
الرصيد اليوم: 30 GB (تم التسديد)
قيمة الباقة: 50 ريال → 30 GB

الاستهلاك = (5 + 30) - 30 = 5 GB ✅
الملاحظة: "تم التسديد اليوم"
```

## 📊 تحديث الاستعلام التلقائي

في دالة `auto_query_scheduler`:

```python
def auto_query_scheduler():
    while True:
        # ... الكود الموجود ...
        
        for customer in customers_to_query:
            numbers = Number.query.filter_by(client_id=customer.id).all()
            
            for number_obj in numbers:
                try:
                    # استعلام الرقم
                    result = query_number(number_obj.number)
                    
                    # تحديث جدول الأرقام
                    update_number_from_daily_query(number_obj, result)
                    db.session.commit()
                    
                except Exception as e:
                    print(f"خطأ في استعلام {number_obj.number}: {e}")
            
            # إرسال التقرير من البيانات المحفوظة
            report = format_daily_report_from_numbers(customer.id)
            send_whatsapp(customer.whatsapp, report)
```

## 🎁 المزايا

### ✅ قبل:
- استعلام مباشر في كل مرة
- بطء في التقارير
- حاجة للبحث في جدول Query

### ✨ بعد:
- بيانات محدثة يومياً في جدول numbers
- تقارير سريعة من البيانات المخزنة
- سهولة الوصول للاستهلاك اليومي
- حساب تلقائي للحالة والملاحظات

## 📝 ملاحظات مهمة

1. **جدول Query**: يمكن الاحتفاظ به للسجل التاريخي الكامل
2. **التحديث اليومي**: يتم تلقائياً عند الاستعلام اليومي
3. **البيانات القديمة**: الحقول القديمة محفوظة للتوافق المؤقت
4. **الأداء**: تحسن كبير لأن البيانات جاهزة

## 🔧 استعلامات مفيدة

### استعلامات جدول Numbers (الحالة الحالية):

#### الحصول على جميع الأرقام النشطة:
```python
active_numbers = Number.query.filter_by(status='active').all()
```

#### الأرقام التي تنتهي قريباً:
```python
critical_numbers = Number.query.filter(
    Number.days_remaining <= 3,
    Number.days_remaining > 0
).all()
```

#### أعلى استهلاك يومي حالياً:
```python
top_consumers = Number.query.order_by(
    Number.daily_consumption_gb.desc()
).limit(10).all()
```

#### إجمالي الاستهلاك اليومي لعميل:
```python
from sqlalchemy import func

total = db.session.query(
    func.sum(Number.daily_consumption_gb)
).filter_by(client_id=client_id).scalar()
```

### استعلامات جدول DailyQuery (السجل التاريخي):

#### إجمالي الاستهلاك لآخر 7 أيام:
```python
from datetime import date, timedelta
from sqlalchemy import func

start_date = date.today() - timedelta(days=7)

total = db.session.query(
    func.sum(DailyQuery.daily_consumption_gb)
).filter(
    DailyQuery.number_id == number_id,
    DailyQuery.query_date >= start_date
).scalar()
```

#### أعلى استهلاك يومي في الشهر:
```python
from datetime import date

first_day = date.today().replace(day=1)

top_day = DailyQuery.query.filter(
    DailyQuery.number_id == number_id,
    DailyQuery.query_date >= first_day
).order_by(DailyQuery.daily_consumption_gb.desc()).first()

print(f"أعلى استهلاك: {top_day.daily_consumption_gb} GB في {top_day.query_date}")
```

#### متوسط الاستهلاك اليومي لجميع أرقام عميل:
```python
from sqlalchemy import func
from datetime import date, timedelta

start_date = date.today() - timedelta(days=7)

# الحصول على أرقام العميل
number_ids = [n.id for n in Number.query.filter_by(client_id=client_id).all()]

avg = db.session.query(
    func.avg(DailyQuery.daily_consumption_gb)
).filter(
    DailyQuery.number_id.in_(number_ids),
    DailyQuery.query_date >= start_date
).scalar()

print(f"متوسط الاستهلاك: {avg:.2f} GB")
```

#### الأيام التي تجاوز فيها الاستهلاك حد معين:
```python
threshold = 5.0  # 5 GB

high_consumption_days = DailyQuery.query.filter(
    DailyQuery.number_id == number_id,
    DailyQuery.daily_consumption_gb > threshold
).order_by(DailyQuery.query_date.desc()).all()

for record in high_consumption_days:
    print(f"{record.query_date}: {record.daily_consumption_gb} GB")
```

## 🎯 التوصيات

### للاستعلام اليومي:
1. ✅ استخدم `update_number_and_save_daily()` - دالة واحدة تحدث كل شيء
2. ✅ سيتم تحديث جدول `numbers` (الحالة الحالية)
3. ✅ سيتم حفظ سجل في `daily_queries` (التاريخ اليومي)

### للتقارير:
1. ✅ استخدم `format_daily_report_from_numbers()` - تقارير من البيانات المخزنة
2. ⚠️ لا تستعلم الأرقام كل مرة - استخدم البيانات من `numbers`

### للتحليلات:
1. ✅ استخدم دوال التحليل مثل `get_consumption_trend()`
2. ✅ استخدم جدول `daily_queries` للرسوم البيانية والإحصائيات
3. 📊 يمكنك بناء dashboard كامل من `daily_queries`

### التنظيف:
1. 🗑️ يمكن حذف السجلات القديمة من `daily_queries` بعد فترة (مثلاً 90 يوم)
2. ⚡ جدول `numbers` دائماً يحتوي على آخر حالة فقط
3. 🔧 جدول `query` القديم يمكن إيقاف استخدامه تدريجياً

## 📊 الفرق بين الجداول الثلاثة

| الميزة | numbers | daily_queries | query (القديم) |
|--------|---------|---------------|----------------|
| الغرض | الحالة الحالية | السجل اليومي | السجل الكامل |
| عدد السجلات | رقم واحد = سجل واحد | رقم واحد = سجل لكل يوم | كل استعلام = سجل |
| الحجم | صغير جداً | متوسط | كبير جداً |
| الاستخدام | التقارير السريعة | التحليلات والإحصائيات | الأرشيف الكامل |
| التحديث | يومياً | يومياً | كل استعلام |
| الحذف | لا يُحذف | بعد 90 يوم (اختياري) | بعد سنة (اختياري) |

---

**آخر تحديث**: 2025-10-19
**الإصدار**: 2.1 (مع جدول DailyQuery)
