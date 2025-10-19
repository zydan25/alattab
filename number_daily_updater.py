"""
وظائف تحديث بيانات جدول الأرقام من الاستعلام اليومي
+ حفظ سجل يومي في جدول DailyQuery
"""

from datetime import datetime, date
from app import db, Number, Package, DailyQuery
import json


def handle_query_error(number_obj, error_message="خطأ في الاستعلام"):
    """
    معالجة حالة فشل الاستعلام - حفظ بيانات بحالة خطأ
    
    Args:
        number_obj: كائن Number من قاعدة البيانات
        error_message: رسالة الخطأ
    
    Returns:
        Number: الكائن مع بيانات الخطأ
    """
    print(f"\n      ⚠️ [معالجة خطأ] {error_message}")
    
    # حفظ البيانات السابقة إلى previous
    if number_obj.current_balance_gb is not None:
        number_obj.previous_balance_gb = number_obj.current_balance_gb
        number_obj.previous_query_time = number_obj.current_query_time
    
    # وضع قيم افتراضية (أصفار) للبيانات الحالية
    number_obj.current_balance_gb = 0.0
    number_obj.package_value = 0.0
    number_obj.current_query_time = datetime.utcnow()
    number_obj.amount_consumed = 0.0
    number_obj.amount_remaining = 0.0
    number_obj.daily_consumption_gb = 0.0
    
    # تعيين الحالة كخطأ
    number_obj.status = "error"
    number_obj.notes = error_message
    
    print(f"      ✅ تم حفظ حالة الخطأ: {error_message}")
    print(f"      📊 جميع الحقول = 0.0")
    print(f"      📝 الحالة: error")
    
    return number_obj


def update_number_from_daily_query(number_obj, query_result):
    """
    تحديث بيانات الرقم في جدول numbers من نتيجة الاستعلام اليومي
    
    المنطق:
    1. نقل البيانات الحالية إلى previous
    2. تحديث البيانات الحالية من الاستعلام الجديد
    3. حساب الاستهلاك اليومي (الفرق من الأمس)
    
    Args:
        number_obj: كائن Number من قاعدة البيانات
        query_result: نتيجة الاستعلام (dict) تحتوي على البيانات الجديدة
    
    Returns:
        Number: الكائن المحدث
    """
    
    print(f"\n      🔍 [DEBUG] بداية update_number_from_daily_query")
    print(f"      📥 query_result المستلم: {query_result}")
    print(f"      🔢 الرصيد الحالي قبل التحديث: {number_obj.current_balance_gb}")
    
    # ====== الخطوة 1: حفظ البيانات الحالية كـ "سابقة" ======
    if number_obj.current_balance_gb:
        number_obj.previous_balance_gb = number_obj.current_balance_gb
        number_obj.previous_query_time = number_obj.current_query_time
        print(f"      ✅ تم حفظ الرصيد السابق: {number_obj.previous_balance_gb} GB")
    
    # ====== الخطوة 2: تحديث البيانات الحالية من الاستعلام ======
    # استخدام .get() مع قيم افتراضية لضمان عدم اختفاء الحقول
    number_obj.current_balance_gb = float(query_result.get('avblnce_gb', 0.0) or 0.0)
    number_obj.package_value = float(query_result.get('baga_amount', 0.0) or 0.0)
    
    # حفظ الوقت السابق قبل التحديث
    previous_time = number_obj.current_query_time
    number_obj.current_query_time = datetime.utcnow()
    
    print(f"      ✅ تحديث الرصيد الجديد: {number_obj.current_balance_gb} GB")
    print(f"      ✅ قيمة الباقة: {number_obj.package_value} ريال")
    
    # عرض الأوقات بتنسيق جميل
    if previous_time:
        print(f"      🕐 الوقت السابق: {previous_time.strftime('%Y-%m-%d %I:%M:%S %p')}")
    print(f"      🕑 الوقت الحالي: {number_obj.current_query_time.strftime('%Y-%m-%d %I:%M:%S %p')}")
    
    # حساب الفارق الزمني
    if previous_time:
        time_diff = number_obj.current_query_time - previous_time
        hours = time_diff.total_seconds() / 3600
        if hours >= 24:
            days = hours / 24
            print(f"      ⏱️ الفارق الزمني: {days:.1f} يوم ({hours:.2f} ساعة)")
        elif hours >= 1:
            print(f"      ⏱️ الفارق الزمني: {hours:.2f} ساعة")
        else:
            minutes = hours * 60
            print(f"      ⏱️ الفارق الزمني: {minutes:.0f} دقيقة")
    
    # تاريخ الانتهاء والأيام المتبقية
    if query_result.get('expdate'):
        expdate_value = query_result['expdate']
        # تحويل string إلى datetime إذا لزم الأمر
        if isinstance(expdate_value, str):
            from dateutil import parser
            try:
                number_obj.expiry_date = parser.parse(expdate_value)
            except:
                # إذا فشل، استخدم datetime.fromisoformat
                try:
                    number_obj.expiry_date = datetime.fromisoformat(expdate_value.replace('Z', '+00:00'))
                except:
                    print(f"      ⚠️ خطأ في تحويل التاريخ: {expdate_value}")
                    number_obj.expiry_date = None
        else:
            number_obj.expiry_date = expdate_value
            
        number_obj.days_remaining = query_result.get('days_remaining', 0)
        print(f"      ✅ تاريخ الانتهاء: {number_obj.expiry_date}")
        print(f"      ✅ الأيام المتبقية: {number_obj.days_remaining}")
    
    # المبالغ المالية - مع قيم افتراضية
    number_obj.amount_consumed = float(query_result.get('amount_consumed', 0.0) or 0.0)
    number_obj.amount_remaining = float(query_result.get('amount_remaining', 0.0) or 0.0)
    
    print(f"      💰 المبلغ المستهلك: {number_obj.amount_consumed} ريال")
    print(f"      💵 المبلغ المتبقي: {number_obj.amount_remaining} ريال")
    
    # ====== الخطوة 3: حساب الاستهلاك اليومي ======
    print(f"\n      🧮 حساب الاستهلاك اليومي...")
    print(f"      📊 الرصيد السابق: {number_obj.previous_balance_gb} GB")
    print(f"      📊 الرصيد الحالي: {number_obj.current_balance_gb} GB")
    
    if number_obj.previous_balance_gb and number_obj.current_balance_gb:
        # التحقق من حالة التعبئة
        if number_obj.current_balance_gb > number_obj.previous_balance_gb:
            # تم التسديد - نحسب الاستهلاك الحقيقي
            print(f"      🔄 حالة: تم التسديد (الرصيد زاد)")
            # الاستهلاك = الرصيد السابق + حجم الباقة الجديدة - الرصيد الحالي
            package = Package.query.filter_by(value=int(number_obj.package_value)).first()
            if package:
                consumption = number_obj.previous_balance_gb + package.volume - number_obj.current_balance_gb
                number_obj.daily_consumption_gb = max(consumption, 0.0)
                number_obj.notes = "تم التسديد اليوم"
                print(f"      ✅ الاستهلاك المحسوب: {number_obj.daily_consumption_gb} GB")
            else:
                number_obj.daily_consumption_gb = 0.0
                number_obj.notes = "تم التسديد (لم يتم العثور على الباقة)"
                print(f"      ⚠️ لم يتم العثور على الباقة")
        else:
            # استهلاك عادي
            print(f"      ➡️ حالة: استهلاك عادي")
            number_obj.daily_consumption_gb = number_obj.previous_balance_gb - number_obj.current_balance_gb
            number_obj.notes = None
            print(f"      ✅ الاستهلاك = {number_obj.previous_balance_gb} - {number_obj.current_balance_gb} = {number_obj.daily_consumption_gb} GB")
    else:
        # أول استعلام - لا يوجد استهلاك
        print(f"      🆕 حالة: أول استعلام")
        number_obj.daily_consumption_gb = 0.0
        number_obj.notes = "أول استعلام"
    
    # ====== الخطوة 4: تحديد الحالة ======
    print(f"\n      🎯 تحديد الحالة...")
    days_remaining = number_obj.days_remaining or 0
    
    if days_remaining <= 0:
        number_obj.status = "expired"
        print(f"      ❌ الحالة: منتهية")
    elif days_remaining == 1:
        number_obj.status = "critical"
        if not number_obj.notes:
            number_obj.notes = "تنتهي غداً"
        print(f"      🔴 الحالة: حرجة (ينتهي غداً)")
    elif days_remaining <= 3:
        number_obj.status = "warning"
        if not number_obj.notes:
            number_obj.notes = f"باقي {days_remaining} أيام"
        print(f"      ⚠️ الحالة: تحذير (باقي {days_remaining} أيام)")
    elif number_obj.current_balance_gb < 1.0:
        number_obj.status = "warning"
        if not number_obj.notes:
            number_obj.notes = "الرصيد منخفض"
        print(f"      ⚠️ الحالة: تحذير (رصيد منخفض)")
    else:
        number_obj.status = "active"
        print(f"      ✅ الحالة: نشط")
    
    print(f"      📝 الملاحظات: {number_obj.notes}")
    print(f"      🏁 [DEBUG] نهاية update_number_from_daily_query\n")
    
    return number_obj


def save_daily_query_record(number_obj, query_result, raw_data=None):
    """
    حفظ سجل الاستعلام اليومي في جدول DailyQuery
    
    Args:
        number_obj: كائن Number من قاعدة البيانات
        query_result: نتيجة الاستعلام (dict)
        raw_data: البيانات الخام (اختياري)
    
    Returns:
        DailyQuery: كائن السجل اليومي المحفوظ
    """
    today = date.today()
    
    # التحقق من وجود سجل لهذا اليوم
    existing = DailyQuery.query.filter_by(
        number_id=number_obj.id,
        query_date=today
    ).first()
    
    if existing:
        # تحديث السجل الموجود
        daily_record = existing
    else:
        # إنشاء سجل جديد
        daily_record = DailyQuery(
            number_id=number_obj.id,
            query_date=today
        )
    
    # ملء البيانات
    daily_record.query_time = datetime.utcnow()
    daily_record.package_value = number_obj.package_value
    daily_record.balance_gb = number_obj.current_balance_gb
    daily_record.daily_consumption_gb = number_obj.daily_consumption_gb
    daily_record.expiry_date = number_obj.expiry_date
    daily_record.days_remaining = number_obj.days_remaining
    daily_record.amount_consumed = number_obj.amount_consumed
    daily_record.amount_remaining = number_obj.amount_remaining
    daily_record.status = number_obj.status
    daily_record.notes = number_obj.notes
    
    # حفظ البيانات الخام
    if raw_data:
        if isinstance(raw_data, dict):
            daily_record.raw_data = json.dumps(raw_data, ensure_ascii=False)
        else:
            daily_record.raw_data = str(raw_data)
    
    # حفظ في قاعدة البيانات
    if not existing:
        db.session.add(daily_record)
    
    db.session.commit()
    
    return daily_record


def update_number_and_save_daily(number_obj, query_result, raw_data=None):
    """
    دالة مجمعة: تحديث جدول الأرقام + حفظ السجل اليومي
    
    Args:
        number_obj: كائن Number من قاعدة البيانات
        query_result: نتيجة الاستعلام (dict)
        raw_data: البيانات الخام (اختياري)
    
    Returns:
        tuple: (Number, DailyQuery)
    """
    # 1. تحديث جدول الأرقام
    number_obj = update_number_from_daily_query(number_obj, query_result)
    
    # 2. حفظ السجل اليومي
    daily_record = save_daily_query_record(number_obj, query_result, raw_data)
    
    return number_obj, daily_record


def get_daily_consumption_summary(client_id):
    """
    الحصول على ملخص الاستهلاك اليومي لجميع أرقام العميل
    
    Args:
        client_id: معرف العميل
    
    Returns:
        dict: ملخص يحتوي على الإحصائيات
    """
    from app import Number
    
    numbers = Number.query.filter_by(client_id=client_id).all()
    
    summary = {
        'total_numbers': len(numbers),
        'total_current_balance': 0.0,
        'total_daily_consumption': 0.0,
        'total_package_value': 0.0,
        'total_amount_consumed': 0.0,
        'total_amount_remaining': 0.0,
        'active_count': 0,
        'warning_count': 0,
        'critical_count': 0,
        'expired_count': 0,
        'error_count': 0,
        'numbers_details': []
    }
    
    for num in numbers:
        summary['total_current_balance'] += num.current_balance_gb or 0.0
        summary['total_daily_consumption'] += num.daily_consumption_gb or 0.0
        summary['total_package_value'] += num.package_value or 0.0
        summary['total_amount_consumed'] += num.amount_consumed or 0.0
        summary['total_amount_remaining'] += num.amount_remaining or 0.0
        
        # عد الحالات
        if num.status == 'active':
            summary['active_count'] += 1
        elif num.status == 'warning':
            summary['warning_count'] += 1
        elif num.status == 'critical':
            summary['critical_count'] += 1
        elif num.status == 'expired':
            summary['expired_count'] += 1
        elif num.status == 'error':
            summary['error_count'] += 1
        
        # تفاصيل كل رقم
        summary['numbers_details'].append({
            'number': num.number,
            'balance': num.current_balance_gb,
            'consumption': num.daily_consumption_gb,
            'days_remaining': num.days_remaining,
            'status': num.status,
            'notes': num.notes
        })
    
    return summary


def format_daily_report_from_numbers(client_id):
    """
    إنشاء تقرير يومي من بيانات جدول الأرقام (بدلاً من الاستعلام المباشر)
    
    Args:
        client_id: معرف العميل
    
    Returns:
        tuple: (
            str: التقرير المنسق,
            list: one_d - مصفوفة أحادية (معلومات العميل، التاريخ، الوقت),
            list: tow_d - مصفوفة ثنائية للجدول (العناوين + الصفوف + الإجماليات)
        )
    """
    from app import Customer, Number
    
    customer = Customer.query.get(client_id)
    if not customer:
        return "❌ العميل غير موجود", [], []
    
    numbers = Number.query.filter_by(client_id=client_id).all()
    
    if not numbers:
        return "⚠️ لا توجد أرقام مسجلة", [], []
    
    lines = ["📊 *تقرير الخطوط اليومي من نظام العطاب اكسبرس* 📊\n"]
    lines.append(f"👤 *العميل*: {customer.name}\n")
    
    # إنشاء المصفوفات للـ PDF
    one_d = []  # مصفوفة أحادية للمعلومات الإضافية
    tow_d = []  # مصفوفة ثنائية للجدول الرئيسي
    
    # إضافة معلومات العميل في one_d
    one_d.append(f"العميل: {customer.name}")
    one_d.append(f"الواتساب: {customer.whatsapp}")
    
    # إضافة العناوين في tow_d
    tow_d.append(['#','الرقم','الرصيد','قيمة الباقة','تاريخ الانتهاء','الأيام','الاستهلاك(ي)','المستهلك','المتبقي','الحالة','اللون'])
    
    for i, num in enumerate(numbers, 1):
        # إنشاء سطر جديد للرقم
        row_data = []
        row_data.append(f"{i}")  # رقم التسلسل
        
        lines.append(f"🔢 *الرقم {i}*")
        lines.append(f"📱 *الرقم*: {num.number}")
        row_data.append(num.number)  # الرقم
        lines.append("─" * 30)
        
        # البيانات الأساسية
        lines.append(f"💳 *الرصيد الحالي*: {num.current_balance_gb:.2f} جيجا")
        row_data.append(f"{num.current_balance_gb:.2f}")  # الرصيد
        
        lines.append(f"📦 *قيمة الباقة*: {num.package_value:.0f} ريال")
        row_data.append(f"{num.package_value:.0f}")  # قيمة الباقة
        
        # التواريخ
        if num.expiry_date:
            expiry_str = num.expiry_date.strftime('%Y-%m-%d')
            lines.append(f"📅 *تاريخ الانتهاء*: {expiry_str}")
            row_data.append(expiry_str)  # تاريخ الانتهاء
            
            lines.append(f"⏰ *الأيام المتبقية*: {num.days_remaining or 0}")
            row_data.append(f"{num.days_remaining or 0}")  # الأيام
        else:
            row_data.append("--")  # تاريخ الانتهاء
            row_data.append("0")  # الأيام
        
        # الاستهلاك
        lines.append(f"📉 *الاستهلاك اليومي*: {num.daily_consumption_gb:.2f} جيجا")
        row_data.append(f"{num.daily_consumption_gb:.2f}")  # الاستهلاك اليومي
        
        # المبالغ
        lines.append(f"💰 *المبلغ المستهلك*: {num.amount_consumed:.2f} ريال")
        row_data.append(f"{num.amount_consumed:.2f}")  # المستهلك
        
        lines.append(f"💵 *المبلغ المتبقي*: {num.amount_remaining:.2f} ريال")
        row_data.append(f"{num.amount_remaining:.2f}")  # المتبقي
        
        # الحالة
        status_emoji = {
            'active': '✅',
            'warning': '⚠️',
            'critical': '🔴',
            'expired': '❌',
            'error': '🚫'
        }
        emoji = status_emoji.get(num.status, 'ℹ️')
        
        # ترجمة الحالة للعربية
        status_ar = {
            'active': 'نشط',
            'warning': 'تحذير',
            'critical': 'حرج',
            'expired': 'منتهي',
            'error': 'خطأ في الاستعلام'
        }
        status_text = status_ar.get(num.status, num.status)
        
        # اللون للـ PDF
        color_map = {
            'active': 'lightgreen',
            'warning': 'yellow',
            'critical': 'orange',
            'expired': 'red',
            'error': 'lightyellow'
        }
        color = color_map.get(num.status, 'white')
        
        lines.append(f"{emoji} *الحالة*: {status_text}")
        
        # النص المجمّع للحالة + الملاحظات
        q = f"{emoji} {status_text}"
        if num.notes:
            lines.append(f"📝 *ملاحظة*: {num.notes}")
            q += f"\n📝 {num.notes}"
        
        # إضافة الحالة واللون
        row_data.append(q)  # الحالة
        row_data.append(color)  # اللون
        
        # إضافة السطر إلى المصفوفة
        tow_d.append(row_data)
        
        lines.append("")  # سطر فارغ
    
    # ملخص إجمالي
    summary = get_daily_consumption_summary(client_id)
    
    lines.append("\n" + "═" * 40)
    lines.append("📈 *الملخص الإجمالي* 📈")
    lines.append("═" * 40)
    lines.append(f"📊 *إجمالي الخطوط*: {summary['total_numbers']}")
    lines.append("")
    lines.append("💎 *إجماليات البيانات:*")
    lines.append(f"   💰 *إجمالي الرصيد*: {summary['total_current_balance']:.2f} GB")
    lines.append(f"   📉 *إجمالي الاستهلاك اليومي*: {summary['total_daily_consumption']:.2f} GB")
    lines.append("")
    lines.append("💵 *إجماليات المبالغ:*")
    lines.append(f"   📦 *إجمالي قيمة الباقات*: {summary['total_package_value']:.2f} ريال")
    lines.append(f"   🔻 *إجمالي المبالغ المستهلكة*: {summary['total_amount_consumed']:.2f} ريال")
    lines.append(f"   🔺 *إجمالي المبالغ المتبقية*: {summary['total_amount_remaining']:.2f} ريال")
    lines.append("")
    lines.append("📊 *حالة الخطوط:*")
    lines.append(f"   ✅ *خطوط نشطة*: {summary['active_count']}")
    lines.append(f"   ⚠️ *خطوط تحذير*: {summary['warning_count']}")
    lines.append(f"   🔴 *خطوط حرجة*: {summary['critical_count']}")
    lines.append(f"   ❌ *خطوط منتهية*: {summary['expired_count']}")
    if summary['error_count'] > 0:
        lines.append(f"   🚫 *خطوط بها أخطاء*: {summary['error_count']}")
    
    # إضافة سطر الإجماليات إلى المصفوفة
    totals_row = []
    totals_row.append(summary['total_numbers'])  # #
    totals_row.append('الإجماليات')  # الرقم
    totals_row.append(f"{summary['total_current_balance']:.2f}")  # الرصيد
    totals_row.append(f"{summary['total_package_value']:.2f}")  # قيمة الباقة
    totals_row.append('--')  # تاريخ الانتهاء
    totals_row.append('--')  # الأيام
    totals_row.append(f"{summary['total_daily_consumption']:.2f}")  # الاستهلاك اليومي
    totals_row.append(f"{summary['total_amount_consumed']:.2f}")  # المستهلك
    totals_row.append(f"{summary['total_amount_remaining']:.2f}")  # المتبقي
    totals_row.append(f"⚠️ قريباً: {summary['warning_count'] + summary['critical_count']}")  # الحالة
    totals_row.append('cyan')  # اللون
    tow_d.append(totals_row)
    
    # ═══════════════════════════════════════
    # قسم الأوقات والفروقات الزمنية
    # ═══════════════════════════════════════
    lines.append("\n" + "═" * 40)
    lines.append("⏰ *معلومات التوقيت* ⏰")
    lines.append("═" * 40)
    
    # البحث عن أول رقم له بيانات توقيت صحيحة
    reference_number = None
    for num in numbers:
        # نأخذ أول رقم له current_query_time و previous_query_time
        if num.current_query_time and num.previous_query_time and num.status != 'error':
            reference_number = num
            break
    
    # إذا لم نجد رقم بدون خطأ، نأخذ أي رقم له بيانات توقيت
    if not reference_number:
        for num in numbers:
            if num.current_query_time:
                reference_number = num
                break
    
    if reference_number and reference_number.current_query_time:
        # عرض وقت الاستعلام الحالي
        lines.append(f"🕐 *وقت الاستعلام الحالي*:")
        lines.append(f"   📅 {reference_number.current_query_time.strftime('%Y-%m-%d')}")
        lines.append(f"   🕒 {reference_number.current_query_time.strftime('%I:%M:%S %p')}")
        
        # عرض وقت الاستعلام السابق إذا كان موجوداً
        if reference_number.previous_query_time:
            lines.append(f"\n🕑 *وقت الاستعلام السابق*:")
            lines.append(f"   📅 {reference_number.previous_query_time.strftime('%Y-%m-%d')}")
            lines.append(f"   🕒 {reference_number.previous_query_time.strftime('%I:%M:%S %p')}")
            
            # حساب وعرض الفارق الزمني
            time_diff = reference_number.current_query_time - reference_number.previous_query_time
            diff_hours = time_diff.total_seconds() / 3600
            
            lines.append(f"\n⏱️ *الفارق الزمني*:")
            if diff_hours >= 24:
                days = diff_hours / 24
                hours = diff_hours % 24
                lines.append(f"   📊 {days:.0f} يوم و {hours:.1f} ساعة")
            elif diff_hours >= 1:
                lines.append(f"   📊 {diff_hours:.1f} ساعة")
            else:
                minutes = diff_hours * 60
                lines.append(f"   📊 {minutes:.0f} دقيقة")
        else:
            lines.append("\nℹ️ *هذا هو الاستعلام الأول*")
    else:
        lines.append("ℹ️ *لا توجد بيانات توقيت متاحة*")
    
    # التاريخ والوقت الحالي
    now = datetime.now()
    lines.append("\n" + "─" * 40)
    lines.append(f"📅 *تاريخ التقرير*: {now.strftime('%Y-%m-%d')}")
    lines.append(f"🕐 *وقت التقرير*: {now.strftime('%I:%M:%S %p')}")
    lines.append("\n📞 للاشتراك التواصل على الرقم: *+967779751181*")
    
    # إضافة التاريخ والوقت إلى one_d
    one_d.append(f"📅 التاريخ: {now.strftime('%Y-%m-%d')}")
    one_d.append(f"🕐 الوقت: {now.strftime('%I:%M:%S %p')}")
    one_d.append(f"📆 اليوم: {now.strftime('%A')}")
    
    # إرجاع التقرير النصي والمصفوفات للـ PDF
    return "\n".join(lines), one_d, tow_d


def get_number_history(number_id, days=7):
    """
    الحصول على سجل الاستعلامات اليومية لرقم معين
    
    Args:
        number_id: معرف الرقم
        days: عدد الأيام (افتراضي 7)
    
    Returns:
        list: قائمة السجلات اليومية
    """
    from datetime import timedelta
    
    start_date = date.today() - timedelta(days=days)
    
    records = DailyQuery.query.filter(
        DailyQuery.number_id == number_id,
        DailyQuery.query_date >= start_date
    ).order_by(DailyQuery.query_date.desc()).all()
    
    return records


def get_consumption_trend(number_id, days=7):
    """
    الحصول على اتجاه الاستهلاك لرقم معين
    
    Args:
        number_id: معرف الرقم
        days: عدد الأيام
    
    Returns:
        dict: إحصائيات الاتجاه
    """
    records = get_number_history(number_id, days)
    
    if not records:
        return {
            'average_daily': 0.0,
            'max_daily': 0.0,
            'min_daily': 0.0,
            'total': 0.0,
            'days_count': 0,
            'trend': 'stable'
        }
    
    consumptions = [r.daily_consumption_gb for r in records if r.daily_consumption_gb]
    
    if not consumptions:
        return {
            'average_daily': 0.0,
            'max_daily': 0.0,
            'min_daily': 0.0,
            'total': 0.0,
            'days_count': 0,
            'trend': 'stable'
        }
    
    avg = sum(consumptions) / len(consumptions)
    
    # تحديد الاتجاه (مقارنة أول 3 أيام مع آخر 3 أيام)
    trend = 'stable'
    if len(consumptions) >= 6:
        recent_avg = sum(consumptions[:3]) / 3
        old_avg = sum(consumptions[-3:]) / 3
        
        if recent_avg > old_avg * 1.2:
            trend = 'increasing'
        elif recent_avg < old_avg * 0.8:
            trend = 'decreasing'
    
    return {
        'average_daily': round(avg, 2),
        'max_daily': round(max(consumptions), 2),
        'min_daily': round(min(consumptions), 2),
        'total': round(sum(consumptions), 2),
        'days_count': len(consumptions),
        'trend': trend
    }


def get_client_daily_records(client_id, query_date=None):
    """
    الحصول على جميع السجلات اليومية لعميل معين في تاريخ محدد
    
    Args:
        client_id: معرف العميل
        query_date: التاريخ (افتراضي اليوم)
    
    Returns:
        list: قائمة السجلات اليومية
    """
    if query_date is None:
        query_date = date.today()
    
    # الحصول على أرقام العميل
    from app import Number
    number_ids = [n.id for n in Number.query.filter_by(client_id=client_id).all()]
    
    if not number_ids:
        return []
    
    # الحصول على السجلات اليومية
    records = DailyQuery.query.filter(
        DailyQuery.number_id.in_(number_ids),
        DailyQuery.query_date == query_date
    ).all()
    
    return records


def compare_consumption_with_yesterday(number_id):
    """
    مقارنة استهلاك اليوم مع الأمس
    
    Args:
        number_id: معرف الرقم
    
    Returns:
        dict: مقارنة الاستهلاك
    """
    from datetime import timedelta
    
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    today_record = DailyQuery.query.filter_by(
        number_id=number_id,
        query_date=today
    ).first()
    
    yesterday_record = DailyQuery.query.filter_by(
        number_id=number_id,
        query_date=yesterday
    ).first()
    
    result = {
        'today': today_record.daily_consumption_gb if today_record else 0.0,
        'yesterday': yesterday_record.daily_consumption_gb if yesterday_record else 0.0,
        'difference': 0.0,
        'percentage_change': 0.0,
        'status': 'same'
    }
    
    if today_record and yesterday_record:
        diff = result['today'] - result['yesterday']
        result['difference'] = round(diff, 2)
        
        if result['yesterday'] > 0:
            change = (diff / result['yesterday']) * 100
            result['percentage_change'] = round(change, 2)
            
            if change > 20:
                result['status'] = 'increased_significantly'
            elif change > 0:
                result['status'] = 'increased'
            elif change < -20:
                result['status'] = 'decreased_significantly'
            elif change < 0:
                result['status'] = 'decreased'
    
    return result
