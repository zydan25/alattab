# استيراد المكتبات المطلوبة
import hashlib  # لتشفير كلمات المرور وإنشاء التوكن
import json     # للتعامل مع ملفات JSON والبيانات
import random   # لإنشاء أرقام عشوائية للمعاملات
import sqlite3  # للتعامل مع قاعدة البيانات
import string   # للتعامل مع النصوص والأحرف
from datetime import datetime, timedelta, timezone  # للتعامل مع التواريخ والأوقات
from pathlib import Path  # للتعامل مع مسارات الملفات
import re  # للتعامل مع التعبيرات النمطية
import json
from flask_migrate import Migrate
import os
import functools
#import db
import base64
import io
from flask_sqlalchemy import SQLAlchemy
import shutil
import time
import subprocess  # لتشغيل أوامر النظام
import threading   # للعمليات المتوازية
import psutil      # لفحص العمليات النشطة

import requests  # لإرسال طلبات HTTP
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_from_directory, send_file
from datetime import datetime , timedelta # إطار العمل Flask
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, column
from flask.cli import FlaskGroup





# تحميل إعدادات التطبيق من ملف config.json
# يحتوي على بيانات الاتصال بـ API الخارجي ومعلومات المصادقة
CONFIG = json.loads(Path("config.json").read_text(encoding="utf-8"))
DOMAIN = CONFIG["domain"].rstrip("/")      # رابط API الخارجي للاستعلام
USERID = CONFIG["userid"]                  # معرف المستخدم في النظام الخارجي
USERNAME = CONFIG["username"]              # اسم المستخدم للمصادقة
PASSWORD = CONFIG["password"]              # كلمة المرور (يُنصح بنقلها لمتغيرات البيئة)
NODE_URL = CONFIG["node_bridge_url"].rstrip("/")  # رابط جسر Node.js للاتصال بواتساب

# إنشاء تطبيق Flask مع تحديد مجلدات القوالب والملفات الثابتة
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')  # مفتاح سري للجلسات

# ========= إعدادات قاعدة البيانات (balance.db) =========
# استيراد إعدادات قاعدة البيانات
from database_config import DatabaseConfig

# تطبيق إعدادات قاعدة البيانات
app.config['SQLALCHEMY_DATABASE_URI'] = DatabaseConfig.get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = DatabaseConfig.SQLALCHEMY_TRACK_MODIFICATIONS
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = DatabaseConfig.get_engine_options()

# إنشاء كائن قاعدة البيانات
db = SQLAlchemy(app)
migrate = Migrate(app, db)
cli = FlaskGroup(app)
# طباعة معلومات الاتصال عند بدء التشغيل
print("\n" + "="*60)
print("📊 معلومات قاعدة البيانات (balance.db):")
db_info = DatabaseConfig.get_info()
for key, value in db_info.items():
    print(f"   {key}: {value}")
print("="*60 + "\n")

# ========= تعريف الجداول (Models) لقاعدة بيانات balance.db =========

class Package(db.Model):
    """جدول الباقات - يخزن معلومات الباقات المتاحة"""
    __tablename__ = 'package'
    
    id = Column(db.Integer, primary_key=True)
    value = Column(db.Float, nullable=False)       # قيمة الباقة بالريال
    volume = Column(db.Float, nullable=False)  # حجم الباقة بالجيجابايت
    def to_dict(self):
        return {
            "id": self.id,
            "value": self.value,
            "volume": self.volume
        }
    
    def __repr__(self):
        return f'<Package {self.value}ريال - {self.volume}GB>'
from datetime import time as dt_time
import time  # وحدة الوقت القياسية

from datetime import datetime, timedelta
class Query(db.Model):
    """جدول الاستعلامات - يخزن سجلات استعلامات الأرصدة"""
    __tablename__ = 'query'
    
    id = Column(db.Integer, primary_key=True)
    phone_number = Column(db.String(32), nullable=False)
    query_time = Column(db.DateTime, default=datetime.utcnow)
    raw_data = Column(db.Text, nullable=False)

    avblnce = Column(db.Float)                 # بالـ GB بعد التحويل
    balance_unit = Column(db.String(10))       # "GB" أو "MB" أو "YER" أو "UNKNOWN"
    baga_amount = Column(db.Float)             # قيمة الباقة كما في الاستعلام
    expdate = Column(db.DateTime)
    remainAmount = Column(db.Float)
    minamtobill = Column(db.Float)
    daily = Column(db.Boolean, default=False)
    days_remaining = db.Column(db.Integer, nullable=True)

    consumption_since_last = db.Column(db.Float, default=0.0)   # بالـ GB
    daily_consumption = db.Column(db.Float, default=0.0)       # بالـ GB
    amount_consumed = db.Column(db.Float, default=0.0)         # بالنقود
    amount_remaining = db.Column(db.Float, default=0.0)        # بالنقود

    notes = db.Column(db.String(255))
    time_since_last = db.Column(db.String(64))
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, default= 1)
    customer = db.relationship("Customer", backref="queries", lazy=True)
    def __repr__(self):
        return f'<Query {self.phone_number} - {self.query_time}>'
class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    whatsapp = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # الوقت الذي يتم فيه الاستعلام التلقائي يوميًا
    auto_query_time = db.Column(db.Time, default=dt_time(8, 0))
 # مثلاً 08:00 صباحًا

    # علاقة مع الأرقام الخاصة بالعميل
    numbers = db.relationship("Number", backref="customer", lazy=True)

    def __repr__(self):
        return f"<Customer {self.name}>"
    numbers = db.relationship(
        "Number",
        backref="customer",
        cascade="all, delete",  # ON DELETE CASCADE
        lazy=True
    )


class Number(db.Model):
    __tablename__ = "numbers"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    client_id = db.Column(db.Integer, db.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    number = db.Column(db.String, nullable=False)
    type = db.Column(db.String, nullable=False)  # yemenet أو yemen4g
    last_balance = db.Column(db.String)  # نص رصيد (مثلاً "67.95 GB")
    last_balance_value = db.Column(db.Float)  # قيمة الرصيد كرقم
    last_balance_timestamp = db.Column(db.String)  # تاريخ آخر استعلام كنص

    __table_args__ = (
        db.UniqueConstraint('client_id', 'number', name='uix_client_number'),
    )
# ========= الدوال المساعدة لقاعدة بيانات balance.db =========
@app.route("/dashboard/add_customer", methods=["GET", "POST"])
def add_customer():
    if request.method == "POST":
        name = request.form.get("name")
        whatsapp = request.form.get("whatsapp")
        auto_time_str = request.form.get("auto_query_time")  # على شكل 'HH:MM'
        
        from datetime import time
        h, m = map(int, auto_time_str.split(":"))
        auto_time = time(h, m)
        
        customer = Customer(name=name, whatsapp=whatsapp, auto_query_time=auto_time)
        db.session.add(customer)
        db.session.commit()
        return redirect(url_for("dashboard"))  # أو أي صفحة تريد
    return render_template("add_customer.html")
@app.route("/queries/<int:customer_id>")
def customer_queries(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    qset = Query.query.filter(Query.customer_id == customer.id).order_by(Query.query_time.desc()).all()
    return render_template("queries.html", queries=qset, datetime_ar=format_datetime_ar, customer_name=customer.name)

@app.route("/dashboard/clients2")
def dashboard_clients():
    clients = Customer.query.order_by(Customer.id.desc()).all()
    return render_template("clients_dashboard.html", clients=clients)

import re


def parse_balance(balance_str):
    """
    يرجع (value_in_GB, unit_str)
    يتعامل مع صيغ مثل:
      "359.59 Gigabyte(s)"
      "5000 Megabyte(s)"
      "3000000 Kilobyte(s)"
      "5805"  (نعتبرها قيمة نقدية إذا كانت موجودة في remainAmount أو إذا النص لا يحتوي وحدة)
      أو نص عربي يحتوي رقم
    """
    if not balance_str:
        return 0.0, "UNKNOWN"
    s = balance_str.strip()
    # استخراج أول رقم عشري
    m = re.search(r"(-?\d+(\.\d+)?)", s.replace(",", ""))
    if not m:
        return 0.0, "UNKNOWN"
    val = float(m.group(1))

    # اكتشاف الوحدة
    low = s.lower()
    if "gigabyte" in low or "gb" in low or "جيجابايت" in low or "gigabyte(s)" in low:
        return val, "GB"
    if "megabyte" in low or "mb" in low or "ميجابايت" in low:
        return val / 1024.0, "GB"   # نحول لجيجابايت ونعيد وحدة "GB"
    if "kilobyte" in low or "kb" in low or "كيلوبايت" in low:
        return val / (1024.0*1024.0), "GB"
    # إذا النص يحتوي كلمة عملة او هو عدد صحيح (مثلاً remainAmount عادة رقمي) نترك كـ "YER" (نقدي)
    if re.search(r"[٫٠-٩0-9]+\s*(ريال|YER|SAR|USD|دولار)", s) or "remain" in s.lower() or s.strip().isdigit():
        return val, "YER"
    # افتراض افتراضي: إن لم تُذكر الوحدة، نعاملها كـ GB
    return val, "GB"

def format_time_delta(td):
    """ترجع نص مثل: '2d 03h:15m:20s' أو '03h:15m:20s'"""
    if td is None:
        return None
    total_seconds = int(td.total_seconds())
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    parts.append(f"{hours:02d}h:{minutes:02d}m:{seconds:02d}s")
    return " ".join(parts)


def add_query(phone_number, response_json, is_daily=False):
    """
    إضافة استعلام مع تطبيق المنطق المفصّل في طلبك.
    - phone_number: str
    - response_json: النص JSON (يمكن أن يكون dict أو str JSON)
    - is_daily: boolean
    تُرجع dict النتائج و الـ Query المُنشأ
    """
    # تأكد أن data dict
    if isinstance(response_json, str):
        data = json.loads(response_json)
    else:
        data = response_json

    # استخراج الحقول الأساسية
    raw_avbl = data.get('avblnce') or data.get('balance') or ""
    avblnce_value, balance_unit = parse_balance(raw_avbl)   # avblnce_value بالـ GB إذا قابلنا وحدة بيانات
    baga_amount = float(data.get('baga_amount') or 0)
    remain_amount_field = data.get('remainAmount')
    try:
        remain_amount = float(remain_amount_field) if remain_amount_field is not None else 0.0
    except:
        remain_amount = 0.0
    minamtobill = float(data.get('minamtobill') or 0)

    # expdate تحويل بأمان
    expdate_raw = data.get('expdate')
    expdate = None
    if expdate_raw:
        try:
            expdate = datetime.strptime(expdate_raw, "%m/%d/%Y %I:%M:%S %p")
        except:
            # حاول صيغ أخرى أو تجاهله
            try:
                expdate = datetime.fromisoformat(expdate_raw)
            except:
                expdate = None
    # بعد تحويل expdate (كما في دالتك الحالية)
    expdate = None
    if expdate_raw:
        try:
            expdate = datetime.strptime(expdate_raw, "%m/%d/%Y %I:%M:%S %p")
        except:
            try:
                expdate = datetime.fromisoformat(expdate_raw)
            except:
                expdate = None

    # --- هنا نحسب days_remaining (عدد الأيام)
    days_remaining = None
    if expdate:
        # حساب الفرق على مستوى الأيام (يمكن أن يكون سالبًا إذا انتهت الباقة)
        days_remaining = (expdate.date() - datetime.utcnow().date()).days

    # جلب آخر استعلام كُلّي وآخر استعلام يومي لليوم السابق
    last_query = Query.query.filter_by(phone_number=phone_number).order_by(Query.query_time.desc()).first()

    yesterday_date = datetime.utcnow().date() - timedelta(days=1)
    last_daily_yesterday = Query.query.filter(
        Query.phone_number == phone_number,
        Query.daily == True,
        Query.query_time >= datetime.combine(yesterday_date, datetime.min.time()),
        Query.query_time <= datetime.combine(yesterday_date, datetime.max.time())
    ).order_by(Query.query_time.desc()).first()

    # دالة مساعدة لجلب باقة بواسطة قيمة الباقة (baga_amount)
    def find_package_by_value(val):
        if not val:
            return None
        try:
            # نحاول المطابقة بالقيمة (قد تحتاج تعديل لو نوع value int/float)
            return Package.query.filter_by(value=float(val)).first()
        except:
            return None

    # ======================================
    # الآن حسب حالة is_daily
    # ======================================
    consumption_since_last = 0.0
    daily_consumption = 0.0
    time_since_last = None

    # helper to compute consumption when prev_avbl exists, with recharge handling
    def compute_consumption(prev_avbl, curr_avbl, baga_val):
        """إرجاع consumption_in_GB (≥0). إذا curr > prev => قد تكون شحنه."""
        if prev_avbl is None:
            return 0.0
        if curr_avbl > prev_avbl:
            # احتمال شحن: نبحث عن الباقة بقيمة baga_val
            pkg = find_package_by_value(baga_val)
            if pkg:
                # consumption = prev + pkg.volume - curr
                return max(prev_avbl + pkg.volume - curr_avbl, 0.0)
            else:
                # إن لم نجد باقة، لا يمكن حساب الإضافة بدقة -> نعتبر الاستهلاك صفر أو prev - curr إذا أقل
                return 0.0
        else:
            return max(prev_avbl - curr_avbl, 0.0)

    if is_daily:
        # لو هو استعلام يومي: نجلب استعلام يومي لليوم السابق، أو آخر استعلام يومي متوفر
        prev_daily = last_daily_yesterday
        if not prev_daily:
            prev_daily = Query.query.filter_by(phone_number=phone_number, daily=True).order_by(Query.query_time.desc()).first()

        if prev_daily:
            prev_avbl = prev_daily.avblnce
            consumption_since_last = compute_consumption(prev_avbl, avblnce_value, baga_amount)
            # الاستهلاك اليومي يساوي الاستهلاك منذ آخر تقرير
            daily_consumption = consumption_since_last
            # فرق الوقت منذ آخر استعلام (نستخدم query_time للـ prev_daily)
            time_since_last = format_time_delta(datetime.utcnow() - prev_daily.query_time)
        else:
            # أول استعلام يومي لهذا الرقم
            consumption_since_last = 0.0
            daily_consumption = 0.0
            time_since_last = None

    else:
        # is_daily == False
        # نجلب آخر استعلام لهذا اليوم (اليوم الحالي) إذا وُجد
        today = datetime.utcnow().date()
        last_today = Query.query.filter(
            Query.phone_number == phone_number,
            Query.query_time >= datetime.combine(today, datetime.min.time()),
            Query.query_time <= datetime.combine(today, datetime.max.time())
        ).order_by(Query.query_time.desc()).first()

        if last_today:
            # إذا كان الاستعلام السابق اليومي
            if last_today.daily:
                prev_avbl = last_today.avblnce
                consumption_since_last = compute_consumption(prev_avbl, avblnce_value, baga_amount)
                daily_consumption = consumption_since_last
                time_since_last = format_time_delta(datetime.utcnow() - last_today.query_time)
            else:
                # السابق ليس يومي => الاستهلاك منذ آخر تقرير = فرق الأرصدة
                prev_avbl = last_today.avblnce
                consumption_since_last = compute_consumption(prev_avbl, avblnce_value, baga_amount)
                # الاستهلاك اليومي = الاستهلاك اليومي السابق + الاستهلاك منذ اخر تقرير الحالي
                daily_consumption = (last_today.daily_consumption or 0.0) + consumption_since_last
                time_since_last = format_time_delta(datetime.utcnow() - last_today.query_time)
        else:
            # لا يوجد استعلام سابق لهذا اليوم -> نأخذ آخر استعلام متاح لأي وقت
            if last_query:
                prev_avbl = last_query.avblnce
                consumption_since_last = compute_consumption(prev_avbl, avblnce_value, baga_amount)
                # إذا آخر استعلام كان يومي، الاستهلاك اليومي = consumption_since_last (حسب وصفك)
                if last_query.daily:
                    daily_consumption = consumption_since_last
                else:
                    daily_consumption = (last_query.daily_consumption or 0.0) + consumption_since_last
                time_since_last = format_time_delta(datetime.utcnow() - last_query.query_time)
            else:
                # لا يوجد أي استعلام سابق إطلاقًا
                consumption_since_last = 0.0
                daily_consumption = 0.0
                time_since_last = None

    # ======================================
    # حساب القيمة النقدية للجيجابايت (price_per_gb) والمبلغ المتبقي/المستهلك
    # ======================================
    package_for_price = find_package_by_value(baga_amount)
    price_per_gb = None
    amount_remaining = 0.0
    amount_consumed = 0.0
    if package_for_price and package_for_price.volume and package_for_price.value:
        try:
            price_per_gb = float(package_for_price.value) / float(package_for_price.volume)
            # المبلغ المتبقي = avblnce_value * price_per_gb
            amount_remaining = avblnce_value * price_per_gb
            # المبلغ المستهلك = consumption_since_last * price_per_gb
            amount_consumed = consumption_since_last * price_per_gb
        except Exception:
            price_per_gb = None

    # الملاحظات (مثال بسيط كما طلبت من قبل، يمكنك توسيعه)
    notes = ""
    if last_query and avblnce_value > (last_query.avblnce or 0):
        notes = "تم تسديد النقطة"
    else:
        if expdate:
            days_remaining = (expdate - datetime.utcnow()).days
            if days_remaining < 5:
                notes = "أوشك على الانتهاء"
        if avblnce_value < 3:
            # إذا كانت ملاحظة أخرى تريدها أن تظهر بجانب السابقة، ادمجها
            if notes:
                notes = notes + "؛ الرصيد منخفض جداً"
            else:
                notes = "الرصيد منخفض جداً"

    # ======================================
    # حفظ الاستعلام الجديد في DB
    # ======================================
    new_query = Query(
        phone_number=phone_number,
        raw_data=json.dumps(data, ensure_ascii=False),
        avblnce=avblnce_value,
        balance_unit=balance_unit,
        baga_amount=baga_amount,
        expdate=expdate,
        remainAmount=remain_amount,
        minamtobill=minamtobill,
        daily=bool(is_daily),
        days_remaining=days_remaining,
        consumption_since_last=consumption_since_last,
        daily_consumption=daily_consumption,
        amount_consumed=amount_consumed,
        amount_remaining=amount_remaining,
        notes=notes,
        time_since_last=time_since_last
    )
    db.session.add(new_query)
    db.session.commit()

    # ======================================
    # إرجاع نتائج مُفصّلة بعد الحفظ
    # ======================================
    result = {
        "id": new_query.id,
        "phone_number": phone_number,
        "avblnce_gb": avblnce_value,
        "balance_unit": balance_unit,
        "baga_amount": baga_amount,
        "expdate": expdate.isoformat() if expdate else None,
         "days_remaining": days_remaining,
        "consumption_since_last_gb": consumption_since_last,
        "daily_consumption_gb": daily_consumption,
        "time_since_last": time_since_last,
        "price_per_gb": price_per_gb,
        "amount_remaining": amount_remaining,
        "amount_consumed": amount_consumed,
        "notes": notes,
        "raw_data": data
    }
    return new_query, result


# def parse_balance(balance_str):
#     """
#     يحول الرصيد من نص إلى قيمة float بالجيجابايت.
    
#     Args:
#         balance_str: نص الرصيد مثل "5.5 Gigabyte(s)" أو "500 Megabyte(s)"
        
#     Returns:
#         float: القيمة بالجيجابايت
#     """
#     if not balance_str:
#         return 0.0
    
#     parts = balance_str.split()
#     try:
#         value = float(parts[0])
#         unit = parts[1].lower() if len(parts) > 1 else "gigabyte(s)"
        
#         if "gigabyte" in unit or "gb" in unit:
#             return value
#         elif "megabyte" in unit or "mb" in unit:
#             return value / 1024
#         elif "kilobyte" in unit or "kb" in unit:
#             return value / (1024 * 1024)
#         else:
#             return value  # افتراض أنه بالجيجابايت إذا لم نعرف الوحدة
#     except (ValueError, IndexError, AttributeError) as e:
#         print(f"[ERROR] خطأ في تحليل الرصيد '{balance_str}': {e}")
#         return 0.0


# def format_time_delta(time_delta):
#     """
#     تنسيق الفرق الزمني بشكل قابل للقراءة
    
#     Args:
#         time_delta: كائن timedelta
        
#     Returns:
#         str: نص منسق مثل "2:30:15" (ساعات:دقائق:ثواني)
#     """
#     if not time_delta:
#         return None
    
#     total_seconds = int(time_delta.total_seconds())
#     hours = total_seconds // 3600
#     minutes = (total_seconds % 3600) // 60
#     seconds = total_seconds % 60
    
#     return f"{hours}:{minutes:02d}:{seconds:02d}"


# def add_query(phone_number, response_json, is_daily=False):
#     """
#     إضافة استعلام جديد لقاعدة البيانات مع حساب الاستهلاك
    
#     Args:
#         phone_number: رقم الهاتف
#         response_json: البيانات الخام من API بصيغة JSON
#         is_daily: هل هذا استعلام يومي؟
        
#     Returns:
#         Query: كائن الاستعلام المُنشأ
#     """
#     print('zydannaser')
#     data = json.loads(response_json)
#     print('zydan')
#     # تحويل الرصيد لأي وحدة إلى جيجابايت
#     avblnce = parse_balance(data.get('avblnce', '0 Gigabyte(s)'))
#     baga_amount = float(data.get('baga_amount', 0))
#     remain_amount = float(data.get('remainAmount', 0))
#     minamtobill = float(data.get('minamtobill', 0))
    
#     # تحويل تاريخ الانتهاء
#     try:
#         expdate = datetime.strptime(data.get('expdate'), "%m/%d/%Y %I:%M:%S %p")
#     except (ValueError, TypeError):
#         expdate = None
#     try:
#         last_query = Query.query.filter_by(phone_number=phone_number).order_by(Query.query_time.desc()).first()
#     except Exception as e:
#         print(f"[ERROR] خطأ في استعلام رقم {phone_number}: {str(e)}")
#         last_query = None
    
#     # آخر استعلام يومي لليوم السابق
#     yesterday = datetime.utcnow().date() - timedelta(days=1)
#     last_daily_query = Query.query.filter(
#         Query.phone_number == phone_number,
#         Query.daily == True,
#         Query.query_time >= datetime.combine(yesterday, datetime.min.time()),
#         Query.query_time <= datetime.combine(yesterday, datetime.max.time())
#     ).order_by(Query.query_time.desc()).first()
    
#     # حساب الاستهلاك منذ آخر تقرير
#     consumption_since_last = 0.0
#     time_since_last = None
    
#     if last_query:
#         consumption_since_last = max(last_query.avblnce - avblnce, 0)
        
#         # إذا زاد الرصيد (تم التعبئة)، نحسب الاستهلاك بطريقة مختلفة
#         if avblnce > last_query.avblnce:
#             package = Package.query.filter_by(value=int(baga_amount)).first()
#             if package:
#                 consumption_since_last = last_query.avblnce + package.volume - avblnce
        
#         # حساب الفرق الزمني منذ آخر استعلام
#         time_since_last = format_time_delta(datetime.utcnow() - last_query.query_time)
    
#     # حساب الاستهلاك اليومي
#     daily_consumption = 0.0
    
#     if is_daily:
#         if last_daily_query:
#             if avblnce > last_daily_query.avblnce:
#                 package = Package.query.filter_by(value=int(baga_amount)).first()
#                 if package:
#                     daily_consumption = last_daily_query.avblnce + package.volume - avblnce
#             else:
#                 daily_consumption = last_daily_query.avblnce - avblnce
#         else:
#             daily_consumption = consumption_since_last
#     else:
#         if last_daily_query:
#             if avblnce > last_daily_query.avblnce:
#                 package = Package.query.filter_by(value=int(baga_amount)).first()
#                 if package:
#                     daily_consumption = last_daily_query.avblnce + package.volume - avblnce
#             else:
#                 daily_consumption = last_daily_query.avblnce - avblnce
    
#     # توليد الملاحظات
#     notes = ""
#     if expdate:
#         days_remaining = (expdate - datetime.utcnow()).days
        
#         if avblnce > (last_query.avblnce if last_query else 0):
#             notes = "تم تسديد النقطة"
#         elif days_remaining < 5:
#             notes = "أوشك على الانتهاء"
#         elif avblnce < 3:
#             notes = "الرصيد منخفض جداً"
    
#     # إنشاء الاستعلام الجديد
#     new_query = Query(
#         phone_number=phone_number,
#         raw_data=response_json,
#         avblnce=avblnce,
#         baga_amount=baga_amount,
#         expdate=expdate,
#         remainAmount=remain_amount,
#         minamtobill=minamtobill,
#         daily=is_daily,
#         consumption_since_last=consumption_since_last,
#         daily_consumption=daily_consumption,
#         notes=notes,
#         time_since_last=time_since_last
#     )
    
#     db.session.add(new_query)
#     db.session.commit()
    
#     print(f"[INFO] تم حفظ استعلام جديد للرقم {phone_number}")
#     return new_query


# فلتر لتنسيق التواريخ في القوالب
def datetimeformat(value, format='%Y-%m-%d %H:%M'):
    if value is None:
        return ''
    
    # إذا كانت القيمة نصية، قم بتحويلها إلى كائن تاريخ
    if isinstance(value, str):
        try:
            # جرب تحويل النص إلى كائن تاريخ
            if 'T' in value:  # تنسيق ISO مع T
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            else:  # تنسيق مخصص
                for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
                    try:
                        value = datetime.strptime(value, fmt)
                        break
                    except ValueError:
                        continue
        except (ValueError, TypeError):
            return value  # إذا فشل التحويل، ارجع القيمة كما هي
    
    # إذا كانت القيمة رقمية (timestamp)
    if isinstance(value, (int, float)):
        try:
            value = datetime.fromtimestamp(value)
        except (ValueError, TypeError):
            return value
    
    # قم بتنسيق التاريخ
    try:
        return value.strftime(format)
    except (AttributeError, ValueError):
        return value

# إضافة الفلتر إلى جينجا
app.jinja_env.filters['datetimeformat'] = datetimeformat
DB_PATH = Path("db.sqlite3")  # مسار ملف قاعدة البيانات SQLite

# بيانات تسجيل الدخول للمدير
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')  # يجب تغييرها في الإنتاج

# إعدادات بوت واتساب
NODE_SERVER_URL = 'http://localhost:3000'
#SESSION_DATA_PATH = './session_data/sessions.json'
SESSION_DATA_PATH ='C:/Users/HASRIAN TOPTECH/Desktop/systems/whatsappnewbot/sessions'
# كلاس إدارة بوت واتساب
class WhatsAppDashboard:
    def __init__(self):
        self.node_server_url = NODE_SERVER_URL
        self.session_data_path = SESSION_DATA_PATH
        self.db_path = DB_PATH
        self._session_cache = None
        self._cache_timestamp = 0
        self._cache_duration = 3  # cache لمدة 3 ثوانِ
        self._http_session = requests.Session()
        self._http_session.headers.update({'Connection': 'keep-alive'})

    def get_session_data(self):   
        """الحصول على بيانات الجلسة من خادم Node.js المحدث مع cache"""
        import time
        current_time = time.time()
        
        # استخدام cache إذا كانت البيانات حديثة
        if (self._session_cache and 
            current_time - self._cache_timestamp < self._cache_duration):
            return self._session_cache
        
        try:
            # الحصول على بيانات الجلسة من خادم Node.js مع معالجة أفضل للأخطاء
            # الحصول على بيانات الجلسة من خادم Node.js مع معالجة أفضل للأخطاء
            try:
                response = self._http_session.get(
                    'http://localhost:3000/api/status', 
                    timeout=60,
                    headers={'Connection': 'close'}  # منع إعادة استخدام الاتصال
                    )
                
            except:
                response = self._http_session.get(
                    'http://localhost:3000/api/health', 
                    timeout=60,
                    headers={'Connection': 'close'}  # منع إعادة استخدام الاتصال
            )      
            if response.status_code == 200:
                node_data = response.json()
                
                # معالجة الحالات المختلفة
                status = node_data.get('status', 'disconnected')
                
                if (status == 'ready' and node_data.get('isConnected', False)) or (status == 'ready' and node_data.get('isConnected', False)):
                    result = {
                        'status': 'connected',
                        'session_id': node_data.get('sessionId', 'whatsapp_main_session'),
                        'phone_number': node_data.get('client_info', {}).get('wid', {}).get('user', 'غير محدد') if node_data.get('client_info') else 'غير محدد',
                        'connected_at': node_data.get('client_info', {}).get('connected_at', 'غير محدد') if node_data.get('client_info') else None,
                        'qr_code': node_data.get('qr'),
                        'client_info': node_data.get('client_info')
                    }
                    self._session_cache = result
                    self._cache_timestamp = current_time
                    return result
                
                elif status == 'initializing':
                    result = {
                        'status': 'initializing',
                        'session_id': node_data.get('sessionId', 'whatsapp_main_session'),
                        'phone_number': 'قيد التهيئة...',
                        'connected_at': None,
                        'qr_code': None,
                        'client_info': None,
                        'message': 'النظام قيد التهيئة - يرجى الانتظار'
                    }
                    return result
                
                elif status == 'qr' or node_data.get('qr'):
                    result = {
                        'status': 'qr',
                        'session_id': node_data.get('sessionId', 'whatsapp_main_session'),
                        'phone_number': 'في انتظار مسح رمز QR',
                        'connected_at': None,
                        'qr_code': node_data.get('qr'),
                        'client_info': None
                    }
                    # لا نحفظ cache لحالة QR لأنها تتغير
                    return result
                else:
                    # التحقق من حالة initializing أو أي حالة أخرى
                    result = {
                        'status': status,  # استخدام الحالة الفعلية من Node.js
                        'session_id': node_data.get('sessionId', 'whatsapp_main_session'),
                        'phone_number': 'قيد التهيئة...' if status == 'initializing' else 'غير متصل',
                        'connected_at': None,
                        'qr_code': node_data.get('qr'),
                        'message': node_data.get('message', '')
                    }
                    # حفظ في cache
                    self._session_cache = result
                    self._cache_timestamp = current_time
                    return result
            else:
                # إذا فشل الاتصال بالخادم
                return {
                    'status': 'server_error',
                    'session_id': 'unknown',
                    'phone_number': 'خادم غير متاح',
                    'connected_at': None,
                    'qr_code': None,
                    'error': f'HTTP {response.status_code}'
                }
                
        except requests.exceptions.ConnectionError as ce:
            print(f"⚠️ فشل الاتصال بخادم Node.js - محاولة إعادة التشغيل...")
            
            # محاولة إعادة تشغيل خادم Node.js
            try:
                self.restart_nodejs_server()
            except Exception as restart_error:
                print(f"خطأ في إعادة تشغيل الخادم: {restart_error}")
            
            return {
                'status': 'disconnected',
                'session_id': 'whatsapp_main_session',
                'client_info': None,
                'qr': None,
                'error': 'خادم Node.js غير متصل'
            }
        except requests.exceptions.Timeout:
            print("⏰ انتهت مهلة الانتظار - Node.js قيد التشغيل")
            return {
                'status': 'initializing',
                'session_id': 'whatsapp_main_session',
                'client_info': None,
                'qr': None,
                'message': 'Node.js قيد التهيئة - يرجى الانتظار'
            }
        except Exception as e:
            print(f"خطأ في الاتصال بخادم Node.js: {e}")
            
            # إنشاء جلسة HTTP جديدة لمحاولة إصلاح المشكلة
            self._create_http_session()
            
            return {
                'status': 'disconnected',
                'session_id': 'whatsapp_main_session',
                'client_info': None,
                'qr': None,
                'error': f'خطأ في الاتصال: {str(e)}'
            }
    

    def get_bot_status(self):
        """الحصول على حالة البوت من خادم Node.js"""
        try:
            response = requests.get(f"{self.node_server_url}/api/status", timeout=30)
            if response.status_code == 200:
                return response.json()
            return {"success": False, "message": "فشل في الاتصال بالبوت"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"خطأ في الاتصال: {str(e)}"}

    def send_command(self, command, data=None):
        """إرسال أوامر للبوت عبر API"""
        try:
            payload = {"command": command}
            if data:
                payload.update(data)
            
            response = requests.post(f"{self.node_server_url}/api/command", 
                                   json=payload, timeout=100)
            return response.json() if response.status_code == 200 else {"success": False, "error": "فشل في الاتصال"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"خطأ في الاتصال: {str(e)}"}

    def send_bot_command(self, command, data=None):
        """إرسال أوامر محدثة للبوت عبر API"""
        try:
            url = f"http://localhost:3000/api/{command}"
            print(f"[تصحيح] إرسال أمر: {command} إلى {url}")
            
            if data:
                response = requests.post(url, json=data, timeout=90)
            else:
                response = requests.post(url, timeout=60)
            
            result = response.json() if response.status_code == 200 else {
                "success": False, 
                "message": f"خطأ HTTP: {response.status_code}"
            }
            
            print(f"[تصحيح] نتيجة الأمر {command}: {result}")
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"[تصحيح] خطأ في الاتصال: {str(e)}")
            return {"success": False, "message": f"خطأ في الاتصال: {str(e)}"}

    def get_database_stats(self):
        """الحصول على إحصائيات قاعدة البيانات"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            stats = {}
            
            # عدد العملاء
            cursor.execute("SELECT COUNT(*) FROM clients")
            stats['total_clients'] = cursor.fetchone()[0]
            
            # عدد الأرقام
            cursor.execute("SELECT COUNT(*) FROM numbers")
            stats['total_numbers'] = cursor.fetchone()[0]
            
            # عدد السجلات
            cursor.execute("SELECT COUNT(*) FROM logs")
            stats['total_messages'] = cursor.fetchone()[0]
            
            # الجلسات النشطة (من ملف JSON)
            session_data = self.get_session_data()
            stats['active_sessions'] = 1 if session_data and session_data.get('status') == 'connected' else 0
            
            conn.close()
            return stats
        except Exception as e:
            return {"error": f"خطأ في قراءة قاعدة البيانات: {str(e)}"}

# إنشاء مثيل من كلاس إدارة بوت واتساب
whatsapp_bot = WhatsAppDashboard()

# متغيرات لتتبع حالة خادم Node.js
node_server_process = None
node_server_status = "stopped"

# دوال إدارة خادم Node.js
def check_node_dependencies():
    """فحص وتثبيت المكتبات المطلوبة لـ Node.js"""
    try:
        # قراءة package.json للتحقق من المكتبات المطلوبة
        package_json_path = Path("package.json")
        if not package_json_path.exists():
            return {"success": False, "message": "ملف package.json غير موجود"}
        
        # التحقق من وجود node_modules
        node_modules_path = Path("node_modules")
        if not node_modules_path.exists():
            print("📦 تثبيت المكتبات المطلوبة...")
            result = subprocess.run(["pnpm", "install"], 
                                  capture_output=True, text=True, cwd=".")
            if result.returncode != 0:
                # محاولة استخدام npm إذا فشل pnpm
                result = subprocess.run(["pnpm", "install"], 
                                      capture_output=True, text=True, cwd=".")
                if result.returncode != 0:
                    return {"success": False, "message": f"فشل في تثبيت المكتبات: {result.stderr}"}
            
            print("✅ تم تثبيت المكتبات بنجاح")
        
        return {"success": True, "message": "المكتبات جاهزة"}
    except Exception as e:
        return {"success": False, "message": f"خطأ في فحص المكتبات: {str(e)}"}

def is_node_server_running():
    """فحص ما إذا كان خادم Node.js يعمل"""
    try:
        # فحص المنفذ 3000
        for conn in psutil.net_connections():
            if conn.laddr.port == 3000 and conn.status == 'LISTEN':
                return True
        return False
    except:
        return False

def start_node_server():
    """تشغيل خادم Node.js"""
    global node_server_process, node_server_status
    
    try:
        # التحقق من أن الخادم ليس يعمل بالفعل
        if is_node_server_running():
            node_server_status = "running"
            return {"success": False, "message": "الخادم يعمل بالفعل"}
        
        # فحص وتثبيت المكتبات
        deps_check = check_node_dependencies()
        if not deps_check["success"]:
            return deps_check
        
        # تشغيل الخادم
        print("🚀 بدء تشغيل خادم Node.js...")
        node_server_process = subprocess.Popen(
            ["node", "whatsapp-bot-clean.js"],
            cwd=".",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # انتظار أطول للتأكد من بدء التشغيل
        time.sleep(5)
        
        if node_server_process.poll() is None:  # العملية ما زالت تعمل
            node_server_status = "running"
            # إعادة تفعيل المراقبة عند تشغيل الخادم
            global monitoring_enabled
            monitoring_enabled = True
            print("✅ تم تشغيل خادم Node.js بنجاح")
            return {"success": True, "message": "تم تشغيل الخادم بنجاح"}
        else:
            # العملية توقفت
            stdout, stderr = node_server_process.communicate()
            node_server_status = "stopped"
            return {"success": False, "message": f"فشل في تشغيل الخادم: {stderr}"}
            
    except Exception as e:
        node_server_status = "error"
        return {"success": False, "message": f"خطأ في تشغيل الخادم: {str(e)}"}

def stop_node_server():
    """إيقاف خادم Node.js"""
    global node_server_process, node_server_status
    
    try:
        # البحث عن العملية بالمنفذ 3000 وإيقافها
        stopped_any = False
        result = subprocess.run(['taskkill', '/F', '/IM', 'node.exe'], 
                                    capture_output=True, text=True)
        if result.returncode == 0:
            
            stopped_any = True
            print("⏹️ تم إيقاف جميع عمليات Node.js")
        # محاولة إيقاف العملية المحفوظة
        if node_server_process and node_server_process.poll() is None:
            try:
                node_server_process.terminate()
                node_server_process.wait(timeout=5)
                stopped_any = True
                print("⏹️ تم إيقاف العملية المحفوظة")
            except subprocess.TimeoutExpired:
                node_server_process.kill()
                node_server_process.wait()
                stopped_any = True
                print("⏹️ تم قتل العملية المحفوظة بالقوة")
        
        # البحث عن أي عمليات Node.js تستخدم المنفذ 3000
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'node' in proc.info['name'].lower():
                        cmdline = proc.info['cmdline']
                        if cmdline and any('index.js' in str(cmd) for cmd in cmdline):
                            proc.terminate()
                            proc.wait(timeout=5)
                            stopped_any = True
                            print(f"⏹️ تم إيقاف عملية Node.js (PID: {proc.info['pid']})")
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                    continue
        except ImportError:
            # إذا لم تكن psutil متوفرة، استخدم طريقة أخرى
            try:
                import os
                if os.name == 'nt':  # Windows
                    result = subprocess.run(['taskkill', '/F', '/IM', 'node.exe'], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        stopped_any = True
                        print("⏹️ تم إيقاف جميع عمليات Node.js")
            except:
                pass
        
        node_server_status = "stopped"
        node_server_process = None
        
        # إيقاف المراقبة مؤقتاً لتجنب محاولات الاتصال
        global monitoring_enabled
        monitoring_enabled = False
        
        if stopped_any:
            return {"success": True, "message": "تم إيقاف الخادم بنجاح"}
        else:
            return {"success": True, "message": "الخادم غير يعمل أو تم إيقافه بالفعل"}
            
    except Exception as e:
        node_server_status = "stopped"
        return {"success": False, "message": f"خطأ في إيقاف الخادم: {str(e)}"}

def get_node_server_status():
    """الحصول على حالة خادم Node.js"""
    global node_server_status
    
    # فحص فعلي للحالة
    if is_node_server_running():
        node_server_status = "running"
    else:
        node_server_status = "stopped"
    
    return {
        "status": node_server_status,
        "is_running": node_server_status == "running",
        "port": 3000
    }

# دالة للتحقق من تسجيل الدخول
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ========= إدارة قاعدة البيانات =========
# دالة للاتصال بقاعدة البيانات
# TODO: يمكن تحسينها باستخدام Connection Pool لتحسين الأداء
def db_conn():
    """إنشاء اتصال جديد بقاعدة البيانات SQLite"""
    return sqlite3.connect(DB_PATH)

def update_db_schema(conn):
    """Update database schema if needed"""
    c = conn.cursor()
    
    # Check and add missing columns to numbers table
    c.execute("PRAGMA table_info(numbers)")
    columns = [col[1] for col in c.fetchall()]
    
    if 'last_balance' not in columns:
        print("[INFO] Adding last_balance column to numbers table")
        c.execute("ALTER TABLE numbers ADD COLUMN last_balance TEXT")
    
    if 'last_balance_value' not in columns:
        print("[INFO] Adding last_balance_value column to numbers table")
        c.execute("ALTER TABLE numbers ADD COLUMN last_balance_value REAL")
    
    if 'last_balance_timestamp' not in columns:
        print("[INFO] Adding last_balance_timestamp column to numbers table")
        c.execute("ALTER TABLE numbers ADD COLUMN last_balance_timestamp TEXT")
    
    # Check if number_history table exists
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='number_history'")
    if not c.fetchone():
        print("[INFO] Creating number_history table")
        c.execute(
            """
            CREATE TABLE number_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number_id INTEGER NOT NULL,
                balance TEXT,
                balance_value REAL,
                package_value REAL,
                expiry_date TEXT,
                min_payment TEXT,
                speed TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (number_id) REFERENCES numbers(id) ON DELETE CASCADE
            )
            """
        )


def init_db():
    with db_conn() as conn:
        c = conn.cursor()
        
        # Create tables if they don't exist
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                full_name TEXT,
                email TEXT,
                is_admin BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
            """
        )
        
        # Create default admin user if not exists
        c.execute("SELECT COUNT(*) FROM users")
        if c.fetchone()[0] == 0:
            hashed_password = hashlib.sha256('admin123'.encode('utf-8')).hexdigest()
            c.execute(
                """
                INSERT INTO users (username, password, full_name, email, is_admin)
                VALUES (?, ?, ?, ?, ?)
                """,
                ('admin', hashed_password, 'مدير النظام', 'admin@example.com', 1)
            )
        
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                whatsapp TEXT NOT NULL UNIQUE
            )
            """
        )
        
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS numbers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                number TEXT NOT NULL,
                type TEXT NOT NULL,
                last_balance TEXT,
                last_balance_value REAL,
                last_balance_timestamp TEXT,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
                UNIQUE(client_id, number)
            )
            """
        )
        
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                number TEXT NOT NULL,
                type TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
            )
            """
        )
        
        # Update database schema if needed
        update_db_schema(conn)
        conn.commit()

# ========= Helpers =========
def gen_transid(k: int = 10) -> str:
    chars = string.digits
    return "".join(random.choice(chars) for _ in range(k))

def md5_hex(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def generate_token(username: str, password: str, transid: str, mobile: str) -> str:
    hash_pass = md5_hex(password)
    return md5_hex(hash_pass + str(transid) + username + str(mobile))

def detect_type(number: str) -> str:
    if not number:
        return "unknown"
        
    n = number.strip()
    print(f"[DEBUG] تحليل نوع الرقم: {n}")
    
    # تنظيف الرقم من أي أحرف غير رقمية
    clean_number = ''.join(filter(str.isdigit, n))
    
    # تحديد نوع الرقم
    if clean_number.startswith('10') or clean_number.startswith('1'):
        print(f"[DEBUG] تم التعرف على الرقم كـ يمن فور جي")
        return "yemen4g"
    elif clean_number.startswith('01'):
        print(f"[DEBUG] تم التعرف على الرقم كـ يمن نت")
        return "yemenet"
    else:
        print(f"[INFO] تم قبول الرقم كنوع افتراضي (يمن نت)")
        return "yemenet"  # قبول أي رقم آخر كنوع افتراضي

def calculate_summary_statistics(client_id: int, results: list) -> dict:
    """حساب الإحصائيات الإجمالية للعميل"""
    from datetime import datetime, timezone
    import json
    
    stats = {
        'total_lines': len(results),
        'total_consumption': 0.0,
        'total_balance': 0.0,
        'expired_lines': 0,
        'expiring_soon_lines': 0,
        'paid_lines': 0,
        'last_query_time': None,
        'current_time': datetime.now(timezone.utc)
    }
    
    # حساب الإحصائيات من النتائج
    for result in results:
        if result.get('data', {}).get('raw'):
            try:
                raw_data = json.loads(result['data']['raw'])
                balance_text = raw_data.get('balance', '')
                
                # استخراج قيمة الرصيد من البيانات الخام
                balance_value = 0.0
                
                # محاولة استخراج الرصيد من الحقول المختلفة
                import re
                
                # أولاً: محاولة استخراج من حقل avblnce
                if 'avblnce' in raw_data:
                    avblnce_text = str(raw_data['avblnce'])
                    balance_match = re.search(r'(\d+\.?\d*)\s*(GB|Gigabyte\(s\)|Gigabyte)', avblnce_text)
                    if balance_match:
                        balance_value = float(balance_match.group(1))
                        stats['total_balance'] += balance_value
                
                # ثانياً: إذا لم نجد في avblnce، نبحث في balance
                if balance_value == 0.0 and balance_text:
                    balance_match = re.search(r'(\d+\.?\d*)\s*(GB|Gigabyte\(s\)|Gigabyte)', balance_text)
                    if balance_match:
                        balance_value = float(balance_match.group(1))
                        stats['total_balance'] += balance_value
                
                # حساب الاستهلاك لكل رقم
                consumption_data = get_consumption_data(result['number'])
                if consumption_data.get('consumption', 0) > 0:
                    stats['total_consumption'] += consumption_data['consumption']
                
                # تحديد حالة الخط
                expiry_text = ''
                if 'تأريخ الانتهاء:' in balance_text:
                    expiry_text = balance_text.split('تأريخ الانتهاء:')[1].split('اقل مبلغ سداد:')[0].strip()
                elif 'تاريخ الانتهاء:' in balance_text:
                    expiry_text = balance_text.split('تاريخ الانتهاء:')[1].split('أقل مبلغ سداد:')[0].strip()
                
                # تحليل تاريخ الانتهاء
                if expiry_text:
                    try:
                        from datetime import datetime
                        expiry_date = datetime.strptime(expiry_text.split()[0], '%m/%d/%Y')
                        now = datetime.now()
                        days_diff = (expiry_date - now).days
                        
                        if days_diff < 0:
                            stats['expired_lines'] += 1
                        elif days_diff <= 7:  # ينتهي خلال أسبوع
                            stats['expiring_soon_lines'] += 1
                        
                        # تحديد إذا كان الخط مسدد (لديه رصيد)
                        if balance_value > 0:
                            stats['paid_lines'] += 1
                    except:
                        pass
            except:
                pass
    
    # البحث عن آخر وقت استعلام لأول رقم فقط
    with db_conn() as conn:
        c = conn.cursor()
        # الحصول على أول رقم للعميل
        c.execute("""
            SELECT id FROM numbers 
            WHERE client_id = ? 
            ORDER BY id ASC 
            LIMIT 1
        """, (client_id,))
        first_number = c.fetchone()
        
        if first_number:
            # البحث عن ثاني أحدث سجل لأول رقم فقط
            c.execute("""
                SELECT created_at 
                FROM number_history 
                WHERE number_id = ?
                ORDER BY created_at DESC 
                LIMIT 2
            """, (first_number[0],))
            results_time = c.fetchall()
            if len(results_time) >= 2:
                # استخدام ثاني أحدث سجل كآخر استعلام
                stats['last_query_time'] = results_time[1][0]
    
    return stats
def format_arabic_reportnew(results: list, client_id: int = None) -> str:
    """
    تنسيق تقرير الأرقام باللغة العربية مع المعلومات المحسنة
    يشمل الأيام المتبقية والاستهلاك من قاعدة البيانات
    """
    lines = ["📊 *تقرير الخطوط من نظام العطاب اكسبرس* 📊\n"]
    
    for i, result in enumerate(results, 1):
        lines.append(f"🔢 *الرقم {i}*")
        
        if "error" in result:
            lines.append(f"📱 *الرقم*: {result['number']}")
            lines.append(f"❌ *خطأ*: {result['error']}\n")
            continue
            
        data = result.get("query", {})
        raw_data = {}
        
        # Try to parse the raw data if it's a string
        if isinstance(data.get("raw"), str):
            try:
                raw_data = json.loads(data["raw"])
            except (json.JSONDecodeError, TypeError):
                raw_data = {"raw": data.get("raw", "")}
        elif isinstance(data.get("raw"), dict):
            raw_data = data["raw"]
        
        # Extract number type for better formatting
        num_type = ""
        if "yem4g" in result.get("endpoint", ""):
            num_type = "يمن فور جي"
        elif "adsl" in result.get("endpoint", "").lower():
            num_type = "يمن نت"
        
        # Format the response based on available data
        if raw_data and isinstance(raw_data, dict):
            # Extract values from the raw data
            balance = raw_data.get("avblnce_gb", "")
            package = raw_data.get("baga_amount", "")
            expiry = raw_data.get("expdate", "")
            min_payment = raw_data.get("minamtobill", "0")
            consumption_since_last_gb = round(raw_data.get("consumption_since_last_gb", "0"),2)
            daily_consumption_gb = round(raw_data.get("daily_consumption_gb", "0"),2)
            amount_remaining = round(raw_data.get("amount_remaining", "0"),2)
            amount_consumed = round(raw_data.get("amount_consumed", ""),2)
            days_remaining = raw_data.get("days_remaining", "")
            time_since_last =  raw_data.get("time_since_last", "")
        
            # Format the response in a clean table-like format
            lines.append(f"📱 *الرقم*: {result['number']}")
            if num_type:
                lines.append(f"📶 *نوع الخدمة*: {num_type}")
            
            # Add separator line
            lines.append("─" * 30)
            
            # Add balance info in a formatted way
            if balance:
                lines.append(f"💳 *الرصيد*: {balance} جيجا")
            if package:
                lines.append(f"📦 *قيمة الباقة*: {package} ريال")
                lines.append(f"📦 *الرصيد المستهلك*: {amount_consumed} ريال")
                lines.append(f"📦 *الرصيد المتبقي*: {amount_remaining} ريال")
            
            # استخدام الدالة المحسنة لحساب الأيام المتبقية
                # تنظيف تنسيق التاريخ
                expiry_clean = expiry.replace(" 12:00:00 AM", "").replace(" 12:00:00 ص", "")
                days_text, days_count, status = calculate_days_remaining(expiry_clean)
                lines.append(f"📅 *تاريخ الانتهاء*: {expiry}")
                lines.append(f"⏰ *الأيام المتبقية*: {days_remaining}")
            
            # إضافة معلومات الاستهلاك من قاعدة البيانات
            # consumption_data = get_consumption_data(result['number'])
            if time_since_last != "null":
                lines.append(f"🔄 *آخر تحديث*: {time_since_last}")
            else:
                lines.append(f"🔄 *آخر تحديث*: أول استعلام")
                
            if consumption_since_last_gb :
                lines.append(f"📉 *الاستهلاك منذ اخر تقرير*: {consumption_since_last_gb} [جيجا]")
            else:
                lines.append(f"📉 *الاستهلاك*: لا يوجد استهلاك")
                 
            if daily_consumption_gb :
                lines.append(f"📉 *الاستهلاك اليومي*: {daily_consumption_gb} جيجا")
          
                
          
            
            # إضافة أقل مبلغ سداد فقط إذا كان أكبر من صفر
            # if min_payment and float(min_payment) > 0:
            #     lines.append(f"💰 *أقل مبلغ سداد*: {min_payment} ريال")
            
            # Add speed if available
            speed = raw_data.get("speed", "")
            if speed and speed.strip():
                lines.append(f"⚡ *السرعة*: {speed}")
            
            # Add status if available
            api_status = raw_data.get("resultDesc", "")
            if api_status and api_status.lower() != "success":
                lines.append(f"ℹ️ *الحالة*: {api_status}")
            
            # إضافة حالة الباقة من حساب الأيام المتبقية
            if expiry:
                if status == "active":
                    lines.append(f"✅ *حالة الباقة*: نشطة")
                elif status == "warning":
                    lines.append(f"⚠️ *حالة الباقة*: تحذير - قريبة من الانتهاء")
                elif status == "critical":
                    lines.append(f"🔴 *حالة الباقة*: حرجة - تنتهي قريباً")
                elif status == "expires_today":
                    lines.append(f"🔴 *حالة الباقة*: تنتهي اليوم")
                elif status == "expired":
                    lines.append(f"❌ *حالة الباقة*: منتهية")
                
        elif "formatted" in data:
            # Fallback to pre-formatted message
            lines.append(data["formatted"])
        else:
            # Fallback to showing the raw data
            lines.append("📋 *تفاصيل الباقة*")
            if "balance" in data:
                lines.append(data["balance"])
            else:
                lines.append("⚠️ لا توجد بيانات متاحة")
        
        lines.append("")  # Add empty line between results
    
    # Add timestamp and footer
    from datetime import datetime
    lines.append("─" * 30)  # Add separator before footer
    # إضافة الإحصائيات الإجمالية إذا تم تمرير معرف العميل
    if client_id and len(results) > 1:
        stats = calculate_summary_statistics(client_id, results)
        
        lines.append("\n" + "═" * 40)
        lines.append("📈 *الإحصائيات الإجمالية* 📈")
        lines.append("═" * 40)
        
        # إجمالي الخطوط والأرصدة
        lines.append(f"📊 *إجمالي الخطوط*: {stats['total_lines']}")
        lines.append(f"💰 *إجمالي الأرصدة*: {stats['total_balance']:.2f} GB")
        
        # الاستهلاك الإجمالي
        if stats['total_consumption'] > 0:
            lines.append(f"📉 *إجمالي الاستهلاك*: {stats['total_consumption']:.2f} GB")
        else:
            lines.append(f"📉 *إجمالي الاستهلاك*: لا يوجد استهلاك")
        
        # حالة الخطوط
        lines.append(f"✅ *خطوط مسددة*: {stats['paid_lines']}")
        lines.append(f"⚠️ *خطوط ستنتهي قريباً*: {stats['expiring_soon_lines']}")
        lines.append(f"❌ *خطوط منتهية*: {stats['expired_lines']}")
        
        # الفارق الزمني
        if stats['last_query_time']:
            time_diff = calculate_time_diff(stats['last_query_time'])
            lines.append(f"🕐 *آخر استعلام*: {time_diff}")
        else:
            lines.append(f"🕐 *آخر استعلام*: هذا هو الاستعلام الأول")
    
    # التاريخ والوقت الحالي
    from datetime import datetime
    import locale
    
    try:
        locale.setlocale(locale.LC_TIME, 'ar_SA.UTF-8')
    except:
        try:
            locale.setlocale(locale.LC_TIME, 'Arabic_Saudi Arabia.1256')
        except:
            pass  # استخدام الإعداد الافتراضي
    
    now = datetime.now()
    current_date = now.strftime('%Y-%m-%d')
    current_time = now.strftime('%I:%M %p')
    day_name = now.strftime('%A')
    
    lines.append("\n" + "─" * 30)
    lines.append(f"📅 *التاريخ*: {current_date}")
    lines.append(f"🕐 *الوقت*: {current_time}")
    lines.append(f"📆 *اليوم*: {day_name}")
    
    lines.append("\n📞 للاشتراك التواصل على الرقم: *+967779751181*")
    
    return "\n".join(lines)

def format_arabic_report(results: list, client_id: int = None) -> str:
    """
    تنسيق تقرير الأرقام باللغة العربية مع المعلومات المحسنة
    يشمل الأيام المتبقية والاستهلاك من قاعدة البيانات
    """
    lines = ["📊 *تقرير الخطوط من نظام العطاب اكسبرس* 📊\n"]
    
    for i, result in enumerate(results, 1):
        lines.append(f"🔢 *الرقم {i}*")
        
        if "error" in result:
            lines.append(f"📱 *الرقم*: {result['number']}")
            lines.append(f"❌ *خطأ*: {result['error']}\n")
            continue
            
        data = result.get("data", {})
        raw_data = {}
        
        # Try to parse the raw data if it's a string
        if isinstance(data.get("raw"), str):
            try:
                raw_data = json.loads(data["raw"])
            except (json.JSONDecodeError, TypeError):
                raw_data = {"raw": data.get("raw", "")}
        elif isinstance(data.get("raw"), dict):
            raw_data = data["raw"]
        
        # Extract number type for better formatting
        num_type = ""
        if "yem4g" in result.get("endpoint", ""):
            num_type = "يمن فور جي"
        elif "adsl" in result.get("endpoint", "").lower():
            num_type = "يمن نت"
        
        # Format the response based on available data
        if raw_data and isinstance(raw_data, dict):
            # Extract values from the raw data
            balance = raw_data.get("avblnce", "")
            package = raw_data.get("baga_amount", "")
            expiry = raw_data.get("expdate", "")
            min_payment = raw_data.get("minamtobill", "0")
            
            # Format the response in a clean table-like format
            lines.append(f"📱 *الرقم*: {result['number']}")
            if num_type:
                lines.append(f"📶 *نوع الخدمة*: {num_type}")
            
            # Add separator line
            lines.append("─" * 30)
            
            # Add balance info in a formatted way
            if balance:
                lines.append(f"💳 *الرصيد*: {balance}")
            if package:
                lines.append(f"📦 *قيمة الباقة*: {package} ريال")
            
            # استخدام الدالة المحسنة لحساب الأيام المتبقية
            if expiry:
                # تنظيف تنسيق التاريخ
                expiry_clean = expiry.replace(" 12:00:00 AM", "").replace(" 12:00:00 ص", "")
                days_text, days_count, status = calculate_days_remaining(expiry_clean)
                lines.append(f"📅 *تاريخ الانتهاء*: {expiry}")
                lines.append(f"⏰ *الأيام المتبقية*: {days_text}")
            
            # إضافة معلومات الاستهلاك من قاعدة البيانات
            consumption_data = get_consumption_data(result['number'])
            if consumption_data.get('has_previous', False):
                lines.append(f"🔄 *آخر تحديث*: {consumption_data['time_diff']}")
                if consumption_data.get('consumption', 0) > 0:
                    lines.append(f"📉 *الاستهلاك*: {consumption_data['consumption']:.2f} GB")
                else:
                    lines.append(f"📉 *الاستهلاك*: لا يوجد استهلاك")
            else:
                lines.append(f"🔄 *آخر تحديث*: أول استعلام")
            
            # إضافة أقل مبلغ سداد فقط إذا كان أكبر من صفر
            if min_payment and float(min_payment) > 0:
                lines.append(f"💰 *أقل مبلغ سداد*: {min_payment} ريال")
            
            # Add speed if available
            speed = raw_data.get("speed", "")
            if speed and speed.strip():
                lines.append(f"⚡ *السرعة*: {speed}")
            
            # Add status if available
            api_status = raw_data.get("resultDesc", "")
            if api_status and api_status.lower() != "success":
                lines.append(f"ℹ️ *الحالة*: {api_status}")
            
            # إضافة حالة الباقة من حساب الأيام المتبقية
            if expiry:
                if status == "active":
                    lines.append(f"✅ *حالة الباقة*: نشطة")
                elif status == "warning":
                    lines.append(f"⚠️ *حالة الباقة*: تحذير - قريبة من الانتهاء")
                elif status == "critical":
                    lines.append(f"🔴 *حالة الباقة*: حرجة - تنتهي قريباً")
                elif status == "expires_today":
                    lines.append(f"🔴 *حالة الباقة*: تنتهي اليوم")
                elif status == "expired":
                    lines.append(f"❌ *حالة الباقة*: منتهية")
                
        elif "formatted" in data:
            # Fallback to pre-formatted message
            lines.append(data["formatted"])
        else:
            # Fallback to showing the raw data
            lines.append("📋 *تفاصيل الباقة*")
            if "balance" in data:
                lines.append(data["balance"])
            else:
                lines.append("⚠️ لا توجد بيانات متاحة")
        
        lines.append("")  # Add empty line between results
    
    # Add timestamp and footer
    from datetime import datetime
    lines.append("─" * 30)  # Add separator before footer
    # إضافة الإحصائيات الإجمالية إذا تم تمرير معرف العميل
    if client_id and len(results) > 1:
        stats = calculate_summary_statistics(client_id, results)
        
        lines.append("\n" + "═" * 40)
        lines.append("📈 *الإحصائيات الإجمالية* 📈")
        lines.append("═" * 40)
        
        # إجمالي الخطوط والأرصدة
        lines.append(f"📊 *إجمالي الخطوط*: {stats['total_lines']}")
        lines.append(f"💰 *إجمالي الأرصدة*: {stats['total_balance']:.2f} GB")
        
        # الاستهلاك الإجمالي
        if stats['total_consumption'] > 0:
            lines.append(f"📉 *إجمالي الاستهلاك*: {stats['total_consumption']:.2f} GB")
        else:
            lines.append(f"📉 *إجمالي الاستهلاك*: لا يوجد استهلاك")
        
        # حالة الخطوط
        lines.append(f"✅ *خطوط مسددة*: {stats['paid_lines']}")
        lines.append(f"⚠️ *خطوط ستنتهي قريباً*: {stats['expiring_soon_lines']}")
        lines.append(f"❌ *خطوط منتهية*: {stats['expired_lines']}")
        
        # الفارق الزمني
        if stats['last_query_time']:
            time_diff = calculate_time_diff(stats['last_query_time'])
            lines.append(f"🕐 *آخر استعلام*: {time_diff}")
        else:
            lines.append(f"🕐 *آخر استعلام*: هذا هو الاستعلام الأول")
    
    # التاريخ والوقت الحالي
    from datetime import datetime
    import locale
    
    try:
        locale.setlocale(locale.LC_TIME, 'ar_SA.UTF-8')
    except:
        try:
            locale.setlocale(locale.LC_TIME, 'Arabic_Saudi Arabia.1256')
        except:
            pass  # استخدام الإعداد الافتراضي
    
    now = datetime.now()
    current_date = now.strftime('%Y-%m-%d')
    current_time = now.strftime('%I:%M %p')
    day_name = now.strftime('%A')
    
    lines.append("\n" + "─" * 30)
    lines.append(f"📅 *التاريخ*: {current_date}")
    lines.append(f"🕐 *الوقت*: {current_time}")
    lines.append(f"📆 *اليوم*: {day_name}")
    
    lines.append("\n📞 للاشتراك التواصل على الرقم: *+967779751181*")
    
    return "\n".join(lines)

def send_whatsapp(to_phone: str, message: str):
    url = f"{NODE_URL}/send"
    res = requests.post(url, json={"to": to_phone, "message": message})
    res.raise_for_status()
    return res.json()

def extract_balance_value(balance_str: str) -> float:
    """استخراج القيمة الرقمية من نص الرصيد
    
    مثال: '9.59 GB' -> 9.59
    يدعم تنسيقات مختلفة مثل: '1.5 جيجا', '500 ميجا', '2.3 GB'
    
    Args:
        balance_str: نص الرصيد
        
    Returns:
        float: القيمة الرقمية للرصيد
    """
    if not balance_str:
        return 0.0
    
    try:
        # البحث عن الرقم الأول في النص (يدعم الأرقام العشرية)
        match = re.search(r'\d+(\.\d+)?', balance_str)
        if match:
            value = float(match.group(0))
            
            # التحقق من وحدة القياس وتحويلها إلى جيجابايت إذا لزم الأمر
            balance_lower = balance_str.lower()
            
            if 'mb' in balance_lower or 'ميجا' in balance_lower:
                value = value / 1024  # تحويل من ميجابايت إلى جيجابايت
            elif 'kb' in balance_lower or 'كيلو' in balance_lower:
                value = value / (1024 * 1024)  # تحويل من كيلوبايت إلى جيجابايت
                
            return value
    except (ValueError, AttributeError) as e:
        print(f"[ERROR] خطأ في استخراج قيمة الرصيد من '{balance_str}': {e}")
    
    return 0.0

def calculate_time_diff(prev_timestamp: str) -> str:
    """Calculate time difference between now and previous timestamp"""
    from datetime import datetime, timezone
    if not prev_timestamp:
        return "أول استعلام"
        
    try:
        # تحويل timestamp إلى datetime object
        if 'T' in prev_timestamp:
            # ISO format
            prev_time = datetime.fromisoformat(prev_timestamp.replace('Z', '+00:00'))
        else:
            # تحويل تنسيق آخر
            prev_time = datetime.fromisoformat(prev_timestamp)
        
        # التأكد من أن prev_time له timezone
        if prev_time.tzinfo is None:
            prev_time = prev_time.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        delta = now - prev_time
        
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days} يوم")
        if hours > 0:
            parts.append(f"{hours} ساعة")
        if minutes > 0 or not parts:  # Always show at least minutes if no days/hours
            parts.append(f"{minutes} دقيقة")
            
        return " و ".join(parts) + " مضت"
    except Exception as e:
        print(f"[ERROR] Error calculating time diff: {e}")
        return "غير معروف"

def calculate_days_remaining(expiry_date_str: str) -> tuple:
    """حساب الأيام المتبقية حتى تاريخ انتهاء الباقة
    
    Args:
        expiry_date_str: تاريخ الانتهاء كنص
        
    Returns:
        tuple: (نص الأيام المتبقية، عدد الأيام كرقم، حالة الباقة)
    """
    if not expiry_date_str:
        return "غير معروف", 0, "unknown"
        
    try:
        # تنظيف النص من الأوقات والنصوص غير المرغوبة
        clean_date = expiry_date_str.replace(" 12:00:00 AM", "").replace(" 12:00:00 ص", "")
        clean_date = clean_date.replace(" 00:00:00", "").replace("T00:00:00", "")
        clean_date = clean_date.strip()
        
        # محاولة تحليل التاريخ بتنسيقات مختلفة
        expiry_date = None
        date_formats = [
            "%m/%d/%Y %I:%M:%S %p",  # 12/31/2024 11:59:59 PM
            "%m/%d/%Y",               # 12/31/2024
            "%Y-%m-%d",               # 2024-12-31
            "%d/%m/%Y",               # 31/12/2024
            "%Y/%m/%d",               # 2024/12/31
            "%d-%m-%Y",               # 31-12-2024 (يمن نت)
            "%Y-%m-%d %H:%M:%S",      # 2024-12-31 23:59:59
            "%d/%m/%Y %H:%M:%S",      # 31/12/2024 23:59:59
            "%m-%d-%Y",               # 12-31-2024
            "%d.%m.%Y",               # 31.12.2024
            "%Y.%m.%d",               # 2024.12.31
        ]
        
        for fmt in date_formats:
            try:
                expiry_date = datetime.strptime(clean_date, fmt)
                break
            except ValueError:
                continue
        
        if not expiry_date:
            # محاولة أخيرة لتحليل التاريخ باستخدام regex
            import re
            
            # البحث عن أرقام التاريخ في النص
            date_pattern = r'(\d{1,4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,4})'
            match = re.search(date_pattern, clean_date)
            
            if match:
                part1, part2, part3 = match.groups()
                
                # تحديد أي جزء هو السنة (الرقم الأكبر من 31)
                parts = [int(part1), int(part2), int(part3)]
                year_candidates = [p for p in parts if p > 31]
                
                if year_candidates:
                    year = year_candidates[0]
                    remaining_parts = [p for p in parts if p != year]
                    
                    # محاولة تحديد الشهر واليوم
                    if len(remaining_parts) == 2:
                        month_candidates = [p for p in remaining_parts if 1 <= p <= 12]
                        day_candidates = [p for p in remaining_parts if 1 <= p <= 31]
                        
                        # إذا كان أحد الأرقام أكبر من 12، فهو اليوم
                        if any(p > 12 for p in remaining_parts):
                            day = max(remaining_parts)
                            month = min(remaining_parts)
                        else:
                            # محاولة الترتيب الأكثر شيوعاً
                            if part1 == str(year):  # YYYY/MM/DD
                                month, day = remaining_parts[0], remaining_parts[1]
                            else:  # DD/MM/YYYY or MM/DD/YYYY
                                # افتراض DD/MM/YYYY أولاً
                                day, month = remaining_parts[0], remaining_parts[1]
                        
                        try:
                            expiry_date = datetime(year, month, day)
                        except ValueError:
                            try:
                                # محاولة عكسية
                                expiry_date = datetime(year, day, month)
                            except ValueError:
                                print(f"[ERROR] فشل في تحليل التاريخ: {clean_date}")
                                return f"تنسيق التاريخ غير معروف: {clean_date}", 0, "invalid_format"
                else:
                    print(f"[ERROR] لم يتم العثور على سنة صالحة في: {clean_date}")
                    return f"تنسيق التاريخ غير معروف: {clean_date}", 0, "invalid_format"
            else:
                print(f"[ERROR] لم يتم العثور على تاريخ صالح في: {clean_date}")
                return f"تنسيق التاريخ غير معروف: {clean_date}", 0, "invalid_format"
            
        # حساب الفرق بالأيام
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        expiry_day = expiry_date.replace(hour=0, minute=0, second=0, microsecond=0)
        days_diff = (expiry_day - today).days
        
        # تحديد حالة الباقة ونص الأيام (الحد الأقصى 30 يوم)
        if days_diff > 30:
            # إذا كانت أكثر من 30 يوم، نعرض 30+ يوم
            status = "active"
            days_text = f"🟢 {days_diff} يوم متبقي"
        elif days_diff > 7:
            status = "active"
            days_text = f"🟢 {days_diff} يوم متبقي"
        elif days_diff > 3:
            status = "warning"
            days_text = f"🟡 {days_diff} أيام متبقية"
        elif days_diff > 0:
            status = "critical"
            days_text = f"🔴 {days_diff} يوم متبقي فقط"
        elif days_diff == 0:
            status = "expires_today"
            days_text = "🔴 تنتهي اليوم"
        else:
            status = "expired"
            days_text = f"❌ منتهية منذ {abs(days_diff)} يوم"
            
        return days_text, days_diff, status
        
    except Exception as e:
        print(f"[ERROR] خطأ في حساب الأيام المتبقية: {e}")
        return "خطأ في التاريخ", 0, "error"

def get_consumption_data(number: str) -> dict:
    """حساب بيانات الاستهلاك من آخر تقرير في قاعدة البيانات
    
    Args:
        number: رقم الهاتف المراد حساب استهلاكه
        
    Returns:
        dict: بيانات الاستهلاك والتقرير السابق
    """
    with db_conn() as conn:
        c = conn.cursor()
        
        # الحصول على بيانات الرقم الحالية
        c.execute("""
            SELECT id, last_balance, last_balance_value, last_balance_timestamp 
            FROM numbers 
            WHERE number = ?
        """, (number,))
        current_data = c.fetchone()
        
        if not current_data:
            print(f"[DEBUG] لم يتم العثور على الرقم {number} في جدول numbers")
            return {
                'has_previous': False,
                'consumption': 0,
                'time_diff': 'أول استعلام',
                'previous_balance': None,
                'current_data': None
            }
        
        number_id = current_data[0]
        print(f"[DEBUG] تم العثور على الرقم {number} بمعرف {number_id}")
        
        # الحصول على آخر تقريرين من التاريخ (لحساب الاستهلاك)
        c.execute("""
            SELECT balance, balance_value, created_at
            FROM number_history 
            WHERE number_id = ?
            ORDER BY created_at DESC 
            LIMIT 2
        """, (number_id,))
        history_records = c.fetchall()
        
        print(f"[DEBUG] تم العثور على {len(history_records)} سجل في التاريخ للرقم {number}")
        
        if len(history_records) < 2:
            # لا يوجد تقرير سابق للمقارنة
            if len(history_records) == 0:
                time_msg = 'أول استعلام'
                print(f"[DEBUG] {time_msg} - لا توجد سجلات في التاريخ")
            else:
                # يوجد سجل واحد فقط، نحسب الوقت منذ إنشائه
                record_time = history_records[0][2]
                time_msg = calculate_time_diff(record_time)
                print(f"[DEBUG] سجل واحد فقط - آخر تحديث: {time_msg}")
            
            return {
                'has_previous': len(history_records) > 0,  # True إذا كان يوجد سجل واحد على الأقل
                'consumption': 0,
                'time_diff': time_msg,
                'previous_balance': history_records[0][0] if history_records else None,
                'current_data': current_data
            }
        
        # حساب الاستهلاك بين آخر تقريرين
        latest_balance = history_records[0][1] or 0  # أحدث تقرير
        previous_balance = history_records[1][1] or 0  # التقرير السابق
        consumption = max(0, previous_balance - latest_balance)  # تجنب القيم السالبة
        
        # حساب الفترة الزمنية
        time_diff = calculate_time_diff(history_records[1][2])  # وقت التقرير السابق
        
        return {
            'has_previous': True,
            'consumption': consumption,
            'time_diff': time_diff,
            'previous_balance': history_records[1][0],
            'previous_balance_value': previous_balance,
            'latest_balance_value': latest_balance,
            'current_data': current_data
        }

def query_number(number: str):
    """استعلام رقم هاتف وجلب بيانات الرصيد والباقة
    
    يقوم بالخطوات التالية:
    1. تحديد نوع الرقم (يمن فور جي أو يمن نت)
    2. إنشاء توكن المصادقة
    3. إرسال طلب الاستعلام لـ API الخارجي
    4. معالجة الرد وحفظ البيانات
    5. حساب الاستهلاك والأيام المتبقية
    
    Args:
        number: رقم الهاتف المراد استعلامه
        
    Returns:
        dict: بيانات الاستعلام أو رسالة خطأ
    """
    print(f"\n[INFO] بدء معالجة الاستعلام للرقم: {number}")
    
    # تحديد نوع الرقم (يمن فور جي أو يمن نت)
    ntype = detect_type(number)
    if ntype == "unknown":
        print(f"[WARN] نوع الرقم غير معروف: {number}")
        return {"number": number, "error": "رقم غير معروف النوع"}
    
    # تنظيف الرقم من أي مسافات أو رموز غير مرغوب فيها
    number = ''.join(filter(str.isdigit, number))
    
    # الحصول على بيانات الاستهلاك من قاعدة البيانات
    consumption_data = get_consumption_data(number)

    # إنشاء معرف المعاملة وتوكن المصادقة
    transid = gen_transid()  # رقم عشوائي مكون من 10 أرقام
    token = generate_token(USERNAME, PASSWORD, transid, number)  # توكن MD5 للمصادقة

    try:
        # اختيار الـ endpoint المناسب حسب نوع الرقم
        if ntype == "yemen4g":
            # نقطة نهاية خاصة بأرقام يمن فور جي
            url = f"{DOMAIN}/yem4g?mobile={number}&transid={transid}&token={token}&userid={USERID}&action=query"
        else:
            # نقطة نهاية عامة لأرقام يمن نت وغيرها
            url = f"{DOMAIN}/post?action=query&mobile={number}&transid={transid}&token={token}&userid={USERID}&action=query&type=adsl"
        
        print(f"[INFO] جارٍ إرسال طلب الاستعلام إلى: {url}")

        # إرسال طلب HTTP GET مع timeout 30 ثانية
        r = requests.get(url, timeout=60)
        r.raise_for_status()  # رفع استثناء في حالة وجود خطأ HTTP
        
        # معالجة الاستجابة من الخادم
        if r.headers.get("Content-Type", "").startswith("application/json"): #or r.headers.get("Content-Type", "").startswith("text/html"):
            if r.headers.get("Content-Type", "").startswith("application/json"):
                data = r.json()
            else:
               try:
                   match = re.search(r'\{.*\}', r.text, re.DOTALL)
                   if match:
                        json_part = match.group(0)
                        data = json.loads(json_part)  # نحوله إلى dict
                   else:
                        print("❌ لم يتم العثور على JSON في النص")
                   
               except json.JSONDecodeError as e:
                   print("خطأ في تحويل JSON:", e)

                # data = {"raw": r.text}
                # print(r)
                # data=data.json()
            print(f"[DEBUG] استجابة API: resultCode={data.get('resultCode')}")
            
            # التحقق من نجاح العملية (resultCode = "0" يعني نجاح)
            if data.get("resultCode") == "0":
                print(f"[DEBUG] نجح الاستعلام، سيتم حفظ البيانات في number_history")
                # استخراج البيانات الحالية من الاستجابة
                current_balance = data.get('avblnce', '')  # الرصيد الحالي
                current_balance_value = extract_balance_value(current_balance)  # القيمة الرقمية للرصيد
                package_value = data.get('baga_amount', 0)  # قيمة الباقة بالريال
                expiry_date = data.get('expdate', '')  # تاريخ انتهاء الباقة
                min_payment = data.get('minamtobill', '')  # أقل مبلغ سداد
                speed = data.get('speed', '')  # سرعة الإنترنت
                
                # حساب الأيام المتبقية مع حالة الباقة
                days_text, days_count, package_status = calculate_days_remaining(expiry_date)
                
                # تحديث قاعدة البيانات بالبيانات الجديدة
                with db_conn() as conn:
                    c = conn.cursor()
                    now = datetime.utcnow().isoformat()  # الوقت الحالي بتنسيق ISO
                    
                    # الحصول على بيانات الرقم الحالية من قاعدة البيانات
                    c.execute("SELECT id FROM numbers WHERE number = ?", (number,))
                    current_data = c.fetchone()
                    
                    if current_data:
                        # تحديث الرقم الموجود
                        c.execute(
                            """
                            UPDATE numbers 
                            SET last_balance = ?, 
                                last_balance_value = ?, 
                                last_balance_timestamp = ?,
                                type = ?
                            WHERE id = ?
                            """,
                            (current_balance, current_balance_value, now, ntype, current_data[0])
                        )
                        number_id = current_data[0]
                    else:
                        # إدراج رقم جديد (افتراضياً للعميل رقم 1)
                        c.execute(
                            """
                            INSERT INTO numbers (client_id, number, type, last_balance, 
                                             last_balance_value, last_balance_timestamp)
                            VALUES (1, ?, ?, ?, ?, ?)
                            """,
                            (number, ntype, current_balance, current_balance_value, now)
                        )
                        number_id = c.lastrowid
                    
                    # إضافة السجل الجديد لتاريخ الاستعلامات
                    print(f"[DEBUG] حفظ سجل جديد في number_history للرقم {number} (ID: {number_id})")
                    print(f"[DEBUG] البيانات: balance={current_balance}, balance_value={current_balance_value}")
                    c.execute(
                        """
                        INSERT INTO number_history 
                        (number_id, balance, balance_value, package_value, expiry_date, 
                         min_payment, speed, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (number_id, current_balance, current_balance_value, package_value,
                         expiry_date, min_payment, speed, now)
                    )
                    print(f"[DEBUG] تم حفظ السجل بنجاح في number_history")
                    
                    conn.commit()  # حفظ التغييرات
                
                # تنسيق موحد ومحسن لجميع أنواع الأرقام
                formatted = [
                    f"📱 الرقم: {number} ({'يمن فور جي' if ntype == 'yemen4g' else 'يمن نت'})",
                    f"📊 الرصيد الحالي: {current_balance}",
                    f"💵 قيمة الباقة: {package_value} ريال",
                    f"📅 تاريخ الانتهاء: {expiry_date}",
                    f"⏰ الأيام المتبقية: {days_text}"
                ]
                
                # إضافة معلومات الاستهلاك إذا كانت متوفرة
                # if consumption_data['has_previous']:
                #     formatted.append(f"🔄 آخر تحديث: {time_diff}")
                #     if consumption > 0:
                #         formatted.append(f"📉 الاستهلاك: {consumption:.2f} جيجا")
                #     elif consumption == 0:
                #         formatted.append(f"✅ لا يوجد استهلاك منذ آخر تقرير")
                
                # إضافة أقل مبلغ سداد إذا كان أكبر من صفر
                if min_payment and float(min_payment or 0) > 0:
                    formatted.append(f"💳 أقل مبلغ سداد: {min_payment} ريال")
                
                # إضافة سرعة الإنترنت إذا كانت متوفرة
                if speed and speed.strip():
                    formatted.append(f"⚡ سرعة الإنترنت: {speed}")
                
                # إضافة تحذيرات حسب حالة الباقة
                if package_status == "expired":
                    formatted.append(f"\n⚠️ تنبيه: الباقة منتهية! يرجى التجديد")
                elif package_status == "critical":
                    formatted.append(f"\n⚠️ تنبيه: الباقة تنتهي قريباً!")
                elif package_status == "expires_today":
                    formatted.append(f"\n🚨 تحذير: الباقة تنتهي اليوم!")
                    
                data["formatted"] = "\n".join(formatted)
                print(f"[DEBUG] تم تنسيق الرد: {data['formatted']}")
            else:
                # في حالة فشل الاستعلام (resultCode != "0")
                error_msg = data.get('resultDesc', 'خطأ غير معروف في الاستعلام')
                print(f"[ERROR] فشل الاستعلام للرقم {number}: {error_msg}")
                return {"number": number, "type": ntype, "error": error_msg}
        else:
            # في حالة عدم كون الرد JSON
            data = {"raw": r.text}
            print(f"[WARN] استجابة غير متوقعة (ليست JSON): {r.text[:200]}...")
            query,result = add_query(number, r.text, is_daily=False)
            result={"raw": result}
            print("الاستهلاك منذ آخر تقرير:", query.consumption_since_last)
            print("الاستهلاك اليومي:", query.daily_consumption)
            print("الملاحظات:", query.notes)
            print("الفرق الزمني منذ آخر استعلام:", query.time_since_last)
            
        print(f"[INFO] تم استلام الرد بنجاح: {data}")
        return {"number": number, "type": ntype, "data": result,"query":result}
    except Exception as e:
        print(f"[ERROR] خطأ في استعلام الرقم {number}: {str(e)}")
        return {"number": number, "type": ntype, "error": str(e),"query":result}
    

# ========= Admin REST =========

# دالة لتنسيق التاريخ العربي
def format_datetime_ar(dt):
    if not dt:
        return "—"
    months = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
              "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
    return f"{dt.day} {months[dt.month-1]} {dt.year} - {dt.hour:02d}:{dt.minute:02d}"

# دالة لتنسيق الفارق الزمني
def format_time_ar(td):
    if not td:
        return "—"
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}س:{minutes:02d}د:{seconds:02d}ث"

# عرض كل سجلات الاستعلام (يمكنك حذفه إذا تريد فقط صفحة العميل)
@app.route("/queries")
def all_queries():
    qset = Query.query.order_by(Query.query_time.desc()).all()
    return render_template("queries.html", queries=qset, datetime_ar=format_datetime_ar)

# عرض سجلات استعلام لعميل محدد
@app.route("/queries/<int:customer_id>", endpoint="queries")
def customer_queries(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    qset = Query.query.filter(Query.customer_id == customer.id).order_by(Query.query_time.desc()).all()

    # فلترة حسب الاستعلام اليومي إذا طلب
    filter_daily = request.args.get("daily")
    if filter_daily == "yes":
        qset = [q for q in qset if q.daily]
    elif filter_daily == "no":
        qset = [q for q in qset if not q.daily]

    return render_template("queries.html", queries=qset, datetime_ar=format_datetime_ar, customer_name=customer.name, customer_id=customer.id)

# مسار إرسال تقرير
@app.route("/send_report/<int:query_id>", methods=["POST"])
def send_report(query_id):
    query = Query.query.get_or_404(query_id)
    # منطق إرسال التقرير هنا (مثلاً WhatsApp أو email)
    flash(f"✅ تم إرسال التقرير للرقم {query.phone_number}", "success")
    return redirect(url_for("customer_queries", customer_id=query.customer_id))



@app.post("/admin/client")
def add_client():
    payload = request.get_json(force=True)
    name = payload.get("name")
    whatsapp = payload.get("whatsapp")
    if not (name and whatsapp):
        return jsonify({"ok": False, "error": "name & whatsapp مطلوبة"}), 400
    with db_conn() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO clients (name, whatsapp) VALUES (?,?)", (name, whatsapp))
        conn.commit()
        return jsonify({"ok": True, "id": c.lastrowid})

@app.post("/admin/number")
def add_number():
    payload = request.get_json(force=True)
    client_id = payload.get("client_id")
    number = payload.get("number")
    ntype = detect_type(number)
    if ntype == "unknown":
        return jsonify({"ok": False, "error": "لا يمكن تحديد نوع الرقم"}), 400
    with db_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT OR IGNORE INTO numbers (client_id, number, type) VALUES (?,?,?)",
            (client_id, number, ntype),
        )
        conn.commit()
        return jsonify({"ok": True})

@app.get("/admin/clients")
def list_clients():
    with db_conn() as conn:
        c = conn.cursor()
        rows = [
            {"id": r[0], "name": r[1], "whatsapp": r[2]}
            for r in c.execute("SELECT id,name,whatsapp FROM clients ORDER BY id DESC")
        ]
    return jsonify(rows)

@app.get("/admin/numbers/<int:client_id>")
def list_numbers(client_id):
    with db_conn() as conn:
        c = conn.cursor()
        rows = [
            {"id": r[0], "number": r[1], "type": r[2]}
            for r in c.execute(
                "SELECT id,number,type FROM numbers WHERE client_id=? ORDER BY id",
                (client_id,),
            )
        ]
    return jsonify(rows)

# ========= Webhook =========
@app.post("/webhook/whatsapp")
def whatsapp_webhook():
    print("\n[INFO] تم استلام طلب ويب هوك جديد")
    payload = request.get_json(force=True)
    from_phone = payload.get("fromNumber")
    body = (payload.get("messageBody") or "").strip()
    print(f"[INFO] من: {from_phone}, الرسالة: {body}")

    with db_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM clients WHERE whatsapp=?", (from_phone,))
        row = c.fetchone()

    if not row:
        print(f"[INFO] رقم غير مسجل: {from_phone}")
        return jsonify({"ok": True})

    client_id = row[0]
    print(f"[DEBUG] معالجة رسالة من العميل {client_id}")

    # قائمة الأوامر المسموحة
    ALLOWED_COMMANDS = ["تقرير", "report"]
    
    # تجاهل الرسائل التي لا تحتوي على أوامر مسموحة
    if body.lower() not in [cmd.lower() for cmd in ALLOWED_COMMANDS]:
        print(f"[INFO] تم تجاهل رسالة غير مرغوب فيها: {body}")
        return jsonify({"ok": True})

    # معالجة أمر التقرير
    if body == "تقرير" or body.lower() == "report":
        print(f"[INFO] طلب تقرير من العميل {client_id}")
        with db_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT number,type FROM numbers WHERE client_id=? ORDER BY id", (client_id,))
            nums = c.fetchall()
            print(f"[INFO] تم العثور على {len(nums)} أرقام مسجلة")

        if not nums:
            try:
                send_whatsapp(from_phone, "⚠️ لا توجد أرقام مرتبطة بحسابك.")
            except Exception as e:
                print(f"[ERROR] فشل إرسال رسالة الخطأ: {str(e)}")
            return jsonify({"ok": True})

        results = []
        resultsn = []
        for (num, ntype) in nums:
            try:
                print(f"[DEBUG] جاري استعلام الرقم: {num} (النوع: {ntype})")
                res = query_number(num)
                results.append(res)
                
                with db_conn() as conn:
                    c = conn.cursor()
                    # حفظ في جدول logs
                    c.execute(
                        "INSERT INTO logs (client_id, number, type, response, created_at) VALUES (?,?,?,?,?)",
                        (client_id, num, ntype, json.dumps(res, ensure_ascii=False), datetime.utcnow().isoformat()),
                    )
                    
                    # حفظ في جدول number_history إذا كان الاستعلام ناجحاً
                    if res.get('data', {}).get('raw'):
                        # العثور على number_id
                        c.execute("SELECT id FROM numbers WHERE number=? AND client_id=?", (num, client_id))
                        number_row = c.fetchone()
                        if number_row:
                            number_id = number_row[0]
                            
                            # استخراج البيانات من النتيجة باستخدام تحليل النص
                            try:
                                raw_data = json.loads(res['data']['raw'])
                                
                                # استخراج النص الكامل من balance
                                full_balance_text = raw_data.get('balance', 'غير متوفر')
                                
                                # تحليل النص لاستخراج البيانات المختلفة
                                balance = 'غير متوفر'
                                balance_value = 0.0
                                package_value = 0.0
                                expiry_date = ''
                                min_payment = ''
                                speed = ''
                                
                                if full_balance_text and full_balance_text != 'غير متوفر':
                                    # استخراج رصيد الباقة
                                    if 'رصيد الباقة:' in full_balance_text:
                                        balance_part = full_balance_text.split('رصيد الباقة:')[1].split('قيمة الباقة:')[0].strip()
                                        balance = balance_part
                                        
                                        # استخراج القيمة الرقمية للرصيد
                                        if 'GB' in balance or 'Gigabyte' in balance:
                                            try:
                                                balance_value = float(balance.split()[0])
                                            except:
                                                balance_value = 0.0
                                    
                                    # استخراج قيمة الباقة
                                    if 'قيمة الباقة:' in full_balance_text:
                                        # البحث عن النهاية المناسبة (تأريخ أو تاريخ)
                                        package_part = full_balance_text.split('قيمة الباقة:')[1]
                                        if 'تأريخ الانتهاء:' in package_part:
                                            package_part = package_part.split('تأريخ الانتهاء:')[0].strip()
                                        elif 'تاريخ الانتهاء:' in package_part:
                                            package_part = package_part.split('تاريخ الانتهاء:')[0].strip()
                                        
                                        try:
                                            # إزالة أي نص إضافي والحصول على الرقم فقط
                                            package_value = float(package_part.replace('ريال', '').strip())
                                        except:
                                            try:
                                                # محاولة استخراج الرقم من النص
                                                import re
                                                numbers = re.findall(r'\d+', package_part)
                                                if numbers:
                                                    package_value = float(numbers[0])
                                            except:
                                                package_value = 0.0
                                    
                                    # استخراج تاريخ الانتهاء (تأريخ أو تاريخ)
                                    expiry_key = None
                                    if 'تأريخ الانتهاء:' in full_balance_text:
                                        expiry_key = 'تأريخ الانتهاء:'
                                    elif 'تاريخ الانتهاء:' in full_balance_text:
                                        expiry_key = 'تاريخ الانتهاء:'
                                    
                                    if expiry_key:
                                        expiry_part = full_balance_text.split(expiry_key)[1]
                                        if 'اقل مبلغ سداد:' in expiry_part:
                                            expiry_part = expiry_part.split('اقل مبلغ سداد:')[0].strip()
                                        elif 'أقل مبلغ سداد:' in expiry_part:
                                            expiry_part = expiry_part.split('أقل مبلغ سداد:')[0].strip()
                                        else:
                                            expiry_part = expiry_part.strip()
                                        expiry_date = expiry_part
                                    
                                    # استخراج أقل مبلغ سداد (اقل أو أقل)
                                    payment_key = None
                                    if 'اقل مبلغ سداد:' in full_balance_text:
                                        payment_key = 'اقل مبلغ سداد:'
                                    elif 'أقل مبلغ سداد:' in full_balance_text:
                                        payment_key = 'أقل مبلغ سداد:'
                                    
                                    if payment_key:
                                        payment_part = full_balance_text.split(payment_key)[1]
                                        if 'السرعة:' in payment_part:
                                            payment_part = payment_part.split('السرعة:')[0].strip()
                                        else:
                                            payment_part = payment_part.strip()
                                        min_payment = payment_part
                                    
                                    # استخراج السرعة
                                    if 'السرعة:' in full_balance_text:
                                        speed_part = full_balance_text.split('السرعة:')[1].strip()
                                        speed = speed_part
                                
                            except Exception as e:
                                print(f"[ERROR] خطأ في استخراج البيانات: {str(e)}")
                                balance = res.get('data', {}).get('balance', 'غير متوفر')
                                balance_value = 0.0
                                package_value = 0.0
                                expiry_date = ''
                                min_payment = ''
                                speed = ''
                            
                            # إدراج في number_history
                            c.execute("""
                                INSERT INTO number_history 
                                (number_id, balance, balance_value, package_value, expiry_date, min_payment, speed, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (number_id, balance, balance_value, package_value, expiry_date, min_payment, speed, datetime.utcnow().isoformat()))
                            
                            # تحديث آخر بيانات في جدول numbers
                            c.execute("""
                                UPDATE numbers 
                                SET last_balance=?, last_balance_value=?, last_balance_timestamp=?
                                WHERE id=?
                            """, (balance, balance_value, datetime.utcnow().isoformat(), number_id))
                    
                    conn.commit()
            except Exception as e:
                print(f"[ERROR] خطأ في معالجة الرقم {num}: {str(e)}")
                results.append({"number": num, "type": ntype, "error": f"خطأ في المعالجة: {str(e)}"})

        try:
            report2=format_arabic_reportnew(results, client_id)
            report = format_arabic_report(results, client_id)
            send_whatsapp(from_phone, report)
            print(f"[INFO] تم إرسال التقرير بنجاح إلى {from_phone}")
            send_whatsapp(from_phone, report2)
            print(f"[INFO] تم إرسال التقرير بنجاح إلى {from_phone}")
        except Exception as e:
            print(f"[ERROR] فشل إرسال التقرير: {str(e)}")
            try:
                send_whatsapp(from_phone, "⚠️ حدث خطأ أثناء معالجة طلبك. يرجى المحاولة لاحقاً.")
            except Exception:
                pass
                
    return jsonify({"ok": True})
    

# ========= Dashboard (web) =========
@app.route('/login', methods=['GET', 'POST'])
def login():
    """صفحة تسجيل دخول المدير"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            flash('تم تسجيل الدخول بنجاح', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """تسجيل خروج المدير"""
    session.pop('logged_in', None)
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('login'))

@app.route('/')
def index():
    """الصفحة الرئيسية - توجيه للوحة الإدارة"""
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    """صفحة لوحة الإدارة لإضافة وتعديل العملاء والأرقام"""
    with db_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT c.id, c.name, c.whatsapp, 
                   COUNT(n.id) as number_count,
                   GROUP_CONCAT(n.number) as numbers
            FROM clients c
            LEFT JOIN numbers n ON c.id = n.client_id
            GROUP BY c.id, c.name, c.whatsapp
        """)
        clients = c.fetchall()
    
    return render_template('dashboard.html', clients=clients)

@app.route('/client/<int:client_id>')
@login_required
def client_detail(client_id):
    """صفحة تفاصيل العميل مع أرقامه"""
    with db_conn() as conn:
        c = conn.cursor()
        
        # جلب بيانات العميل
        c.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
        client = c.fetchone()
        
        if not client:
            return "العميل غير موجود", 404
            
        # تحويل إلى dict
        client = {
            'id': client[0],
            'name': client[1], 
            'whatsapp': client[2],
            'created_at': client[3] if len(client) > 3 else None
        }
        
        # جلب أرقام العميل
        c.execute("""
            SELECT id, number, type, last_balance, last_balance_value, last_balance_timestamp
            FROM numbers 
            WHERE client_id = ? 
            ORDER BY id DESC
        """, (client_id,))
        
        numbers = []
        for row in c.fetchall():
            numbers.append({
                'id': row[0],
                'number': row[1],
                'type': row[2],
                'last_balance': row[3],
                'last_balance_value': row[4],
                'last_balance_timestamp': row[5]
            })
    
    return render_template('client_detail.html', client=client, numbers=numbers)

@app.route('/history')
@login_required
def history():
    """صفحة عرض سجلات الاستعلام"""
    with db_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT 
                nh.id,
                n.number,
                n.type,
                nh.balance,
                nh.balance_value,
                nh.package_value,
                nh.expiry_date,
                nh.min_payment,
                nh.speed,
                nh.created_at,
                c.name as client_name
            FROM number_history nh
            JOIN numbers n ON nh.number_id = n.id
            LEFT JOIN clients c ON n.client_id = c.id
            ORDER BY nh.created_at DESC
            LIMIT 100
        """)
        history_records = c.fetchall()
        
        # إحصائيات سريعة
        c.execute("SELECT COUNT(*) FROM number_history")
        total_queries = c.fetchone()[0]
        
        c.execute("""
            SELECT COUNT(DISTINCT number_id) 
            FROM number_history 
            WHERE DATE(created_at) = DATE('now')
        """)
        today_numbers = c.fetchone()[0]
    
    return render_template('history.html', 
                         history_records=history_records,
                         total_queries=total_queries,
                         today_numbers=today_numbers)

@app.route('/api/query_test/<number>')
def test_query(number):
    """API لاختبار استعلام رقم واحد مع حفظ النتائج"""
    try:
        result = query_number(number)
        
      
        # حفظ النتيجة في number_history إذا كان الاستعلام ناجحاً
        if result.get('data', {}).get('raw'):
            try:
                import json
                from datetime import datetime
                
                raw_data = json.loads(result['data']['raw'])
                if raw_data.get("resultCode") == "0":
                    with db_conn() as conn:
                        c = conn.cursor()
                        now = datetime.utcnow().isoformat()
                        
                        # البحث عن الرقم أو إنشاؤه
                        c.execute("SELECT id FROM numbers WHERE number = ?", (number,))
                        number_record = c.fetchone()
                        
                        if not number_record:
                            # إنشاء رقم جديد (افتراضياً للعميل رقم 1)
                            c.execute(
                                "INSERT INTO numbers (client_id, number, type) VALUES (1, ?, ?)",
                                (number, result.get('type', 'unknown'))
                            )
                            number_id = c.lastrowid
                        else:
                            number_id = number_record[0]
                        
                        # استخراج البيانات بتحليل النص
                        full_balance_text = raw_data.get('balance', raw_data.get('avblnce', 'غير متوفر'))
                        
                        # تحليل النص لاستخراج البيانات المختلفة
                        balance = 'غير متوفر'
                        balance_value = 0.0
                        package_value = 0.0
                        expiry_date = ''
                        min_payment = ''
                        speed = ''
                        
                        if full_balance_text and full_balance_text != 'غير متوفر':
                            # استخراج رصيد الباقة
                            if 'رصيد الباقة:' in full_balance_text:
                                balance_part = full_balance_text.split('رصيد الباقة:')[1].split('قيمة الباقة:')[0].strip()
                                balance = balance_part
                                
                                # استخراج القيمة الرقمية للرصيد
                                if 'GB' in balance or 'Gigabyte' in balance:
                                    try:
                                        balance_value = float(balance.split()[0])
                                    except:
                                        balance_value = 0.0
                            
                            # استخراج قيمة الباقة
                            if 'قيمة الباقة:' in full_balance_text:
                                # البحث عن النهاية المناسبة (تأريخ أو تاريخ)
                                package_part = full_balance_text.split('قيمة الباقة:')[1]
                                if 'تأريخ الانتهاء:' in package_part:
                                    package_part = package_part.split('تأريخ الانتهاء:')[0].strip()
                                elif 'تاريخ الانتهاء:' in package_part:
                                    package_part = package_part.split('تاريخ الانتهاء:')[0].strip()
                                
                                try:
                                    # إزالة أي نص إضافي والحصول على الرقم فقط
                                    package_value = float(package_part.replace('ريال', '').strip())
                                except:
                                    try:
                                        # محاولة استخراج الرقم من النص
                                        import re
                                        numbers = re.findall(r'\d+', package_part)
                                        if numbers:
                                            package_value = float(numbers[0])
                                    except:
                                        package_value = 0.0
                            
                            # استخراج تاريخ الانتهاء (تأريخ أو تاريخ)
                            expiry_key = None
                            if 'تأريخ الانتهاء:' in full_balance_text:
                                expiry_key = 'تأريخ الانتهاء:'
                            elif 'تاريخ الانتهاء:' in full_balance_text:
                                expiry_key = 'تاريخ الانتهاء:'
                            
                            if expiry_key:
                                expiry_part = full_balance_text.split(expiry_key)[1]
                                if 'اقل مبلغ سداد:' in expiry_part:
                                    expiry_part = expiry_part.split('اقل مبلغ سداد:')[0].strip()
                                elif 'أقل مبلغ سداد:' in expiry_part:
                                    expiry_part = expiry_part.split('أقل مبلغ سداد:')[0].strip()
                                else:
                                    expiry_part = expiry_part.strip()
                                expiry_date = expiry_part
                            
                            # استخراج أقل مبلغ سداد (اقل أو أقل)
                            payment_key = None
                            if 'اقل مبلغ سداد:' in full_balance_text:
                                payment_key = 'اقل مبلغ سداد:'
                            elif 'أقل مبلغ سداد:' in full_balance_text:
                                payment_key = 'أقل مبلغ سداد:'
                            
                            if payment_key:
                                payment_part = full_balance_text.split(payment_key)[1]
                                if 'السرعة:' in payment_part:
                                    payment_part = payment_part.split('السرعة:')[0].strip()
                                else:
                                    payment_part = payment_part.strip()
                                min_payment = payment_part
                            
                            # استخراج السرعة
                            if 'السرعة:' in full_balance_text:
                                speed_part = full_balance_text.split('السرعة:')[1].strip()
                                speed = speed_part
                        
                        # حفظ السجل في number_history
                        c.execute(
                            """
                            INSERT INTO number_history 
                            (number_id, balance, balance_value, package_value, expiry_date, 
                             min_payment, speed, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                number_id,
                                balance,
                                balance_value,
                                package_value,
                                expiry_date,
                                min_payment,
                                speed,
                                now
                            )
                        )
                        
                        # تحديث آخر بيانات في جدول numbers
                        c.execute("""
                            UPDATE numbers 
                            SET last_balance=?, last_balance_value=?, last_balance_timestamp=?
                            WHERE id=?
                        """, (balance, balance_value, now, number_id))
                        conn.commit()
                        print(f"[INFO] تم حفظ نتيجة الاستعلام للرقم {number} في السجلات")
                        
            except Exception as save_error:
                print(f"[ERROR] فشل حفظ النتيجة في السجلات: {str(save_error)}")
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.post("/dashboard/add_client")
def dashboard_add_client():
    name = request.form.get("name")
    wa = request.form.get("whatsapp")
    with db_conn() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO clients (name, whatsapp) VALUES (?,?)", (name, wa))
        conn.commit()
    return redirect(url_for('dashboard'))

# إضافة رقم جديد لعميل
@app.post("/dashboard/add_number")
def dashboard_add_number():
    client_id = request.form.get("client_id")
    number = request.form.get("number")
    number_type = request.form.get("type", "yemenet")  # افتراضي يمن نت
    
    with db_conn() as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO numbers (client_id, number, type) VALUES (?,?,?)", 
                 (client_id, number, number_type))
        conn.commit()
    
    # إعادة توجيه إلى صفحة تفاصيل العميل إذا كان الطلب من هناك
    if request.referrer and f"/client/{client_id}" in request.referrer:
        return redirect(f"/client/{client_id}")
    return redirect(url_for('dashboard'))
@app.route('/dashboard/add_numbernew',methods=['POST'])
def add_number_new():
    client_id = request.form.get('client_id')
    number_value = request.form.get('number')
    number_type = request.form.get('type')

    if not all([client_id, number_value, number_type]):
        flash("يرجى إدخال جميع البيانات", "danger")
        return redirect(request.referrer)

    # إنشاء الرقم الجديد
    new_number = Number(
        client_id=int(client_id),
        number=number_value,
        type=number_type
    )
    db.session.add(new_number)
    db.session.commit()

    flash("✅ تم إضافة الرقم بنجاح", "success")
    return redirect(request.referrer)


# تعديل رقم
@app.post("/dashboard/edit_number")
def dashboard_edit_number():
    number_id = request.form.get("number_id")
    number = request.form.get("number")
    number_type = request.form.get("type")
    
    with db_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE numbers SET number=?, type=? WHERE id=?", 
                 (number, number_type, number_id))
        conn.commit()
        
        # الحصول على client_id للإعادة التوجيه
        c.execute("SELECT client_id FROM numbers WHERE id=?", (number_id,))
        client_id = c.fetchone()[0]
    
    if request.referrer and "/client/" in request.referrer:
        return redirect(f"/client/{client_id}")
    return redirect(url_for('dashboard'))

# حذف رقم
@app.post("/dashboard/delete_number")
def dashboard_delete_number():
    number_id = request.form.get("number_id")
    
    with db_conn() as conn:
        c = conn.cursor()
        # الحصول على client_id قبل الحذف
        c.execute("SELECT client_id FROM numbers WHERE id=?", (number_id,))
        result = c.fetchone()
        client_id = result[0] if result else None
        
        # حذف السجلات المرتبطة أولاً
        c.execute("DELETE FROM number_history WHERE number_id=?", (number_id,))
        # ثم حذف الرقم
        c.execute("DELETE FROM numbers WHERE id=?", (number_id,))
        conn.commit()
    
    if request.referrer and "/client/" in request.referrer and client_id:
        return redirect(f"/client/{client_id}")
    return redirect(url_for('dashboard'))


# Edit client
@app.post("/dashboard/edit_client")
def dashboard_edit_client():
    cid = request.form.get("client_id")
    name = request.form.get("name")
    wa = request.form.get("whatsapp")
    with db_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE clients SET name=?, whatsapp=? WHERE id=?", (name, wa, cid))
        conn.commit()
    return redirect(url_for('dashboard'))

# Delete client (and its numbers)
@app.post("/dashboard/delete_client")
def dashboard_delete_client():
    cid = request.form.get("client_id")
    with db_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM numbers WHERE client_id=?", (cid,))
        c.execute("DELETE FROM clients WHERE id=?", (cid,))
        conn.commit()
    return redirect(url_for('dashboard'))

# Delete number (الدالة المكررة محذوفة)
@app.post("/dashboard/delete_number_old")
def dashboard_delete_number_old():
    nid = request.form.get("number_id")
    with db_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM numbers WHERE id=?", (nid,))
        conn.commit()
    return redirect(url_for('dashboard'))


# ========= Routes لإدارة بوت واتساب =========

@app.route('/whatsapp')
@login_required
def whatsapp_dashboard():
    """الصفحة الرئيسية - لوحة إدارة بوت واتساب"""
    # التحقق من حالة خادم Node.js وتشغيله إذا لم يكن يعمل
    if not is_node_server_running():
        print("🚀 تشغيل خادم Node.js تلقائياً...")
        start_result = start_node_server()
        if start_result["success"]:
            print("✅ تم تشغيل خادم Node.js بنجاح")
            # انتظار قصير للتأكد من بدء التشغيل
            time.sleep(3)
        else:
            print(f"❌ فشل في تشغيل الخادم: {start_result['message']}")
    
    session_data = whatsapp_bot.get_session_data()
    stats = whatsapp_bot.get_database_stats()
    
    # جلب أحدث رمز QR من خادم Node.js
    try:
        response = requests.get('http://localhost:3000/api/qr', timeout=20)
        if response.status_code == 200:
            qr_data = response.json()
            if qr_data.get('success') and qr_data.get('qr'):
                session_data['qr_code'] = qr_data['qr']
                session_data['status'] = 'qr_generated'
    except Exception as e:
        print(f'خطأ في جلب رمز QR: {str(e)}')
    
    return render_template('public/index.html', 
                         session_data=session_data,
                         stats=stats)

@app.route('/api/whatsapp/status')
def api_whatsapp_status():
    """API محسن للحصول على حالة البوت"""
    try:
        # التحقق من حالة خادم Node.js
        node_running = is_node_server_running()
        
        if not node_running:
            return jsonify({
                "success": True,
                "status": "server_stopped",
                "session": {
                    "status": "disconnected",
                    "session_id": "unknown",
                    "phone_number": "الخادم متوقف",
                    "connected_at": None,
                    "qr_code": None
                },
                "server_status": {
                    "running": False,
                    "message": "خادم Node.js متوقف"
                }
            })
        
        # الحصول على بيانات الجلسة المحدثة
        session_data = whatsapp_bot.get_session_data()
        
        return jsonify({
            "success": True,
            "data": {
                "session": session_data,
                "stats": whatsapp_bot.get_database_stats()
            },
            "status": session_data.get('status', 'unknown'),
            "server_status": {
                "running": True,
                "message": "خادم Node.js يعمل"
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "status": "error",
            "message": f"خطأ في الحصول على الحالة: {str(e)}",
            "session": {
                "status": "error",
                "session_id": "error",
                "phone_number": "خطأ",
                "connected_at": None,
                "qr_code": None
            }
        })


@app.route('/api/whatsapp/connect', methods=['POST'])
@login_required
def api_whatsapp_connect():
    """API لبدء الاتصال مع النظام المحسن"""
    try:
        # التأكد من تشغيل خادم Node.js أولاً
        if not is_node_server_running():
            start_result = start_node_server()
            if not start_result["success"]:
                return jsonify({
                    "success": False,
                    "message": f"فشل في تشغيل الخادم: {start_result['message']}"
                })
            # انتظار قليل لبدء الخادم
            import time
            time.sleep(2)
        
        # التحقق من الجلسة الحالية قبل إرسال أمر الاتصال
        print("[تصحيح] فحص الجلسة الحالية قبل الاتصال...")
        
        # الحصول على البيانات الخام من Node.js للتشخيص
        try:
            raw_response = requests.get('http://localhost:3000/api/status', timeout=30)
            if raw_response.status_code == 200:
                raw_data = raw_response.json()
                print(f"[تصحيح] البيانات الخام من Node.js:")
                print(f"  - status: {raw_data.get('status')}")
                print(f"  - isConnected: {raw_data.get('isConnected')}")
                print(f"  - sessionId: {raw_data.get('sessionId')}")
                print(f"  - client_info موجود: {bool(raw_data.get('client_info'))}")
        except Exception as debug_error:
            print(f"[تصحيح] خطأ في جلب البيانات الخام: {debug_error}")
        
        session_data = whatsapp_bot.get_session_data()
        
        if session_data.get('status') == 'connected':
            print("[تصحيح] الجلسة متصلة بالفعل - لا حاجة لإرسال أمر connect")
            return jsonify({
                "success": True,
                "message": "البوت متصل بالفعل",
                "status": "already_connected",
                "session_data": session_data
            })
        elif session_data.get('status') == 'initializing':
            print("[تصحيح] العميل قيد التهيئة - تجاهل طلب الاتصال")
            return jsonify({
                "success": True,
                "message": "العميل قيد التهيئة - يرجى الانتظار قليلاً",
                "status": "initializing",
                "session_data": session_data
            })
        
        print(f"[تصحيح] حالة الجلسة الحالية: {session_data.get('status', 'غير محدد')}")
        print("[تصحيح] إرسال أمر الاتصال...")
        
        # إرسال أمر الاتصال فقط إذا لم تكن الجلسة متصلة
        result = whatsapp_bot.send_bot_command('connect')
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"خطأ في بدء الاتصال: {str(e)}"
        })

@app.route('/api/whatsapp/disconnect', methods=['POST'])
@login_required
def api_whatsapp_disconnect():
    """API لقطع الاتصال مع التنظيف الشامل"""
    try:
        result = whatsapp_bot.send_bot_command('disconnect')
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"خطأ في قطع الاتصال: {str(e)}"
        })

@app.route('/api/whatsapp/restart', methods=['POST'])
@login_required
def api_whatsapp_restart():
    """API لإعادة تشغيل البوت مع التنظيف الشامل"""
    try:
        result = whatsapp_bot.send_bot_command('restart')
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# API routes للتحكم بالبوت
@app.route('/api/bot/connect', methods=['POST'])
@login_required
def api_bot_connect():
    """بدء اتصال البوت"""
    try:
        result = whatsapp_bot.send_bot_command('connect')
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/bot/disconnect', methods=['POST'])
@login_required
def api_bot_disconnect():
    """قطع اتصال البوت"""
    try:
        result = whatsapp_bot.send_bot_command('disconnect')
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/bot/restart', methods=['POST'])
@login_required
def api_bot_restart():
    """إعادة تشغيل البوت"""
    try:
        result = whatsapp_bot.send_bot_command('restart')
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/bot/qr-refresh', methods=['POST'])
@login_required
def api_bot_qr_refresh():
    """تحديث رمز QR"""
    try:
        result = whatsapp_bot.send_bot_command('qr-refresh')
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/bot/send-message', methods=['POST'])
@login_required
def api_bot_send_message():
    """إرسال رسالة عبر البوت"""
    try:
        data = request.get_json()
        phone = data.get('phone')
        message = data.get('message')
        try:
            send_whatsapp(phone,message)
        except Exception as e:
            print(f"successmessage{e}")
        if not phone or not message:
            return jsonify({"success": False, "message": "رقم الهاتف والرسالة مطلوبان"})
        
        result = whatsapp_bot.send_bot_command('send-message', {
            'phone': phone,
            'message': message
        })
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/bot/logs')
@login_required
def api_bot_logs():
    """الحصول على سجل أنشطة البوت"""
    try:
        # قراءة آخر 20 سجل من ملف الجلسة أو قاعدة البيانات
        logs = []
        session_data = whatsapp_bot.get_session_data()
        
        if session_data:
            # يمكن إضافة المزيد من السجلات هنا
            logs.append({
                "timestamp": session_data.get('last_activity', 'غير محدد'),
                "level": "info",
                "message": f"حالة الجلسة: {session_data.get('status', 'غير معروف')}",
                "details": f"رقم الهاتف: {session_data.get('phone_number', 'غير محدد')}"
            })
        
        return jsonify({"success": True, "logs": logs})
    except Exception as e:
        return jsonify({"success": False, "message": str(e), "logs": []})

@app.route('/qr')
@login_required
def qr_page():
    """صفحة عرض رمز QR"""
    session_data = whatsapp_bot.get_session_data()
    qr_code = None
    
    if session_data and 'qr_code' in session_data:
        qr_code = session_data['qr_code']
    
    return render_template('qr_page.html', qr_code=qr_code, session_data=session_data)

@app.route('/sessions')
@login_required
def sessions_page():
    """صفحة إدارة الجلسات"""
    session_data = whatsapp_bot.get_session_data()
    
    # قراءة جميع الجلسات من الملف
    all_sessions = []
    try:
        if os.path.exists(SESSION_DATA_PATH):
            with open(SESSION_DATA_PATH, 'r', encoding='utf-8') as f:
                all_sessions = json.load(f)
    except Exception as e:
        flash(f'خطأ في قراءة بيانات الجلسات: {e}', 'error')
    
    return render_template('sessions_page.html', sessions=all_sessions, current_session=session_data)

@app.route('/database')
@login_required
def database_page():
    """صفحة إدارة قاعدة البيانات"""
    stats = whatsapp_bot.get_database_stats()
    
    # جلب إحصائيات إضافية
    with db_conn() as conn:
        c = conn.cursor()
        
        # آخر العملاء المضافين
        c.execute("SELECT name, whatsapp, rowid FROM clients ORDER BY rowid DESC LIMIT 5")
        recent_clients = c.fetchall()
        
        # آخر الأرقام المضافة
        c.execute("""
            SELECT n.number, n.type, c.name, n.rowid 
            FROM numbers n 
            JOIN clients c ON n.client_id = c.id 
            ORDER BY n.rowid DESC LIMIT 5
        """)
        recent_numbers = c.fetchall()
        
        # آخر السجلات
        c.execute("""
            SELECT l.number, l.type, c.name, l.created_at, l.rowid 
            FROM logs l 
            JOIN clients c ON l.client_id = c.id 
            ORDER BY l.rowid DESC LIMIT 10
        """)
        recent_logs = c.fetchall()
    
    return render_template('database_page.html', 
                         stats=stats, 
                         recent_clients=recent_clients,
                         recent_numbers=recent_numbers,
                         recent_logs=recent_logs)

@app.route('/send-message')
@login_required
def send_message_page():
    """صفحة إرسال الرسائل"""
    # جلب قوائم العملاء والأرقام للاختيار منها
    clients = []
    numbers = []
    
    with db_conn() as conn:
        c = conn.cursor()
        
        # جلب قائمة العملاء
        c.execute("SELECT id, name, whatsapp FROM clients ORDER BY name")
        clients = [{'id': row[0], 'name': row[1], 'whatsapp': row[2]} for row in c.fetchall()]
        
        # جلب قائمة الأرقام مع معلومات العملاء
        c.execute("""
            SELECT n.id, n.number, n.type, c.name, c.whatsapp 
            FROM numbers n 
            JOIN clients c ON n.client_id = c.id 
            ORDER BY n.number
        """)
        numbers = [{
            'id': row[0], 
            'number': row[1], 
            'type': row[2], 
            'client_name': row[3],
            'client_whatsapp': row[4]
        } for row in c.fetchall()]
    
    # جلب آخر الرسائل المرسلة
    recent_messages = []
    try:
        with open('message_logs.json', 'r', encoding='utf-8') as f:
            recent_messages = json.load(f)[-5:]  # آخر 5 رسائل
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    
    return render_template('send_message.html', 
                         clients=clients, 
                         numbers=numbers,
                         recent_messages=recent_messages)

@app.route('/settings')
@login_required
def settings_page():
    """صفحة إعدادات النظام"""
    # تحميل الإعدادات الحالية
    settings = {}
    try:
        if os.path.exists('settings.json'):
            with open('settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
    except Exception as e:
        flash(f'خطأ في تحميل الإعدادات: {e}', 'error')
    
    # إحصائيات النظام
    stats = {
        'total_users': 0,
        'total_clients': 0,
        'total_messages': 0,
        'disk_usage': '0 MB',
        'server_uptime': '0 يوم 00:00:00',
        'version': '1.0.0',
        'last_backup': 'غير متوفر'
    }
    
    # جلب إحصائيات قاعدة البيانات
    try:
        # تهيئة قاعدة البيانات إذا لم تكن موجودة
        init_db()
        
        with db_conn() as conn:
            c = conn.cursor()
            
            # التحقق من وجود الجداول أولاً
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if c.fetchone():
                # عدد المستخدمين
                c.execute("SELECT COUNT(*) FROM users")
                stats['total_users'] = c.fetchone()[0]
            else:
                stats['total_users'] = 0
                flash('جدول المستخدمين غير موجود', 'warning')
            
            # عدد العملاء
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clients'")
            if c.fetchone():
                c.execute("SELECT COUNT(*) FROM clients")
                stats['total_clients'] = c.fetchone()[0]
            else:
                stats['total_clients'] = 0
                flash('جدول العملاء غير موجود', 'warning')
            
            # عدد الرسائل
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='logs'")
            if c.fetchone():
                c.execute("SELECT COUNT(*) FROM logs")
                stats['total_messages'] = c.fetchone()[0]
            else:
                stats['total_messages'] = 0
                flash('جدول السجلات غير موجود', 'warning')
            
    except Exception as e:
        flash(f'خطأ في جلب إحصائيات قاعدة البيانات: {e}', 'error')
        # تعيين قيم افتراضية في حالة الخطأ
        stats['total_users'] = 0
        stats['total_clients'] = 0
        stats['total_messages'] = 0
    
    # حساب استخدام القرص (طريقة متوافقة مع Windows)
    try:
        import shutil
        total, used, free = shutil.disk_usage('.')
        total_gb = total / (1024 * 1024 * 1024)  # تحويل إلى جيجابايت
        used_gb = used / (1024 * 1024 * 1024)
        used_percent = (used / total) * 100
        stats['disk_usage'] = f'{used_gb:.1f} GB / {total_gb:.1f} GB ({used_percent:.1f}%)'
    except Exception as e:
        print(f'Error calculating disk usage: {e}')
        stats['disk_usage'] = 'غير متاح'
    
    # وقت تشغيل الخادم
    try:
        with open('.server_start_time', 'r') as f:
            start_time = float(f.read().strip())
            uptime = time.time() - start_time
            days = int(uptime // (24 * 3600))
            uptime = uptime % (24 * 3600)
            hours = int(uptime // 3600)
            uptime %= 3600
            minutes = int(uptime // 60)
            stats['server_uptime'] = f'{days} يوم {hours:02d}:{minutes:02d}'
    except:
        pass
    
    # آخر نسخة احتياطية
    try:
        if os.path.exists('backups'):
            backups = [f for f in os.listdir('backups') if f.endswith('.db')]
            if backups:
                last_backup = max(backups, key=lambda f: os.path.getmtime(os.path.join('backups', f)))
                stats['last_backup'] = time.strftime('%Y-%m-%d %H:%M', 
                                                  time.localtime(os.path.getmtime(os.path.join('backups', last_backup))))
    except:
        pass
    
    return render_template('settings.html', 
                         settings=settings, 
                         stats=stats,
                         current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))





def save_settings(settings):
    """حفظ الإعدادات في ملف JSON"""
    try:
        with open('settings.json', 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        return True, 'تم حفظ الإعدادات بنجاح'
    except Exception as e:
        return False, f'خطأ في حفظ الإعدادات: {str(e)}'

def create_database_backup():
    """إنشاء نسخة احتياطية من قاعدة البيانات"""
    try:
        # إنشاء مجلد النسخ الاحتياطي إذا لم يكن موجوداً
        backup_dir = Path('backups')
        backup_dir.mkdir(exist_ok=True)
        
        # إنشاء اسم ملف النسخة الاحتياطية
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = backup_dir / f'db_backup_{timestamp}.db'
        
        # نسخ الملف
        shutil.copy2(DB_PATH, backup_file)
        
        # حذف النسخ القديمة (الاحتفاظ بـ 5 نسخ فقط)
        backups = sorted(backup_dir.glob('db_backup_*.db'), key=os.path.getmtime, reverse=True)
        for old_backup in backups[5:]:
            old_backup.unlink()
            
        return True, 'تم إنشاء نسخة احتياطية بنجاح', backup_file.name
    except Exception as e:
        return False, f'خطأ في إنشاء نسخة احتياطية: {str(e)}', None

# ========= API Endpoints =========

# 🔹 هنا تعريف الـ model

# 🔹 هنا routes API
@app.route("/api/packages", methods=["GET"])
def get_packages():
    return jsonify([p.to_dict() for p in Package.query.all()])

@app.route("/api/packages", methods=["POST"])
def add_package():
    data = request.get_json()
    pkg = Package(value=data["value"], volume=data["volume"])
    db.session.add(pkg)
    db.session.commit()
    return jsonify(pkg.to_dict()), 201

@app.route("/api/packages/<int:pkg_id>", methods=["PUT"])
def update_package(pkg_id):
    pkg = Package.query.get_or_404(pkg_id)
    data = request.get_json()
    pkg.value = data.get("value", pkg.value)
    pkg.volume = data.get("volume", pkg.volume)
    db.session.commit()
    return jsonify(pkg.to_dict())

@app.route("/api/packages/<int:pkg_id>", methods=["DELETE"])
def delete_package(pkg_id):
    pkg = Package.query.get_or_404(pkg_id)
    db.session.delete(pkg)
    db.session.commit()
    return jsonify({"message": "deleted"})

# 🔹 صفحة HTML
@app.route('/packages')
def packages_page():
    return render_template('packages.html')

@app.route('/api/status')
def api_status():
    """API للحصول على حالة النظام - متوافق مع JavaScript الجديد"""
    try:
        # الحصول على بيانات الجلسة من خادم Node.js
        session_data = whatsapp_bot.get_session_data()
        database_stats = whatsapp_bot.get_database_stats()
        
        # إحصائيات النظام
        stats = {
            'clientReady': session_data.get('status') == 'connected',
            'sessionActive': bool(session_data.get('phone_number')),
            'errorCount': 0,
            'messageQueueLength': database_stats.get('total_messages', 0),
            'uptime': 0,
            'memoryUsage': {'used': 0},
            'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        try:
            with db_conn() as conn:
                c = conn.cursor()
                
                # عدد المستخدمين
                c.execute("SELECT COUNT(*) FROM users")
                stats['total_users'] = c.fetchone()[0]
                
                # عدد العملاء
                c.execute("SELECT COUNT(*) FROM clients")
                stats['total_clients'] = c.fetchone()[0]
                
                # عدد الرسائل
                c.execute("SELECT COUNT(*) FROM logs")
                stats['total_messages'] = c.fetchone()[0]
                
        except Exception as e:
            app.logger.error(f'خطأ في جلب إحصائيات قاعدة البيانات: {e}')
        
        return jsonify({
            'success': True,
            'data': {
                'session': {
                    'isClientReady': stats['clientReady'],
                    'hasQRCode': session_data.get('qr_code') is not None,
                    'sessionData': session_data,
                    'clientState': None,
                    'timestamp': stats['server_time'],
                    'isRestarting': False
                },
                'stats': stats
            },
            'status': 'connected' if stats['clientReady'] else 'disconnected',
            'server_time': stats['server_time']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'خطأ في جلب حالة النظام: {str(e)}'
        }), 500

@app.route('/api/messages/send', methods=['POST'])
@login_required
def api_messages_send():
    """API لإرسال رسالة"""
    try:
        data = request.get_json()
        print(f"{data}")
        # التحقق من البيانات المطلوبة
        if not data or 'to' not in data or 'message' not in data:
            return jsonify({
                'success': False,
                'message': 'بيانات غير صالحة. يرجى إدخال رقم الهاتف والرسالة.'
            }), 400
        
        # إرسال الرسالة عبر البوت مع التنسيق الصحيح
        try:
            print(f"Sending message to {data['to']} with content: {data['message'][:50]}...")  # Log message preview
            result = whatsapp_bot.send_bot_command('send-message', {
                'phone': data['to'],
                'message': data['message']
            })
            print(f"Bot command result: {result}")
        except Exception as e:
            print(f"Error in send_bot_command: {str(e)}")
            raise
        
        # حفظ سجل الرسالة
        if result.get('success', False):
            try:
                with open('message_logs.json', 'a+', encoding='utf-8') as f:
                    try:
                        f.seek(0)
                        messages = json.load(f)
                    except (json.JSONDecodeError, FileNotFoundError):
                        messages = []
                    
                    messages.append({
                        'to': data['to'],
                        'message': data['message'],
                        'timestamp': datetime.now().isoformat(),
                        'status': 'sent' if result.get('success') else 'failed',
                        'message_id': result.get('message_id')
                    })
                    
                    # الاحتفاظ فقط بـ 100 رسالة كحد أقصى
                    messages = messages[-100:]
                    
                    f.seek(0)
                    f.truncate()
                    json.dump(messages, f, ensure_ascii=False, indent=2)
            except Exception as e:
                app.logger.error(f'خطأ في حفظ سجل الرسالة: {e}')
        
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'حدث خطأ أثناء إرسال الرسالة: {str(e)}'
        }), 500

@app.route('/api/settings/save', methods=['POST'])
@login_required
def api_save_settings():
    """API لحفظ الإعدادات"""
    try:
        settings = request.get_json()
        success, message = save_settings(settings)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'خطأ في معالجة الطلب: {str(e)}'}), 500

@app.route('/api/backup/create', methods=['POST'])
@login_required
def api_create_backup():
    """API لإنشاء نسخة احتياطية"""
    try:
        success, message, filename = create_database_backup()
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'download_url': f'/download/backup/{filename}',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({'success': False, 'message': message}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'خطأ في إنشاء النسخة الاحتياطية: {str(e)}'}), 500

@app.route('/download/backup/<filename>')
@login_required
def download_backup(filename):
    """تحميل ملف النسخة الاحتياطية"""
    try:
        return send_from_directory(
            'backups',
            filename,
            as_attachment=True,
            download_name=f'whatsapp_bot_backup_{datetime.now().strftime("%Y%m%d")}.db'
        )
    except Exception as e:
        return jsonify({'success': False, 'message': f'خطأ في تحميل الملف: {str(e)}'}), 404

# API endpoints لإدارة خادم Node.js
@app.route('/api/node-server/status', methods=['GET'])
@login_required
def node_server_status():
    """الحصول على حالة خادم Node.js"""
    try:
        status = get_node_server_status()
        return jsonify({"success": True, "data": status})
    except Exception as e:
        return jsonify({"success": False, "message": f"خطأ في فحص حالة الخادم: {str(e)}"})

@app.route('/api/node-server/start', methods=['POST'])
@login_required
def start_node_server_api():
    """تشغيل خادم Node.js"""
    try:
        result = start_node_server()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": f"خطأ في تشغيل الخادم: {str(e)}"})

@app.route('/api/node-server/stop', methods=['POST'])
@login_required
def stop_node_server_api():
    """إيقاف خادم Node.js"""
    try:
        result = stop_node_server()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": f"خطأ في إيقاف الخادم: {str(e)}"})

@app.route('/api/node-server/restart', methods=['POST'])
@login_required
def restart_node_server_api():
    """إعادة تشغيل خادم Node.js"""
    try:
        # إيقاف الخادم أولاً
        stop_result = stop_node_server()
        if stop_result["success"] or "غير يعمل" in stop_result["message"]:
            # انتظار قصير ثم تشغيل الخادم
            time.sleep(1)
            start_result = start_node_server()
            return jsonify(start_result)
        else:
            return jsonify(stop_result)
    except Exception as e:
        return jsonify({"success": False, "message": f"خطأ في إعادة تشغيل الخادم: {str(e)}"})

# إضافة route لملف flutter_service_worker.js لتجنب خطأ 404
@app.route('/flutter_service_worker.js')
def flutter_service_worker():
    return 'console.log("Flutter service worker not needed");', 200, {'Content-Type': 'application/javascript'}

# متغير للتحكم في المراقبة
monitoring_enabled = True

# إضافة مراقبة صحة خادم Node.js وإعادة التشغيل التلقائي
def monitor_node_server():
    """مراقبة صحة خادم Node.js وإعادة تشغيله إذا لزم الأمر"""
    global node_server_process, node_server_status, monitoring_enabled
    
    while True:
        try:
            # فحص حالة الخادم كل دقيقة (بدلاً من 30 ثانية)
            time.sleep(120)
            
            # تجاهل المراقبة إذا تم إيقافها
            if not monitoring_enabled:
                continue
            
            # التحقق من أن العملية ما زالت تعمل (فقط إذا كان من المفترض أن تعمل)
            if node_server_status == "running" and node_server_process and node_server_process.poll() is not None:
                print("⚠️ تم اكتشاف توقف خادم Node.js - محاولة إعادة التشغيل...")
                node_server_status = "stopped"
                
                # محاولة إعادة التشغيل
                restart_result = start_node_server()
                if restart_result["success"]:
                    print("✅ تم إعادة تشغيل خادم Node.js بنجاح")
                else:
                    print(f"❌ فشل في إعادة تشغيل الخادم: {restart_result['message']}")
            
            # فحص الاتصال بالخادم (فقط إذا كان من المفترض أن يعمل)
            elif node_server_status == "running":
                try:
                    print(f"🔍 محاولة الاتصال بـ http://localhost:3000/api/health...")
                    response = requests.get("http://localhost:3000/api/health", timeout=1000)
                    print(f"✅ استجابة من خادم Node.js: {response.status_code}")
                    if response.status_code != 200:
                        print(f"⚠️ خادم Node.js يستجيب لكن برمز خطأ: {response.status_code}")
                        print(f"📄 محتوى الاستجابة: {response.text[:200]}")
                except requests.exceptions.ConnectionError as e:
                    print(f"❌ خطأ في الاتصال: الخادم غير متاح على البورت 3000")
                    print(f"   التفاصيل: {str(e)}")
                except requests.exceptions.Timeout as e:
                    print(f"⏰ انتهت مهلة الانتظار للاتصال بخادم Node.js")
                    print(f"   التفاصيل: {str(e)}")
                except requests.exceptions.RequestException as e:
                    print(f"❌ خطأ عام في طلب HTTP: {type(e).__name__}")
                    print(f"   التفاصيل: {str(e)}")
                except Exception as e:
                    print(f"❌ خطأ غير متوقع في المراقبة: {type(e).__name__}")
                    print(f"   التفاصيل: {str(e)}")
                    
        except Exception as e:
            print(f"❌ خطأ في مراقبة الخادم: {str(e)}")

# بدء مراقبة الخادم في thread منفصل
import threading
monitor_thread = threading.Thread(target=monitor_node_server, daemon=True)

if __name__ == '__main__':
   
    init_db()
    cli()
    with app.app_context():
       
        print("تم إنشاء قاعدة البيانات والجداول بنجاح")
    # إنشاء ملف لتتبع وقت بدء التشغيل
    with open('.server_start_time', 'w') as f:
        f.write(str(time.time()))
    
    # إنشاء مجلد النسخ الاحتياطي إذا لم يكن موجوداً
    os.makedirs('backups', exist_ok=True)
    
    # بدء مراقبة خادم Node.js
    monitor_thread.start()
    
    app.run(debug=True, host='0.0.0.0', port=5000)




