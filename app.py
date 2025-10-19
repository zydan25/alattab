# استيراد المكتبات المطلوبة
import hashlib  # لتشفير كلمات المرور وإنشاء التوكن
import json     # للتعامل مع ملفات JSON والبيانات
import random   # لإنشاء أرقام عشوائية للمعاملات
import sqlite3  # للتعامل مع قاعدة البيانات
import string   # للتعامل مع النصوص والأحرف
from datetime import datetime, timedelta, timezone, date  # للتعامل مع التواريخ والأوقات
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
    
    # الوقت الذي يتم فيه الاستعلام التلقائي يوميًا (مثلاً 08:00 صباحًا)
    auto_query_time = db.Column(db.Time, default=dt_time(8, 0))
    
    # حالة تفعيل الاستعلام التلقائي (افتراضي: مفعّل)
    auto_query_enabled = db.Column(db.Boolean, default=True, nullable=False)

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
    """جدول الأرقام مع بيانات الاستعلام اليومي"""
    __tablename__ = "numbers"
    
    # المعلومات الأساسية
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    client_id = db.Column(db.Integer, db.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    number = db.Column(db.String, nullable=False)
    type = db.Column(db.String, nullable=False)  # yemenet أو yemen4g
    
    # بيانات الباقة والرصيد (من آخر استعلام يومي)
    package_value = db.Column(db.Float, default=0.0)  # قيمة الباقة بالريال
    current_balance_gb = db.Column(db.Float, default=0.0)  # الرصيد الحالي بالجيجا
    
    # التواريخ والوقت
    expiry_date = db.Column(db.DateTime)  # تاريخ انتهاء الباقة
    days_remaining = db.Column(db.Integer)  # الأيام المتبقية
    current_query_time = db.Column(db.DateTime)  # وقت الاستعلام الحالي
    previous_query_time = db.Column(db.DateTime)  # وقت الاستعلام السابق (الأمس)
    
    # الاستهلاك اليومي (الفرق من الأمس)
    previous_balance_gb = db.Column(db.Float, default=0.0)  # الرصيد في الاستعلام السابق
    daily_consumption_gb = db.Column(db.Float, default=0.0)  # الاستهلاك اليومي = السابق - الحالي
    
    # المبالغ المالية
    amount_consumed = db.Column(db.Float, default=0.0)  # المبلغ المستهلك (ريال)
    amount_remaining = db.Column(db.Float, default=0.0)  # المبلغ المتبقي (ريال)
    
    # الحالة والملاحظات
    status = db.Column(db.String(20))  # الحالة: active, warning, critical, expired
    notes = db.Column(db.String(255))  # ملاحظات تلقائية (مثل: تم التسديد، قرب الانتهاء)
    
    # الحقول القديمة (للتوافق المؤقت)
    last_balance = db.Column(db.String)  # نص رصيد (مثلاً "67.95 GB")
    last_balance_value = db.Column(db.Float)  # قيمة الرصيد كرقم
    last_balance_timestamp = db.Column(db.String)  # تاريخ آخر استعلام كنص

    __table_args__ = (
        db.UniqueConstraint('client_id', 'number', name='uix_client_number'),
    )
    
    def __repr__(self):
        return f'<Number {self.number} - {self.current_balance_gb}GB>'


class DailyQuery(db.Model):
    """جدول الاستعلامات اليومية - سجل تاريخي يومي"""
    __tablename__ = "daily_queries"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    number_id = db.Column(db.Integer, db.ForeignKey("numbers.id", ondelete="CASCADE"), nullable=False)
    query_date = db.Column(db.Date, nullable=False, index=True)  # تاريخ الاستعلام (يوم فقط)
    query_time = db.Column(db.DateTime, default=datetime.utcnow)  # الوقت الكامل
    
    # بيانات الباقة والرصيد
    package_value = db.Column(db.Float, default=0.0)
    balance_gb = db.Column(db.Float, default=0.0)
    
    # التواريخ
    expiry_date = db.Column(db.DateTime)
    days_remaining = db.Column(db.Integer)
    
    # الاستهلاك اليومي
    daily_consumption_gb = db.Column(db.Float, default=0.0)
    
    # المبالغ المالية
    amount_consumed = db.Column(db.Float, default=0.0)
    amount_remaining = db.Column(db.Float, default=0.0)
    
    # الحالة
    status = db.Column(db.String(20))  # active, warning, critical, expired
    notes = db.Column(db.String(255))
    
    # البيانات الخام (للرجوع إليها عند الحاجة)
    raw_data = db.Column(db.Text)
    
    # العلاقات
    number = db.relationship("Number", backref="daily_queries", lazy=True)
    
    __table_args__ = (
        # لضمان استعلام واحد فقط لكل رقم في اليوم
        db.UniqueConstraint('number_id', 'query_date', name='uix_number_date'),
        db.Index('idx_query_date', 'query_date'),
    )
    
    def __repr__(self):
        return f'<DailyQuery {self.number_id} - {self.query_date}>'
    
    def to_dict(self):
        """تحويل بيانات الاستعلام اليومي إلى قاموس"""
        return {
            'id': self.id,
            'number_id': self.number_id,
            'query_date': self.query_date.isoformat() if self.query_date else None,
            'query_time': self.query_time.isoformat() if self.query_time else None,
            'package_value': self.package_value,
            'balance_gb': self.balance_gb,
            'daily_consumption_gb': self.daily_consumption_gb,
            'days_remaining': self.days_remaining,
            'amount_remaining': self.amount_remaining,
            'status': self.status,
            'notes': self.notes
        }


class User(db.Model):
    """جدول المستخدمين - للمصادقة"""
    __tablename__ = 'users'
    
    id = Column(db.Integer, primary_key=True)
    username = Column(db.String(100), nullable=False, unique=True)
    password = Column(db.String(255), nullable=False)  # SHA256 hash
    full_name = Column(db.String(150))
    email = Column(db.String(150))
    is_admin = Column(db.Boolean, default=False)
    created_at = Column(db.DateTime, default=datetime.utcnow)
    last_login = Column(db.DateTime)
    
    def __repr__(self):
        return f"<User {self.username}>"


class Log(db.Model):
    """جدول السجلات - لتتبع الرسائل والعمليات"""
    __tablename__ = 'logs'
    
    id = Column(db.Integer, primary_key=True)
    customer_id = Column(db.Integer, db.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    number = Column(db.String(50), nullable=False)
    type = Column(db.String(20), nullable=False)  # yemenet أو yemen4g
    response = Column(db.Text, nullable=False)  # JSON response
    created_at = Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # العلاقة
    customer = db.relationship("Customer", backref="logs", lazy=True)
    
    def __repr__(self):
        return f"<Log {self.number} - {self.created_at}>"
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
    days_text, days_count, status,expyer_date = calculate_days_remaining(expdate_raw)

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
                expdate = expyer_date
                
    
    
    # بعد تحويل expdate (كما في دالتك الحالية)
    # expdate = None
    # if expdate_raw:
    #     try:
    #         expdate = datetime.strptime(expdate_raw, "%m/%d/%Y %I:%M:%S %p")
    #     except:
    #         try:
    #             expdate = datetime.fromisoformat(expdate_raw)
    #         except:
    #             expdate = None

    # --- هنا نحسب days_remaining (عدد الأيام)
    days_remaining = None
    if expdate:
        # حساب الفرق على مستوى الأيام (يمكن أن يكون سالبًا إذا انتهت الباقة)
        try:
            days_remaining = (expdate.date() - datetime.utcnow().date()).days
        except:
            days_remaining = days_count

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
    
    days_text, days_count, status,expyer_date = calculate_days_remaining(expdate_raw)
    # الملاحظات (مثال بسيط كما طلبت من قبل، يمكنك توسيعه)
    notes = ""
    if last_query and avblnce_value > (last_query.avblnce or 0):
        notes = "تم تسديد النقطة"
    else:
        if expdate:
            try:
                days_remaining = (expdate - datetime.utcnow()).days
            except Exception:
                days_remaining = days_count
            
            if days_remaining < 5:
                notes =f"أوشك على الانتهاء : {days_text}"
            elif days_remaining<=0:
                notes=f"{days_text}"
        if avblnce_value < 5:
            # إذا كانت ملاحظة أخرى تريدها أن تظهر بجانب السابقة، ادمجها
            if notes:
                notes = notes + "؛ الرصيد منخفض جداً"
            else:
                notes = "الرصيد منخفض جداً"
        elif avblnce_value == 0:
            if notes:
                notes = notes + "؛ الرصيد منتهي"
            else:
                notes = "الرصيد منتهي"

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
    # """الحصول على إحصائيات قاعدة البيانات"""
        try:
            stats = {}
            
            # عدد العملاء
            stats['total_clients'] = Customer.query.count()
            
            # عدد الأرقام
            stats['total_numbers'] = Number.query.count()
            
            # عدد السجلات
            stats['total_messages'] = Log.query.count()
            
            # الجلسات النشطة
            session_data = self.get_session_data()
            stats['active_sessions'] = 1 if session_data and session_data.get('status') == 'connected' else 0
            
            return stats
        except Exception as e:
            return {"error": f"خطأ في قراءة قاعدة البيانات: {str(e)}"}
    # def get_database_stats(self):
    #     """الحصول على إحصائيات قاعدة البيانات"""
    #     try:
    #         conn = sqlite3.connect(self.db_path)
    #         cursor = conn.cursor()
            
    #         stats = {}
            
    #         # عدد العملاء
    #         cursor.execute("SELECT COUNT(*) FROM clients")
    #         stats['total_clients'] = cursor.fetchone()[0]
            
    #         # عدد الأرقام
    #         cursor.execute("SELECT COUNT(*) FROM numbers")
    #         stats['total_numbers'] = cursor.fetchone()[0]
            
    #         # عدد السجلات
    #         cursor.execute("SELECT COUNT(*) FROM logs")
    #         stats['total_messages'] = cursor.fetchone()[0]
            
    #         # الجلسات النشطة (من ملف JSON)
    #         session_data = self.get_session_data()
    #         stats['active_sessions'] = 1 if session_data and session_data.get('status') == 'connected' else 0
            
    #         conn.close()
    #         return stats
    #     except Exception as e:
    #         return {"error": f"خطأ في قراءة قاعدة البيانات: {str(e)}"}

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
# def db_conn():
#     """إنشاء اتصال جديد بقاعدة البيانات SQLite"""
#     return sqlite3.connect(DB_PATH)

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


# def init_db():
#     with db_conn() as conn:
#         c = conn.cursor()
        
#         # Create tables if they don't exist
#         c.execute(
#             """
#             CREATE TABLE IF NOT EXISTS users (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 username TEXT NOT NULL UNIQUE,
#                 password TEXT NOT NULL,
#                 full_name TEXT,
#                 email TEXT,
#                 is_admin BOOLEAN DEFAULT 0,
#                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                 last_login TIMESTAMP
#             )
#             """
#         )
        
#         # Create default admin user if not exists
#         c.execute("SELECT COUNT(*) FROM users")
#         if c.fetchone()[0] == 0:
#             hashed_password = hashlib.sha256('admin123'.encode('utf-8')).hexdigest()
#             c.execute(
#                 """
#                 INSERT INTO users (username, password, full_name, email, is_admin)
#                 VALUES (?, ?, ?, ?, ?)
#                 """,
#                 ('admin', hashed_password, 'مدير النظام', 'admin@example.com', 1)
#             )
        
#         c.execute(
#             """
#             CREATE TABLE IF NOT EXISTS clients (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 name TEXT NOT NULL,
#                 whatsapp TEXT NOT NULL UNIQUE
#             )
#             """
#         )
        
#         c.execute(
#             """
#             CREATE TABLE IF NOT EXISTS numbers (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 client_id INTEGER NOT NULL,
#                 number TEXT NOT NULL,
#                 type TEXT NOT NULL,
#                 last_balance TEXT,
#                 last_balance_value REAL,
#                 last_balance_timestamp TEXT,
#                 FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
#                 UNIQUE(client_id, number)
#             )
#             """
#         )
        
#         c.execute(
#             """
#             CREATE TABLE IF NOT EXISTS logs (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 client_id INTEGER NOT NULL,
#                 number TEXT NOT NULL,
#                 type TEXT NOT NULL,
#                 response TEXT NOT NULL,
#                 created_at TEXT NOT NULL,
#                 FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
#             )
#             """
#         )
        
#         # Update database schema if needed
#         update_db_schema(conn)
#         conn.commit()

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

# def calculate_summary_statistics(client_id: int, results: list) -> dict:
#     """حساب الإحصائيات الإجمالية للعميل"""
#     from datetime import datetime, timezone
#     import json
    
#     stats = {
#         'total_lines': len(results),
#         'total_consumption': 0.0,
#         'total_balance': 0.0,
#         'expired_lines': 0,
#         'expiring_soon_lines': 0,
#         'paid_lines': 0,
#         'last_query_time': None,
#         'current_time': datetime.now(timezone.utc)
#     }
    
#     # حساب الإحصائيات من النتائج
#     for result in results:
#         if result.get('data', {}).get('raw'):
#             try:
#                 raw_data = json.loads(result['data']['raw'])
#                 balance_text = raw_data.get('balance', '')
                
#                 # استخراج قيمة الرصيد من البيانات الخام
#                 balance_value = 0.0
                
#                 # محاولة استخراج الرصيد من الحقول المختلفة
#                 import re
                
#                 # أولاً: محاولة استخراج من حقل avblnce
#                 if 'avblnce' in raw_data:
#                     avblnce_text = str(raw_data['avblnce'])
#                     balance_match = re.search(r'(\d+\.?\d*)\s*(GB|Gigabyte\(s\)|Gigabyte)', avblnce_text)
#                     if balance_match:
#                         balance_value = float(balance_match.group(1))
#                         stats['total_balance'] += balance_value
                
#                 # ثانياً: إذا لم نجد في avblnce، نبحث في balance
#                 if balance_value == 0.0 and balance_text:
#                     balance_match = re.search(r'(\d+\.?\d*)\s*(GB|Gigabyte\(s\)|Gigabyte)', balance_text)
#                     if balance_match:
#                         balance_value = float(balance_match.group(1))
#                         stats['total_balance'] += balance_value
                
#                 # حساب الاستهلاك لكل رقم
#                 consumption_data = get_consumption_data(result['number'])
#                 if consumption_data.get('consumption', 0) > 0:
#                     stats['total_consumption'] += consumption_data['consumption']
                
#                 # تحديد حالة الخط
#                 expiry_text = ''
#                 if 'تأريخ الانتهاء:' in balance_text:
#                     expiry_text = balance_text.split('تأريخ الانتهاء:')[1].split('اقل مبلغ سداد:')[0].strip()
#                 elif 'تاريخ الانتهاء:' in balance_text:
#                     expiry_text = balance_text.split('تاريخ الانتهاء:')[1].split('أقل مبلغ سداد:')[0].strip()
                
#                 # تحليل تاريخ الانتهاء
#                 if expiry_text:
#                     try:
#                         from datetime import datetime
#                         expiry_date = datetime.strptime(expiry_text.split()[0], '%m/%d/%Y')
#                         now = datetime.now()
#                         days_diff = (expiry_date - now).days
                        
#                         if days_diff < 0:
#                             stats['expired_lines'] += 1
#                         elif days_diff <= 7:  # ينتهي خلال أسبوع
#                             stats['expiring_soon_lines'] += 1
                        
#                         # تحديد إذا كان الخط مسدد (لديه رصيد)
#                         if balance_value > 0:
#                             stats['paid_lines'] += 1
#                     except:
#                         pass
#             except:
#                 pass
    
#     # البحث عن آخر وقت استعلام لأول رقم فقط
#     with db_conn() as conn:
#         c = conn.cursor()
#         # الحصول على أول رقم للعميل
#         c.execute("""
#             SELECT id FROM numbers 
#             WHERE client_id = ? 
#             ORDER BY id ASC 
#             LIMIT 1
#         """, (client_id,))
#         first_number = c.fetchone()
        
#         if first_number:
#             # البحث عن ثاني أحدث سجل لأول رقم فقط
#             c.execute("""
#                 SELECT created_at 
#                 FROM number_history 
#                 WHERE number_id = ?
#                 ORDER BY created_at DESC 
#                 LIMIT 2
#             """, (first_number[0],))
#             results_time = c.fetchall()
#             if len(results_time) >= 2:
#                 # استخدام ثاني أحدث سجل كآخر استعلام
#                 stats['last_query_time'] = results_time[1][0]
    
#     return stats
def calculate_summary_statistics(client_id: int, results: list) -> dict:
    """حساب الإحصائيات الإجمالية للعميل - باستخدام balance.db"""
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
    
    # البحث عن آخر وقت استعلام لأول رقم باستخدام SQLAlchemy
    # الحصول على أول رقم للعميل
    first_number = Number.query.filter_by(client_id=client_id)\
                               .order_by(Number.id.asc())\
                               .first()
    
    if first_number:
        # البحث عن ثاني أحدث سجل لأول رقم من جدول Query
        queries = Query.query.filter_by(phone_number=first_number.number)\
                            .order_by(Query.query_time.desc())\
                            .limit(2).all()
        
        if len(queries) >= 2:
            # استخدام ثاني أحدث سجل كآخر استعلام
            stats['last_query_time'] = queries[1].query_time.isoformat()
    
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
                
            #if consumption_since_last_gb :
            lines.append(f"📉 *الاستهلاك منذ اخر تقرير*: {consumption_since_last_gb} [جيجا]")
            # else:
            #     lines.append(f"📉 *الاستهلاك*: لا يوجد استهلاك")
                 
            # if daily_consumption_gb :
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

# def format_arabic_report(results: list, client_id: int = None) -> str:
#     """
#     تنسيق تقرير الأرقام باللغة العربية مع المعلومات المحسنة
#     يشمل الأيام المتبقية والاستهلاك من قاعدة البيانات
#     """
#     lines = ["📊 *تقرير الخطوط من نظام العطاب اكسبرس* 📊\n"]
    
#     for i, result in enumerate(results, 1):
#         lines.append(f"🔢 *الرقم {i}*")
        
#         if "error" in result:
#             lines.append(f"📱 *الرقم*: {result['number']}")
#             lines.append(f"❌ *خطأ*: {result['error']}\n")
#             continue
            
#         data = result.get("data", {})
#         raw_data = {}
        
#         # Try to parse the raw data if it's a string
#         if isinstance(data.get("raw"), str):
#             try:
#                 raw_data = json.loads(data["raw"])
#             except (json.JSONDecodeError, TypeError):
#                 raw_data = {"raw": data.get("raw", "")}
#         elif isinstance(data.get("raw"), dict):
#             raw_data = data["raw"]
        
#         # Extract number type for better formatting
#         num_type = ""
#         if "yem4g" in result.get("endpoint", ""):
#             num_type = "يمن فور جي"
#         elif "adsl" in result.get("endpoint", "").lower():
#             num_type = "يمن نت"
        
#         # Format the response based on available data
#         if raw_data and isinstance(raw_data, dict):
#             # Extract values from the raw data
#             balance = raw_data.get("avblnce", "")
#             package = raw_data.get("baga_amount", "")
#             expiry = raw_data.get("expdate", "")
#             min_payment = raw_data.get("minamtobill", "0")
            
#             # Format the response in a clean table-like format
#             lines.append(f"📱 *الرقم*: {result['number']}")
#             if num_type:
#                 lines.append(f"📶 *نوع الخدمة*: {num_type}")
            
#             # Add separator line
#             lines.append("─" * 30)
            
#             # Add balance info in a formatted way
#             if balance:
#                 lines.append(f"💳 *الرصيد*: {balance}")
#             if package:
#                 lines.append(f"📦 *قيمة الباقة*: {package} ريال")
            
#             # استخدام الدالة المحسنة لحساب الأيام المتبقية
#             if expiry:
#                 # تنظيف تنسيق التاريخ
#                 expiry_clean = expiry.replace(" 12:00:00 AM", "").replace(" 12:00:00 ص", "")
#                 days_text, days_count, status = calculate_days_remaining(expiry_clean)
#                 lines.append(f"📅 *تاريخ الانتهاء*: {expiry}")
#                 lines.append(f"⏰ *الأيام المتبقية*: {days_text}")
            
#             # إضافة معلومات الاستهلاك من قاعدة البيانات
#             consumption_data = get_consumption_data(result['number'])
#             if consumption_data.get('has_previous', False):
#                 lines.append(f"🔄 *آخر تحديث*: {consumption_data['time_diff']}")
#                 if consumption_data.get('consumption', 0) > 0:
#                     lines.append(f"📉 *الاستهلاك*: {consumption_data['consumption']:.2f} GB")
#                 else:
#                     lines.append(f"📉 *الاستهلاك*: لا يوجد استهلاك")
#             else:
#                 lines.append(f"🔄 *آخر تحديث*: أول استعلام")
            
#             # إضافة أقل مبلغ سداد فقط إذا كان أكبر من صفر
#             if min_payment and float(min_payment) > 0:
#                 lines.append(f"💰 *أقل مبلغ سداد*: {min_payment} ريال")
            
#             # Add speed if available
#             speed = raw_data.get("speed", "")
#             if speed and speed.strip():
#                 lines.append(f"⚡ *السرعة*: {speed}")
            
#             # Add status if available
#             api_status = raw_data.get("resultDesc", "")
#             if api_status and api_status.lower() != "success":
#                 lines.append(f"ℹ️ *الحالة*: {api_status}")
            
#             # إضافة حالة الباقة من حساب الأيام المتبقية
#             if expiry:
#                 if status == "active":
#                     lines.append(f"✅ *حالة الباقة*: نشطة")
#                 elif status == "warning":
#                     lines.append(f"⚠️ *حالة الباقة*: تحذير - قريبة من الانتهاء")
#                 elif status == "critical":
#                     lines.append(f"🔴 *حالة الباقة*: حرجة - تنتهي قريباً")
#                 elif status == "expires_today":
#                     lines.append(f"🔴 *حالة الباقة*: تنتهي اليوم")
#                 elif status == "expired":
#                     lines.append(f"❌ *حالة الباقة*: منتهية")
                
#         elif "formatted" in data:
#             # Fallback to pre-formatted message
#             lines.append(data["formatted"])
#         else:
#             # Fallback to showing the raw data
#             lines.append("📋 *تفاصيل الباقة*")
#             if "balance" in data:
#                 lines.append(data["balance"])
#             else:
#                 lines.append("⚠️ لا توجد بيانات متاحة")
        
#         lines.append("")  # Add empty line between results
    
#     # Add timestamp and footer
#     from datetime import datetime
#     lines.append("─" * 30)  # Add separator before footer
#     # إضافة الإحصائيات الإجمالية إذا تم تمرير معرف العميل
#     if client_id and len(results) > 1:
#         stats = calculate_summary_statistics(client_id, results)
        
#         lines.append("\n" + "═" * 40)
#         lines.append("📈 *الإحصائيات الإجمالية* 📈")
#         lines.append("═" * 40)
        
#         # إجمالي الخطوط والأرصدة
#         lines.append(f"📊 *إجمالي الخطوط*: {stats['total_lines']}")
#         lines.append(f"💰 *إجمالي الأرصدة*: {stats['total_balance']:.2f} GB")
        
#         # الاستهلاك الإجمالي
#         if stats['total_consumption'] > 0:
#             lines.append(f"📉 *إجمالي الاستهلاك*: {stats['total_consumption']:.2f} GB")
#         else:
#             lines.append(f"📉 *إجمالي الاستهلاك*: لا يوجد استهلاك")
        
#         # حالة الخطوط
#         lines.append(f"✅ *خطوط مسددة*: {stats['paid_lines']}")
#         lines.append(f"⚠️ *خطوط ستنتهي قريباً*: {stats['expiring_soon_lines']}")
#         lines.append(f"❌ *خطوط منتهية*: {stats['expired_lines']}")
        
#         # الفارق الزمني
#         if stats['last_query_time']:
#             time_diff = calculate_time_diff(stats['last_query_time'])
#             lines.append(f"🕐 *آخر استعلام*: {time_diff}")
#         else:
#             lines.append(f"🕐 *آخر استعلام*: هذا هو الاستعلام الأول")
    
#     # التاريخ والوقت الحالي
#     from datetime import datetime
#     import locale
    
#     try:
#         locale.setlocale(locale.LC_TIME, 'ar_SA.UTF-8')
#     except:
#         try:
#             locale.setlocale(locale.LC_TIME, 'Arabic_Saudi Arabia.1256')
#         except:
#             pass  # استخدام الإعداد الافتراضي
    
#     now = datetime.now()
#     current_date = now.strftime('%Y-%m-%d')
#     current_time = now.strftime('%I:%M %p')
#     day_name = now.strftime('%A')
    
#     lines.append("\n" + "─" * 30)
#     lines.append(f"📅 *التاريخ*: {current_date}")
#     lines.append(f"🕐 *الوقت*: {current_time}")
#     lines.append(f"📆 *اليوم*: {day_name}")
    
#     lines.append("\n📞 للاشتراك التواصل على الرقم: *+967779751181*")
    
#     return "\n".join(lines)
def format_arabic_report(results: list, client_id: int = None) -> str:
    print("تم الدخول لدالة format_arabic_report")
    """
    تنسيق تقرير الأرقام باللغة العربية مع المعلومات المحسنة
    يشمل كل البيانات التفصيلية والإحصائيات الإجمالية
    """
    lines = ["📊 *تقرير الخطوط من نظام العطاب اكسبرس* 📊\n"]
    one_d=[]
    tow_d=[]
   
    # متغيرات لحساب الإجماليات
    total_balance_gb = 0.0
    total_consumption_since_last = 0.0
    total_daily_consumption = 0.0
    total_amount_consumed = 0.0
    total_amount_remaining = 0.0
    total_package_value = 0.0
    expired_count = 0
    expiring_soon_count = 0
    active_count = 0
    tow_d.append(['#','الرقم','الرصيد الحالي','قيمة الباقة','تاريخ الانتهاء','الأيام','الاستهلاك','الاستهلاك(ي)',' المستهلك','المتبقي','الحالة','اللون'])    

    for i, result in enumerate(results, 1):
        one_d=[]
        one_d.append(f"{i}")
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
            
        # Format the response based on available data
        # if raw_data and isinstance(raw_data, dict):
        #     # Extract values from the raw data
        #     balance = raw_data.get("avblnce", "")
        #     package = raw_data.get("baga_amount", "")
        #     expiry = raw_data.get("expdate", "")
        #     min_payment = raw_data.get("minamtobill", "0")
            
            # Format the response in a clean table-like format
            lines.append(f"📱 *الرقم*: {result['number']}")
            if num_type:
                lines.append(f"📶 *نوع الخدمة*: {num_type}")
            one_d.append(result['number'])
            
            # Add separator line
            lines.append("─" * 30)
            
            # Add balance info in a formatted way
            if balance:
                lines.append(f"💳 *الرصيد الحالي*: {balance} جيجا")
                one_d.append(balance)
                # استخراج قيمة الرصيد الرقمية للإجماليات
                import re
                balance_match = re.search(r'(\d+\.?\d*)', str(balance))
                if balance_match:
                    total_balance_gb += float(balance_match.group(1))
            else:
                one_d.append("غير معروف")        
            if package:
                lines.append(f"📦 *قيمة الباقة*: {package} ريال")
                one_d.append(package)
                try:
                    total_package_value += float(package)
                except:
                    pass
            else:
                one_d.append("غير معروف")
            
            # استخدام الدالة المحسنة لحساب الأيام المتبقية
            status = None
            if expiry:
                # تنظيف تنسيق التاريخ
                expiry_clean = expiry.replace(" 12:00:00 AM", "").replace(" 12:00:00 ص", "")
                days_text, days_count, status, expiry_date = calculate_days_remaining(expiry_clean)
                lines.append(f"📅 *تاريخ الانتهاء*: {expiry_date}")
                lines.append(f"⏰ *الأيام المتبقية*: {days_text}")
                one_d.append(expiry_date)
                one_d.append(days_count)
                print(one_d)
                
                
                # حساب إحصائيات الحالة
                if status == "expired":
                    expired_count += 1
                elif status in ["warning", "critical", "expires_today"]:
                    expiring_soon_count += 1
                elif status == "active":
                    active_count += 1
            else:
                one_d.append(expiry)
                one_d.append("0")
            # ═══════════════════════════════════════════════════════════
            # إضافة معلومات الاستهلاك التفصيلية من Query model
            # ═══════════════════════════════════════════════════════════
            try:
                # جلب آخر استعلام من Query model
                latest_query = Query.query.filter_by(phone_number=result['number'])\
                                         .order_by(Query.query_time.desc())\
                                         .first()
                
                if latest_query:
                    # عرض الوقت منذ آخر استعلام
                   
                    # lines.append(f"🕐 *آخر تحديث*: {latest_query.time_since_last}")
                    
                    # عرض الاستهلاك منذ آخر تقرير
                    
                    lines.append(f"📊 *الاستهلاك منذ آخر تقرير*: {latest_query.consumption_since_last:.2f} جيجا")
                    total_consumption_since_last += latest_query.consumption_since_last
                    one_d.append(round(latest_query.consumption_since_last,2))
                    # عرض الاستهلاك اليومي
                    
                    lines.append(f"📉 *الاستهلاك اليومي*: {latest_query.daily_consumption:.2f} جيجا")
                    total_daily_consumption += latest_query.daily_consumption
                    one_d.append(round(latest_query.daily_consumption,2))
                    # عرض المبلغ المستهلك
                 
                    lines.append(f"💸 *المبلغ المستهلك*: {latest_query.amount_consumed:.2f} ريال")
                    total_amount_consumed += latest_query.amount_consumed
                    one_d.append(round(latest_query.amount_consumed,2))
                    
                    # عرض المبلغ المتبقي
                    
                    if latest_query.amount_remaining :
                        
                        lines.append(f"💰 *المبلغ المتبقي*: {latest_query.amount_remaining:.2f} ريال")
                        total_amount_remaining += latest_query.amount_remaining
                        one_d.append(round(latest_query.amount_remaining,2))
                    else:
                        lines.append(f"💰 *المبلغ المتبقي*: 0.00 ريال")
                        one_d.append(0)
                    color=''
                    q=''
                    # عرض الملاحظات إذا كانت موجودة
                    if latest_query.notes and latest_query.notes.strip():
                        # إضافة رموز تعبيرية حسب نوع الملاحظة
                        notes_text = latest_query.notes
                        if "انتهت" in notes_text or "منتهية" in notes_text:
                            lines.append(f"⚠️ *ملاحظة*: {notes_text}")
                            q=f"⚠️{notes_text}"
                            color='lightyellow'
                        elif "رصيد منخفض" in notes_text:
                            lines.append(f"🔴 *ملاحظة*: {notes_text}")
                            q=f"🔴{notes_text}"
                            color='red'
                        elif "شحن" in notes_text or "تعبئة" in notes_text:
                            lines.append(f"✅ *ملاحظة*: {notes_text}")
                            q=f"✅{notes_text}"
                            color='lightgreen'
                        else:
                            lines.append(f"📝 *ملاحظة*: {notes_text}")
                            q=f"📝{notes_text}"
                            color='white'
                else:
                    lines.append(f"🔄 *آخر تحديث*: أول استعلام")
                    one_d.append("أول استعلام")
                    one_d.append("أول استعلام")
                    one_d.append("أول استعلام")
                    one_d.append("أول استعلام")
                    q=f"🔄"
                        
            except Exception as e:
                print(f"[خطأ] فشل في جلب بيانات الاستهلاك للرقم {result['number']}: {e}")
                lines.append(f"🔄 *آخر تحديث*: أول استعلام")
                one_d.append("أول استعلام")
                one_d.append("أول استعلام")
                one_d.append("أول استعلام")
                one_d.append("أول استعلام")
                q=f"🔄"
            
            # إضافة أقل مبلغ سداد فقط إذا كان أكبر من صفر
            if min_payment and float(min_payment) > 0:
                lines.append(f"💵 *أقل مبلغ سداد*: {min_payment} ريال")
            
            # Add speed if available
            speed = raw_data.get("speed", "")
            if speed and speed.strip():
                lines.append(f"⚡ *السرعة*: {speed}")
            
            # Add status if available
            api_status = raw_data.get("resultDesc", "")
            if api_status and api_status.lower() != "success":
                lines.append(f"ℹ️ *الحالة*: {api_status}")
            
            # إضافة حالة الباقة من حساب الأيام المتبقية
            if expiry and status:
                if status == "active":
                    lines.append(f"✅ *حالة الباقة*: نشطة")
                    q+='\n'+f"✅ *حالة الباقة*: نشطة"
                elif status == "warning":
                    lines.append(f"⚠️ *حالة الباقة*: تحذير - قريبة من الانتهاء")
                    q+='\n'+f"⚠️ *الباقة*: تحذير - قريبة من الانتهاء"
                    color='yellow'
                elif status == "critical":
                    lines.append(f"🔴 *حالة الباقة*: حرجة - تنتهي قريباً")
                    q+='\n'+f"🔴 *الباقة*: حرجة - تنتهي قريباً"
                    color='orange'
                elif status == "expires_today":
                    lines.append(f"🔴 *حالة الباقة*: تنتهي اليوم")
                    q+='\n'+f"🔴 *الباقة*: تنتهي اليوم"
                    color='orange'
                elif status == "expired":
                    lines.append(f"❌ *حالة الباقة*: منتهية")
                    q+='\n'+f"❌ *الباقة*: منتهية"
                    color='red'
            one_d.append(q)
            one_d.append(color)
            tow_d.append(one_d)  
            print(tow_d)
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
    
    # ═══════════════════════════════════════════════════════════
    # إضافة الإحصائيات الإجمالية الشاملة
    # ═══════════════════════════════════════════════════════════
    if len(results) :
        one_d=[]
        lines.append("\n" + "═" * 40)
        lines.append("📈 *الإحصائيات الإجمالية* 📈")
        lines.append("═" * 40)
        
        # إجمالي الخطوط
        lines.append(f"📊 *إجمالي الخطوط*: {len(results)}")
        one_d.append(len(results))
        one_d.append('الاجماليات')
        # إجمالي الأرصدة
        if total_balance_gb :
            lines.append(f"💳 *إجمالي الأرصدة*: {total_balance_gb:.2f} GB")
            one_d.append(round(total_balance_gb,2))
        
        # إجمالي قيمة الباقات
        if total_package_value :
            lines.append(f"📦 *إجمالي قيمة الباقات*: {total_package_value:.2f} ريال")
            one_d.append(total_package_value)
            one_d.append('--')
            one_d.append('--')
            one_d.append(round(total_consumption_since_last,2))
            one_d.append(round(total_daily_consumption,2))
            one_d.append(round(total_amount_consumed,2))
            one_d.append(round(total_amount_remaining,2))
        # إجمالي الاستهلاك منذ آخر تقرير
        if total_consumption_since_last  :
            lines.append(f"📊 *إجمالي الاستهلاك منذ آخر تقرير*: {total_consumption_since_last:.2f} جيجابايت")
            
            
        
        # إجمالي الاستهلاك اليومي
        if total_daily_consumption :
            lines.append(f"📉 *إجمالي الاستهلاك اليومي*: {total_daily_consumption:.2f} جيجابايت")
            
            
        
        # إجمالي المبلغ المستهلك
            lines.append(f"💸 *إجمالي المبلغ المستهلك*: {total_amount_consumed:.2f} ريال")
            
        
        # إجمالي المبلغ المتبقي
        if total_amount_remaining:
            lines.append(f"💰 *إجمالي المبلغ المتبقي*: {total_amount_remaining:.2f} ريال")
            
           
        one_d.append(f"   ⚠️ خطوط ستنتهي قريباً: {expiring_soon_count}")
        one_d.append('cyan')
        tow_d.append(one_d)
        one_d=[]
        lines.append("")  # سطر فارغ
        print(f"الثاني عند سطر فارغ{tow_d}")
        # حالة الخطوط
        lines.append("📍 *تفاصيل حالة الخطوط*:")
        lines.append(f"   ✅ خطوط نشطة: {active_count}")
        lines.append(f"   ⚠️ خطوط ستنتهي قريباً: {expiring_soon_count}")
        lines.append(f"   ❌ خطوط منتهية: {expired_count}")
        clientname=Customer.query.filter_by(id=client_id).first().name
        whatsapp=Customer.query.filter_by(id=client_id).first().whatsapp
        one_d.append(f"العميل:{clientname}")
        one_d.append(f"الواتساب:{whatsapp}")
        
        # آخر وقت استعلام إذا كان متوفراً
        if client_id:
            try:
                # البحث عن أول رقم للعميل
                first_number = Number.query.filter_by(client_id=client_id)\
                                           .order_by(Number.id.asc())\
                                           .first()
                
                if first_number:
                    # البحث عن ثاني أحدث سجل
                    queries = Query.query.filter_by(phone_number=first_number.number)\
                                        .order_by(Query.query_time.desc())\
                                        .limit(2).all()
                    
                    if len(queries) >= 2:
                        time_diff = calculate_time_diff(queries[1].query_time.isoformat())
                        lines.append(f"\n🕐 *آخر استعلام كان*: {time_diff}")
                        one_d.append(f"\n🕐 *آخر استعلام كان*: {time_diff}")
            except Exception as e:
                print(f"[خطأ] فشل في جلب وقت آخر استعلام: {e}")
    
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
    
    lines.append("\n" + "─" * 40)
    lines.append(f"📅 *التاريخ*: {current_date}")
    lines.append(f"🕐 *الوقت*: {current_time}")
    lines.append(f"📆 *اليوم*: {day_name}")
    one_d.append(f"📅 *التاريخ*: {current_date}")
    one_d.append(f"🕐 *الوقت*: {current_time}")
    one_d.append(f"📆 *اليوم*: {day_name}")
    
    
    lines.append("\n📞 للاشتراك التواصل على الرقم: *+967779751181*")
    lines.append("─" * 40)
    print("تم إنشاء التقرير بنجاح")
    pdf=create_pdf(one_d,tow_d,clientname,whatsapp,'static/image/pdf.png')
    print("وصلنا هنا")
    print(pdf)
    one_d=[]
    tow_d=[]
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
        days_diff-=1
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
            
        return days_text, days_diff, status,expiry_date.date()
        
    except Exception as e:
        print(f"[ERROR] خطأ في حساب الأيام المتبقية: {e}")
        return "خطأ في التاريخ", 0, "error"



from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Spacer
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from datetime import datetime
import arabic_reshaper
from bidi.algorithm import get_display
import os
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Spacer, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display

# تسجيل خط يدعم العربية
#pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
# تسجيل الخط العربي
pdfmetrics.registerFont(TTFont('Arial', 'static/fonts/Arial.ttf'))

def process_arabic(text):
    reshaped_text = arabic_reshaper.reshape(str(text))
    bidi_text = get_display(reshaped_text)
    return bidi_text
# دالة لمعالجة النصوص العربية

def get_report_path(client_name):
    # إنشاء مجلد التقارير لو مش موجود
    reports_dir = "reports"
    os.makedirs(reports_dir, exist_ok=True)

    # اسم الملف: العميل + التاريخ + الوقت
    filename = f"{client_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"

    # المسار النهائي
    return os.path.join(reports_dir, filename)

import os
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Spacer, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.enums import TA_RIGHT,TA_CENTER
import arabic_reshaper
from bidi.algorithm import get_display

# تسجيل خط عربي
# pdfmetrics.registerFont(TTFont('Arial', 'Arial.ttf'))
# مسار الخط داخل المشروع
# font_path = os.path.join(os.getcwd(), "static/fonts", "dejavu-sans.condensed.ttf")

# # تسجيل الخط
# pdfmetrics.registerFont(TTFont('noto-sans', font_path))
# دالة لمعالجة النصوص العربية

def create_pdf(one_d_array, two_d_array, client_name,whatsapp, image_path):
    """
    إنشاء ملف PDF:
    - دعم العربية RTL
    - صورة في الأعلى
    - جدول المصفوفة الأحادية (صفوف من عمودين)
    - جدول المصفوفة الثنائية (بدون عمود اللون)
    - تلوين الصفوف حسب آخر عمود
    - جدول الأسطورة للألوان
    - أعمدة مرنة، نصوص طويلة تتفاف
    """

    # إنشاء مجلد reports
    reports_dir = os.path.join(os.getcwd(), "reports")
    os.makedirs(reports_dir, exist_ok=True)

    # اسم الملف
    file_name = f"{client_name}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf"
    file_path = os.path.join(reports_dir, file_name)

    # إعداد PDF أفقي
    doc = SimpleDocTemplate(file_path, pagesize=landscape(A4),
                            rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)

    story = []

    # ستايل للنصوص العربية
    arabic_style = ParagraphStyle(
        name='Arabic',
        fontName='Arial',
        fontSize=11,
        color=colors.white,
        alignment=TA_CENTER,
        leading=14
    )

    # إضافة الصورة
    if os.path.exists(image_path):
        img = Image(image_path, width=200, height=100)
        story.append(img)
        story.append(Spacer(1, 20))

    # جدول المصفوفة الأحادية (صفوف من عمودين)
    if one_d_array:
        one_d_table_data = []
        for i in range(0, len(one_d_array), 2):
            row = [Paragraph(process_arabic(one_d_array[i]), arabic_style)]
            if i + 1 < len(one_d_array):
                row.append(Paragraph(process_arabic(one_d_array[i+1]), arabic_style))
            else:
                row.append(Paragraph("", arabic_style))
            # قلب الأعمدة للـ RTL
            one_d_table_data.append(list(reversed(row)))

        # أعمدة مرنة
        page_width, _ = landscape(A4)
        col_width = (page_width - 40) / 2
        one_d_table = Table(one_d_table_data, colWidths=[col_width]*2)
        one_d_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ]))
        story.append(one_d_table)
        story.append(Spacer(1, 40))
        
    # جدول المصفوفة الثنائية
    if two_d_array and isinstance(two_d_array, list) and len(two_d_array) > 0:
    # إعداد تنسيق الهيدر
        header_style = ParagraphStyle(
            name='HeaderArabic',
            fontName='Arial',
            fontSize=12,
            textColor=colors.white,
            alignment=TA_CENTER
        )

        headers = [Paragraph(process_arabic(str(h)), header_style) for h in two_d_array[0]]
        data_rows = two_d_array[1:]

        clean_rows = []
        row_colors = []
        for row in data_rows:
            if isinstance(row, list) and len(row) >= 1:
                clean_rows.append([process_arabic(str(cell)) for cell in row[:-1]])
                row_colors.append(row[-1])
            else:
                continue

        if clean_rows:
            num_cols = len(clean_rows[0])
            page_width, _ = landscape(A4)
            usable_width = page_width - 40  # هوامش جانبية

            # تجهيز البيانات
            raw_data = [two_d_array[0][:-1]] + [r[:-1] for r in data_rows]

            # --------- 🔹 حساب عرض الأعمدة بناءً على النصوص 🔹 ---------
            from reportlab.pdfbase.pdfmetrics import stringWidth

            col_widths = []
            for col_idx in range(num_cols):
                max_len = 0
                for row in raw_data:
                    if col_idx < len(row):
                        txt = str(row[col_idx])
                        w = stringWidth(txt, 'Arial', 11)
                        if w > max_len:
                            max_len = w
                col_widths.append(max_len + 20)  # +20 هو هامش بسيط داخل الخلية

            # توزيع الأعمدة بحيث تملأ عرض الصفحة تمامًا
            total_width = sum(col_widths)
            if total_width > 0:
                scale_factor = usable_width / total_width
                col_widths = [w * scale_factor for w in col_widths]
            else:
                col_widths = [usable_width / num_cols] * num_cols

            # إنشاء البيانات النهائية مع فقرات وتنسيق RTL
            table_data = [headers[:-1]] + [
                [Paragraph(process_arabic(str(cell)), arabic_style) for cell in row[:-1]]
                for row in data_rows
            ]
            table_data_rtl = [list(reversed(row)) for row in table_data]

            # إنشاء الجدول
            table = Table(table_data_rtl, colWidths=col_widths[::-1], repeatRows=0)  # لاحظ العكس هنا

            style = TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('BACKGROUND', (0, 0), (-1, 0), colors.black),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.white),
            ])

            # تلوين الصفوف
            for i, color_name in enumerate(row_colors, start=1):
                row_color = getattr(colors, str(color_name), None)
                if isinstance(row_color, colors.Color):
                    style.add('BACKGROUND', (0, i), (-1, i), row_color)

            table.setStyle(style)
            story.append(table)
            story.append(Spacer(1, 30))

    # if two_d_array and isinstance(two_d_array, list) and len(two_d_array) > 0:
        
    #     header_style = ParagraphStyle(
    #         name='HeaderArabic',
    #         fontName='Arial',
    #         fontSize=12,
    #         textColor=colors.white, 
    #         alignment=TA_CENTER
    #     )
    #     headers = [Paragraph(process_arabic(str(h)), header_style) for h in two_d_array[0]]

    #     data_rows = two_d_array[1:]

    #     clean_rows = []
    #     row_colors = []
    #     for row in data_rows:
    #         if isinstance(row, list) and len(row) >= 1:
    #             clean_rows.append([Paragraph(process_arabic(str(cell)), arabic_style) for cell in row[:-1]])
    #             row_colors.append(row[-1])
    #         else:
    #             continue

    #     if clean_rows:
    #         num_cols = len(clean_rows[0])
    #         page_width, _ = landscape(A4)
    #         col_width = (page_width - 40) / num_cols

    #         table_data = [headers[:-1]] + clean_rows
    #         # قلب الأعمدة للـ RTL
    #         table_data_rtl = [list(reversed(row)) for row in table_data]

    #         table = Table(table_data_rtl, colWidths=[col_width]*num_cols, repeatRows=1)

    #         style = TableStyle([
    #             ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
    #             ('FONTSIZE', (0, 0), (-1, -1), 11),
    #             ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    #             ('BACKGROUND', (0, 0), (-1, 0), colors.black),
    #             ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    #             ('GRID', (0,0), (-1,-1), 0.5, colors.white),
    #         ])

    #         used_colors = {}
    #         for i, color_name in enumerate(row_colors, start=1):
    #             row_color = getattr(colors, str(color_name), None)
    #             if isinstance(row_color, colors.Color):
    #                 style.add('BACKGROUND', (0, i), (-1, i), row_color)
    #                 used_colors[str(color_name)] = row_color

    #         table.setStyle(style)
    #         story.append(table)
    #         story.append(Spacer(1, 30))

    #         # جدول الأسطورة للألوان
            # if used_colors:
            #     legend_data = []
            #     for name, color in used_colors.items():
            #         legend_data.append([Paragraph(process_arabic(f"لون: {name}"), arabic_style), ""])

            #     legend_table = Table(legend_data, colWidths=[200, 50])
            #     legend_style = TableStyle([
            #         ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
            #         ('FONTSIZE', (0, 0), (-1, -1), 11),
            #         ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            #     ])

            #     for i, (name, color) in enumerate(used_colors.items()):
            #         if isinstance(color, colors.Color):
            #             legend_style.add('BACKGROUND', (1, i), (1, i), color)

            #     legend_table.setStyle(legend_style)
            #     story.append(legend_table)

   
    print("lllllllllllllllllllllllll")
    doc.build(story)
    print("]]]]]]]]]]]]]]]]]]]]]]]]]]]")
    nowd=datetime.now().date()
    nowt=datetime.now().time().strftime("%H:%M:%S")
    t=f"تقرير العميل: {client_name} \n التاريخ:{nowd} \n الوقت:{nowt}"
    print("fffffffffffffffffffffffffffffffffff")
    send_message_flask(whatsapp, t, file_path)

    return file_path

# def create_pdf(one_d_array, two_d_array, client_name, image_path):
#     """
#     إنشاء ملف PDF يحتوي على:
#     - صورة في الأعلى
#     - جدول من المصفوفة الأحادية (عمودين)
#     - جدول من المصفوفة الثنائية (بدون عمود اللون)
#     - جدول يوضح الألوان المستخدمة
#     يدعم العربية، التفاف النصوص، والأعمدة المرنة.
#     """

#     # إنشاء مجلد reports إذا لم يكن موجودًا
#     reports_dir = os.path.join(os.getcwd(), "reports")
#     os.makedirs(reports_dir, exist_ok=True)

#     # اسم الملف ومساره
#     file_name = f"{client_name}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf"
#     file_path = os.path.join(reports_dir, file_name)

#     # إعداد ملف PDF أفقي
#     doc = SimpleDocTemplate(file_path, pagesize=landscape(A4),
#                             rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)

#     story = []

#     # إعداد ستايل للـ Paragraph العربي
#     arabic_style = ParagraphStyle(name='Arabic', fontName='Arial', fontSize=11, alignment=2, leading=14)  # alignment=2: center

#     # إضافة الصورة
#     if os.path.exists(image_path):
#         img = Image(image_path, width=200, height=100)
#         story.append(img)
#         story.append(Spacer(1, 20))

#     # جدول المصفوفة الأحادية (صفوف من عمودين)
#     if one_d_array:
#         one_d_table_data = []
#         for i in range(0, len(one_d_array), 2):
#             row = [Paragraph(process_arabic(one_d_array[i]), arabic_style)]
#             if i + 1 < len(one_d_array):
#                 row.append(Paragraph(process_arabic(one_d_array[i+1]), arabic_style))
#             else:
#                 row.append(Paragraph("", arabic_style))
#             one_d_table_data.append(row)

#         # أعمدة مرنة
#         page_width, _ = landscape(A4)
#         col_width = (page_width - 40) / 2  # 40 هو مجموع الهوامش
#         one_d_table = Table(one_d_table_data, colWidths=[col_width]*2)
#         one_d_table.setStyle(TableStyle([
#             ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
#             ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
#             ('FONTSIZE', (0, 0), (-1, -1), 12),
#             ('GRID', (0,0), (-1,-1), 0.5, colors.black),
#         ]))
#         story.append(one_d_table)
#         story.append(Spacer(1, 40))

#     # جدول المصفوفة الثنائية
#     if two_d_array and isinstance(two_d_array, list) and len(two_d_array) > 0:
#         headers = [Paragraph(process_arabic(str(h)), arabic_style) for h in two_d_array[0]]
#         data_rows = two_d_array[1:]

#         clean_rows = []
#         row_colors = []
#         for row in data_rows:
#             if isinstance(row, list) and len(row) >= 1:
#                 # بدون عمود اللون
#                 clean_rows.append([Paragraph(process_arabic(str(cell)), arabic_style) for cell in row[:-1]])
#                 row_colors.append(row[-1])
#             else:
#                 continue

#         if clean_rows:
#             num_cols = len(clean_rows[0])
#             page_width, _ = landscape(A4)
#             col_width = (page_width - 40) / num_cols
#             table_data = [headers[:-1]] + clean_rows

#             table = Table(table_data, colWidths=[col_width]*num_cols, repeatRows=1)

#             style = TableStyle([
#                 ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
#                 ('FONTSIZE', (0, 0), (-1, -1), 11),
#                 ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
#                 ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
#                 ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
#                 ('GRID', (0,0), (-1,-1), 0.5, colors.black),
#             ])

#             used_colors = {}
#             for i, color_name in enumerate(row_colors, start=1):
#                 row_color = getattr(colors, str(color_name), None)
#                 if isinstance(row_color, colors.Color):
#                     style.add('BACKGROUND', (0, i), (-1, i), row_color)
#                     used_colors[str(color_name)] = row_color

#             table.setStyle(style)
#             story.append(table)
#             story.append(Spacer(1, 30))

#             # جدول الأسطورة للألوان
#             if used_colors:
#                 legend_data = []
#                 for name, color in used_colors.items():
#                     legend_data.append([Paragraph(process_arabic(f"لون: {name}"), arabic_style), ""])

#                 legend_table = Table(legend_data, colWidths=[200, 50])
#                 legend_style = TableStyle([
#                     ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
#                     ('FONTSIZE', (0, 0), (-1, -1), 11),
#                     ('GRID', (0,0), (-1,-1), 0.5, colors.black),
#                 ])

#                 for i, (name, color) in enumerate(used_colors.items()):
#                     if isinstance(color, colors.Color):
#                         legend_style.add('BACKGROUND', (1, i), (1, i), color)

#                 legend_table.setStyle(legend_style)
#                 story.append(legend_table)

#     # بناء PDF
#     doc.build(story)

#     return file_path

def generate_pdf_report(results: list, client_id: int, output_path: str = None) -> str:
    """إنشاء تقرير PDF احترافي باللغة العربية مع كل البيانات المحسنة"""
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import arabic_reshaper
        from bidi.algorithm import get_display
    except ImportError:
        print("[ERROR] قم بتشغيل: pip install reportlab arabic-reshaper python-bidi")
        return None
    
    try:
        pdfmetrics.registerFont(TTFont('Arabic', 'C:\\Windows\\Fonts\\arial.ttf'))
    except:
        print("[WARNING] فشل تحميل الخط العربي")
    
    customer = Customer.query.get(client_id)
    if not customer:
        return None
    
    if not output_path:
        os.makedirs('reports', exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f'reports/report_{customer.name}_{timestamp}.pdf'
    
    def arabic_text(text):
        if not text:
            return ""
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    
    # استخدام landscape للعرض الأفقي لاستيعاب الأعمدة الإضافية
    doc = SimpleDocTemplate(output_path, pagesize=landscape(A4), 
                           rightMargin=1*cm, leftMargin=1*cm,
                           topMargin=1.5*cm, bottomMargin=1.5*cm)
    elements = []
    
    # الترويسة
    header_data = [
        [arabic_text('تقرير استعلام الباقات - كامل البيانات')],
        [arabic_text(f'العميل: {customer.name}')],
        [arabic_text(f'رقم الهاتف: {customer.whatsapp}')],
        [arabic_text(f'وقت الاستعلام: {customer.auto_query_time.strftime("%H:%M") if customer.auto_query_time else "غير محدد"}')],
        [arabic_text(f'التاريخ: {datetime.now().strftime("%Y-%m-%d %H:%M")}')]
    ]
    
    header_table = Table(header_data, colWidths=[27*cm])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Arabic'),
        ('FONTSIZE', (0, 0), (0, 0), 14),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3*cm))
    
    # الجدول المحسن مع كل البيانات - RTL من اليمين لليسار
    table_data = [[
        arabic_text('الحالة'),
        arabic_text('المبلغ المتبقي'),
        arabic_text('المبلغ المستهلك'),
        arabic_text('الاستهلاك اليومي'),
        arabic_text('الاستهلاك منذ آخر تقرير'),
        arabic_text('الأيام المتبقية'),
        arabic_text('تاريخ الانتهاء'),
        arabic_text('قيمة الباقة'),
        arabic_text('الرصيد الحالي'),
        arabic_text('النوع'),
        arabic_text('الرقم'),
        arabic_text('#')
    ]]
    
    total_balance = 0
    total_package = 0
    total_consumption_last = 0
    total_daily_consumption = 0
    total_amount_consumed = 0
    total_amount_remaining = 0
    row_colors = []
    
    for idx, result in enumerate(results, 1):
        # البيانات موجودة في result['query'] الذي هو dict يحتوي على كل البيانات المحسنة
        data = result.get('query', {})
        
        # استخراج البيانات من المستوى الأول مباشرة
        number = result.get('number', '')
        num_type = 'يمن 4G' if 'yemen4g' in result.get('endpoint', '').lower() else 'يمن نت'
        
        print(f"[DEBUG PDF] معالجة الرقم {number}")
        print(f"[DEBUG PDF] محتوى data: {data}")
        
        # البيانات الأساسية - data هو dict مباشرة يحتوي على المفاتيح
        balance = data.get('avblnce_gb', 0)
        package = data.get('baga_amount', 0)
        expiry = data.get('expdate', '')
        
        # البيانات المحسنة
        consumption_since_last = data.get('consumption_since_last_gb', 0)
        daily_consumption = data.get('daily_consumption_gb', 0)
        amount_consumed = data.get('amount_consumed', 0)
        amount_remaining = data.get('amount_remaining', 0)
        days_remaining_num = data.get('days_remaining', 0)
        
        print(f"[DEBUG PDF] {number}: balance={balance}, package={package}, expiry={expiry}")
        print(f"[DEBUG PDF] استهلاك: consumption_last={consumption_since_last}, daily={daily_consumption}")
        
        # حساب الأيام المتبقية والحالة
        days_text = f'{days_remaining_num} يوم'
        status_text = '✓'
        status_color = colors.HexColor('#ccffcc')
        
        if expiry and isinstance(expiry, str):
            try:
                expiry_clean = expiry.replace(" 12:00:00 AM", "").replace(" 12:00:00 ص", "")
                days_text, days_count, status = calculate_days_remaining(expiry_clean)
                
                if status == "expired":
                    status_color = colors.HexColor('#ffcccc')
                    status_text = '❌'
                elif status in ["critical", "expires_today"]:
                    status_color = colors.HexColor('#ffe6cc')
                    status_text = '🔴'
                elif status == "warning":
                    status_color = colors.HexColor('#fff9cc')
                    status_text = '🟡'
                else:
                    status_color = colors.HexColor('#ccffcc')
                    status_text = '🟢'
            except Exception as e:
                print(f"[DEBUG] خطأ في حساب الأيام: {e}")
                days_text = f'{days_remaining_num} يوم' if days_remaining_num else '-'
        
        row_colors.append(status_color)
        
        # حساب الإجماليات
        try:
            total_balance += float(balance) if balance else 0
            total_package += float(package) if package else 0
            total_consumption_last += float(consumption_since_last) if consumption_since_last else 0
            total_daily_consumption += float(daily_consumption) if daily_consumption else 0
            total_amount_consumed += float(amount_consumed) if amount_consumed else 0
            total_amount_remaining += float(amount_remaining) if amount_remaining else 0
        except Exception as e:
            print(f"[DEBUG] خطأ في حساب الإجماليات: {e}")
        
        # إضافة الصف - RTL من اليمين
        table_data.append([
            arabic_text(status_text),
            arabic_text(f'{amount_remaining:.2f}' if amount_remaining else '-'),
            arabic_text(f'{amount_consumed:.2f}' if amount_consumed else '-'),
            arabic_text(f'{daily_consumption:.2f}' if daily_consumption else '-'),
            arabic_text(f'{consumption_since_last:.2f}' if consumption_since_last else '-'),
            arabic_text(days_text),
            arabic_text(expiry[:10] if expiry else '-'),
            arabic_text(f'{package:.0f}' if package else '-'),
            arabic_text(f'{balance:.2f}' if balance else '-'),
            arabic_text(num_type),
            arabic_text(number),
            arabic_text(str(idx))
        ])
    
    # صف الإجماليات - RTL
    table_data.append([
        '',
        arabic_text(f'{total_amount_remaining:.2f}'),
        arabic_text(f'{total_amount_consumed:.2f}'),
        arabic_text(f'{total_daily_consumption:.2f}'),
        arabic_text(f'{total_consumption_last:.2f}'),
        '',
        '',
        arabic_text(f'{total_package:.0f}'),
        arabic_text(f'{total_balance:.2f}'),
        '',
        arabic_text('المجموع'),
        ''
    ])
    
    # عرض الأعمدة - RTL من اليمين لليسار
    col_widths = [1.5*cm, 2*cm, 2*cm, 2*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2*cm, 2.5*cm, 2*cm, 3*cm, 1*cm]
    data_table = Table(table_data, colWidths=col_widths)
    
    table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Arabic'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e2e8f0')),
        ('FONTSIZE', (0, -1), (-1, -1), 8),
    ]
    
    # تلوين الصفوف
    for idx, color in enumerate(row_colors, 1):
        table_style.append(('BACKGROUND', (0, idx), (-1, idx), color))
    
    data_table.setStyle(TableStyle(table_style))
    elements.append(data_table)
    
    # مفتاح الألوان
    elements.append(Spacer(1, 0.3*cm))
    legend_data = [[
        arabic_text('🟢 جيد (>7 أيام) | 🟡 تحذير (3-7 أيام) | 🔴 حرج (<3 أيام) | ❌ منتهي')
    ]]
    legend_table = Table(legend_data, colWidths=[27*cm])
    legend_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Arabic'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    elements.append(legend_table)
    
    doc.build(elements)
    print(f"[INFO] ✅ تم إنشاء PDF محسن: {output_path}")
    return output_path

# def get_consumption_data(number: str) -> dict:
#     """حساب بيانات الاستهلاك من آخر تقرير في قاعدة البيانات
    
#     Args:
#         number: رقم الهاتف المراد حساب استهلاكه
        
#     Returns:
#         dict: بيانات الاستهلاك والتقرير السابق
#     """
#     with db_conn() as conn:
#         c = conn.cursor()
        
#         # الحصول على بيانات الرقم الحالية
#         c.execute("""
#             SELECT id, last_balance, last_balance_value, last_balance_timestamp 
#             FROM numbers 
#             WHERE number = ?
#         """, (number,))
#         current_data = c.fetchone()
        
#         if not current_data:
#             print(f"[DEBUG] لم يتم العثور على الرقم {number} في جدول numbers")
#             return {
#                 'has_previous': False,
#                 'consumption': 0,
#                 'time_diff': 'أول استعلام',
#                 'previous_balance': None,
#                 'current_data': None
#             }
        
#         number_id = current_data[0]
#         print(f"[DEBUG] تم العثور على الرقم {number} بمعرف {number_id}")
        
#         # الحصول على آخر تقريرين من التاريخ (لحساب الاستهلاك)
#         c.execute("""
#             SELECT balance, balance_value, created_at
#             FROM number_history 
#             WHERE number_id = ?
#             ORDER BY created_at DESC 
#             LIMIT 2
#         """, (number_id,))
#         history_records = c.fetchall()
        
#         print(f"[DEBUG] تم العثور على {len(history_records)} سجل في التاريخ للرقم {number}")
        
#         if len(history_records) < 2:
#             # لا يوجد تقرير سابق للمقارنة
#             if len(history_records) == 0:
#                 time_msg = 'أول استعلام'
#                 print(f"[DEBUG] {time_msg} - لا توجد سجلات في التاريخ")
#             else:
#                 # يوجد سجل واحد فقط، نحسب الوقت منذ إنشائه
#                 record_time = history_records[0][2]
#                 time_msg = calculate_time_diff(record_time)
#                 print(f"[DEBUG] سجل واحد فقط - آخر تحديث: {time_msg}")
            
#             return {
#                 'has_previous': len(history_records) > 0,  # True إذا كان يوجد سجل واحد على الأقل
#                 'consumption': 0,
#                 'time_diff': time_msg,
#                 'previous_balance': history_records[0][0] if history_records else None,
#                 'current_data': current_data
#             }
        
#         # حساب الاستهلاك بين آخر تقريرين
#         latest_balance = history_records[0][1] or 0  # أحدث تقرير
#         previous_balance = history_records[1][1] or 0  # التقرير السابق
#         consumption = max(0, previous_balance - latest_balance)  # تجنب القيم السالبة
        
#         # حساب الفترة الزمنية
#         time_diff = calculate_time_diff(history_records[1][2])  # وقت التقرير السابق
        
#         return {
#             'has_previous': True,
#             'consumption': consumption,
#             'time_diff': time_diff,
#             'previous_balance': history_records[1][0],
#             'previous_balance_value': previous_balance,
#             'latest_balance_value': latest_balance,
#             'current_data': current_data
#         }
def get_consumption_data(number: str) -> dict:
    """حساب بيانات الاستهلاك من Query model"""
    
    # جلب آخر استعلامين للرقم
    queries = Query.query.filter_by(phone_number=number)\
                         .order_by(Query.query_time.desc())\
                         .limit(2).all()
    
    if len(queries) < 2:
        if len(queries) == 1:
            return {
                'has_previous': True,
                'consumption': 0,
                'time_diff': calculate_time_diff(queries[0].query_time.isoformat()),
                'previous_balance': None,
                'current_data': queries[0]
            }
        return {
            'has_previous': False,
            'consumption': 0,
            'time_diff': 'أول استعلام',
            'previous_balance': None,
            'current_data': None
        }
    
    latest = queries[0]
    previous = queries[1]
    
    consumption = max(0, previous.avblnce - latest.avblnce)
    time_diff = calculate_time_diff(previous.query_time.isoformat())
    
    return {
        'has_previous': True,
        'consumption': consumption,
        'time_diff': time_diff,
        'previous_balance': f"{previous.avblnce} {previous.balance_unit}",
        'previous_balance_value': previous.avblnce,
        'latest_balance_value': latest.avblnce,
        'current_data': latest
    }
one_d=[]

two_d=[]
    
def query_number(number: str,is_daily: bool = False):
    print("تم الدخول لدالة query")
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
        data = {"raw": r.text}
        query,result = add_query(number, r.text, is_daily=False)
        result={"raw": result}
        return {"number": number, "type": ntype, "data": result,"query":result}
    
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
                # with db_conn() as conn:
                #     c = conn.cursor()
                #     now = datetime.utcnow().isoformat()  # الوقت الحالي بتنسيق ISO
                    
                #     # الحصول على بيانات الرقم الحالية من قاعدة البيانات
                #     c.execute("SELECT id FROM numbers WHERE number = ?", (number,))
                #     current_data = c.fetchone()
                    
                #     if current_data:
                #         # تحديث الرقم الموجود
                #         c.execute(
                #             """
                #             UPDATE numbers 
                #             SET last_balance = ?, 
                #                 last_balance_value = ?, 
                #                 last_balance_timestamp = ?,
                #                 type = ?
                #             WHERE id = ?
                #             """,
                #             (current_balance, current_balance_value, now, ntype, current_data[0])
                #         )
                #         number_id = current_data[0]
                #     else:
                #         # إدراج رقم جديد (افتراضياً للعميل رقم 1)
                #         c.execute(
                #             """
                #             INSERT INTO numbers (client_id, number, type, last_balance, 
                #                              last_balance_value, last_balance_timestamp)
                #             VALUES (1, ?, ?, ?, ?, ?)
                #             """,
                #             (number, ntype, current_balance, current_balance_value, now)
                #         )
                #         number_id = c.lastrowid
                    
                #     # إضافة السجل الجديد لتاريخ الاستعلامات
                #     print(f"[DEBUG] حفظ سجل جديد في number_history للرقم {number} (ID: {number_id})")
                #     print(f"[DEBUG] البيانات: balance={current_balance}, balance_value={current_balance_value}")
                #     c.execute(
                #         """
                #         INSERT INTO number_history 
                #         (number_id, balance, balance_value, package_value, expiry_date, 
                #          min_payment, speed, created_at)
                #         VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                #         """,
                #         (number_id, current_balance, current_balance_value, package_value,
                #          expiry_date, min_payment, speed, now)
                #     )
                #     print(f"[DEBUG] تم حفظ السجل بنجاح في number_history")
                    
                #     conn.commit()  # حفظ التغييرات
                # تحديث أو إدراج الرقم في قاعدة بيانات balance.db باستخدام SQLAlchemy
                try:
                    now = datetime.utcnow()
                    
                    # البحث عن الرقم في جدول Number
                    existing_number = Number.query.filter_by(number=number).first()

                    if existing_number:
                        # تحديث الرقم الموجود
                        print(f"[DEBUG] تحديث الرقم الموجود: {number}")
                        existing_number.last_balance = current_balance
                        existing_number.last_balance_value = current_balance_value
                        existing_number.last_balance_timestamp = now
                        existing_number.type = ntype
                        db.session.commit()
                        number_id = existing_number.id
                        print(f"[DEBUG] تم تحديث الرقم {number} (ID: {number_id})")
                    else:
                        # إدراج رقم جديد (افتراضياً للعميل رقم 1)
                        print(f"[DEBUG] إدراج رقم جديد: {number}")
                        
                        # محاولة العثور على عميل افتراضي أو إنشاء واحد
                        default_customer = Customer.query.first()
                        if not default_customer:
                            # إنشاء عميل افتراضي إذا لم يكن موجوداً
                            default_customer = Customer(
                                name="عميل افتراضي",
                                whatsapp="000000000"
                            )
                            db.session.add(default_customer)
                            db.session.commit()
                        
                        new_number = Number(
                            client_id=default_customer.id,
                            number=number,
                            type=ntype,
                            last_balance=current_balance,
                            last_balance_value=current_balance_value,
                            last_balance_timestamp=now
                        )
                        db.session.add(new_number)
                        db.session.commit()
                        number_id = new_number.id
                        print(f"[DEBUG] تم إدراج الرقم الجديد {number} (ID: {number_id})")
                    
                    print(f"[INFO] ✅ تم حفظ بيانات الرقم {number} بنجاح")
                    
                except Exception as e:
                    print(f"[ERROR] ❌ فشل في حفظ بيانات الرقم: {str(e)}")
                    db.session.rollback()

                # ملاحظة: لا حاجة للحفظ في number_history
                # لأن دالة add_query() تحفظ البيانات التفصيلية في Query model
                # والتي تحتوي على معلومات أكثر شمولاً
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
        import traceback
        traceback.print_exc()
        print("-----------------hhhhhhhhhhh---------------")
        return {"number": number, "type": ntype, "endpoint": 'adsl', "error": str(e), "query": {}}
    

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


# @app.post("/admin/client")
# def add_client():
#     payload = request.get_json(force=True)
#     name = payload.get("name")
#     whatsapp = payload.get("whatsapp")
#     if not (name and whatsapp):
#         return jsonify({"ok": False, "error": "name & whatsapp مطلوبة"}), 400
#     with db_conn() as conn:
#         c = conn.cursor()
#         c.execute("INSERT INTO clients (name, whatsapp) VALUES (?,?)", (name, whatsapp))
#         conn.commit()
#         return jsonify({"ok": True, "id": c.lastrowid})
@app.post("/admin/client")
def add_client():
    payload = request.get_json(force=True)
    name = payload.get("name")
    whatsapp = payload.get("whatsapp")
    
    if not (name and whatsapp):
        return jsonify({"ok": False, "error": "name & whatsapp مطلوبة"}), 400
    
    try:
        # إنشاء عميل جديد باستخدام SQLAlchemy
        new_customer = Customer(name=name, whatsapp=whatsapp)
        db.session.add(new_customer)
        db.session.commit()
        
        return jsonify({"ok": True, "id": new_customer.id})
    
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] فشل في إضافة العميل: {str(e)}")
        return jsonify({"ok": False, "error": f"خطأ في الإضافة: {str(e)}"}), 500
    
# @app.post("/admin/number")
# def add_number():
#     payload = request.get_json(force=True)
#     client_id = payload.get("client_id")
#     number = payload.get("number")
#     ntype = detect_type(number)
#     if ntype == "unknown":
#         return jsonify({"ok": False, "error": "لا يمكن تحديد نوع الرقم"}), 400
#     with db_conn() as conn:
#         c = conn.cursor()
#         c.execute(
#             "INSERT OR IGNORE INTO numbers (client_id, number, type) VALUES (?,?,?)",
#             (client_id, number, ntype),
#         )
#         conn.commit()
#         return jsonify({"ok": True})

@app.post("/admin/number")
def add_number():
    payload = request.get_json(force=True)
    client_id = payload.get("client_id")
    number = payload.get("number")
    ntype = detect_type(number)
    
    if ntype == "unknown":
        return jsonify({"ok": False, "error": "لا يمكن تحديد نوع الرقم"}), 400
    
    try:
        # التحقق من وجود الرقم مسبقاً
        existing_number = Number.query.filter_by(
            client_id=client_id, 
            number=number
        ).first()
        
        if existing_number:
            # الرقم موجود مسبقاً - تجاهل (مثل INSERT OR IGNORE)
            return jsonify({"ok": True, "message": "الرقم موجود مسبقاً"})
        
        # إضافة رقم جديد
        new_number = Number(
            client_id=client_id,
            number=number,
            type=ntype
        )
        db.session.add(new_number)
        db.session.commit()
        
        return jsonify({"ok": True, "id": new_number.id})
    
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] فشل في إضافة الرقم: {str(e)}")
        return jsonify({"ok": False, "error": f"خطأ في الإضافة: {str(e)}"}), 500

@app.get("/admin/clients")
def list_clients():
    # with db_conn() as conn:
    #     c = conn.cursor()
    #     rows = [
    #         {"id": r[0], "name": r[1], "whatsapp": r[2]}
    #         for r in c.execute("SELECT id,name,whatsapp FROM clients ORDER BY id DESC")
    #     ]
    # return jsonify(rows)
    customers = Customer.query.order_by(Customer.id.desc()).all()
    rows = [
        {"id": c.id, "name": c.name, "whatsapp": c.whatsapp}
        for c in customers
    ]
    return jsonify(rows)

# @app.get("/admin/numbers/<int:client_id>")
# def list_numbers(client_id):
#     with db_conn() as conn:
#         c = conn.cursor()
#         rows = [
#             {"id": r[0], "number": r[1], "type": r[2]}
#             for r in c.execute(
#                 "SELECT id,number,type FROM numbers WHERE client_id=? ORDER BY id",
#                 (client_id,),
#             )
#         ]
#     return jsonify(rows)

@app.get("/admin/numbers/<int:client_id>")
def list_numbers(client_id):
    try:
        # جلب جميع الأرقام للعميل المحدد
        numbers = Number.query.filter_by(client_id=client_id)\
                              .order_by(Number.id)\
                              .all()
        
        rows = [
            {"id": n.id, "number": n.number, "type": n.type}
            for n in numbers
        ]
        
        return jsonify(rows)
    
    except Exception as e:
        print(f"[ERROR] فشل في جلب الأرقام: {str(e)}")
        return jsonify({"error": f"خطأ في جلب البيانات: {str(e)}"}), 500
    

# ========= Webhook =========
@app.post("/webhook/whatsapp")
def whatsapp_webhook():
    print("\n[INFO] تم استلام طلب ويب هوك جديد")
    payload = request.get_json(force=True)
    from_phone = payload.get("fromNumber")
    body = (payload.get("messageBody") or "").strip()
    print(f"[INFO] من: {from_phone}, الرسالة: {body}")

    # with db_conn() as conn:
    #     c = conn.cursor()
    #     c.execute("SELECT id FROM clients WHERE whatsapp=?", (from_phone,))
    #     row = c.fetchone()

    # if not row:
    #     print(f"[INFO] رقم غير مسجل: {from_phone}")
    #     return jsonify({"ok": True})

    # client_id = row[0]
    # استخدام SQLAlchemy
    customer = Customer.query.filter_by(whatsapp=from_phone).first()

    if not customer:
        print(f"[INFO] رقم غير مسجل: {from_phone}")
        return jsonify({"ok": True})

    client_id = customer.id
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
        # with db_conn() as conn:
        #     c = conn.cursor()
        #     c.execute("SELECT number,type FROM numbers WHERE client_id=? ORDER BY id", (client_id,))
        #     nums = c.fetchall()
        # استخدام SQLAlchemy
        numbers = Number.query.filter_by(client_id=client_id).order_by(Number.id).all()
        nums = [(n.number, n.type) for n in numbers]
        print(f"[INFO] تم العثور على {len(nums)} أرقام مسجلة")

        if not nums:
            try:
                send_whatsapp(from_phone, "⚠️ لا توجد أرقام مرتبطة بحسابك.")
            except Exception as e:
                print(f"[ERROR] فشل إرسال رسالة الخطأ: {str(e)}")
            return jsonify({"ok": True})

        results = []
        
        for (num, ntype) in nums:
            try:
                print(f"[DEBUG] جاري استعلام الرقم: {num} (النوع: {ntype})")
                res = query_number(num)
                results.append(res)
                
                log_entry = Log(
                    customer_id=client_id,
                    number=num,
                    type=ntype,
                    response=json.dumps(res, ensure_ascii=False),
                    created_at=datetime.utcnow()
                )
                db.session.add(log_entry)
                db.session.commit()
                    
                    # حفظ في جدول number_history إذا كان الاستعلام ناجحاً
                    # if res.get('data', {}).get('raw'):
                    #     # العثور على number_id
                    #     c.execute("SELECT id FROM numbers WHERE number=? AND client_id=?", (num, client_id))
                    #     number_row = c.fetchone()
                    #     if number_row:
                    #         number_id = number_row[0]
                            
                    #         # استخراج البيانات من النتيجة باستخدام تحليل النص
                    #         try:
                    #             raw_data = json.loads(res['data']['raw'])
                                
                    #             # استخراج النص الكامل من balance
                    #             full_balance_text = raw_data.get('balance', 'غير متوفر')
                                
                    #             # تحليل النص لاستخراج البيانات المختلفة
                    #             balance = 'غير متوفر'
                    #             balance_value = 0.0
                    #             package_value = 0.0
                    #             expiry_date = ''
                    #             min_payment = ''
                    #             speed = ''
                                
                    #             if full_balance_text and full_balance_text != 'غير متوفر':
                    #                 # استخراج رصيد الباقة
                    #                 if 'رصيد الباقة:' in full_balance_text:
                    #                     balance_part = full_balance_text.split('رصيد الباقة:')[1].split('قيمة الباقة:')[0].strip()
                    #                     balance = balance_part
                                        
                    #                     # استخراج القيمة الرقمية للرصيد
                    #                     if 'GB' in balance or 'Gigabyte' in balance:
                    #                         try:
                    #                             balance_value = float(balance.split()[0])
                    #                         except:
                    #                             balance_value = 0.0
                                    
                    #                 # استخراج قيمة الباقة
                    #                 if 'قيمة الباقة:' in full_balance_text:
                    #                     # البحث عن النهاية المناسبة (تأريخ أو تاريخ)
                    #                     package_part = full_balance_text.split('قيمة الباقة:')[1]
                    #                     if 'تأريخ الانتهاء:' in package_part:
                    #                         package_part = package_part.split('تأريخ الانتهاء:')[0].strip()
                    #                     elif 'تاريخ الانتهاء:' in package_part:
                    #                         package_part = package_part.split('تاريخ الانتهاء:')[0].strip()
                                        
                    #                     try:
                    #                         # إزالة أي نص إضافي والحصول على الرقم فقط
                    #                         package_value = float(package_part.replace('ريال', '').strip())
                    #                     except:
                    #                         try:
                    #                             # محاولة استخراج الرقم من النص
                    #                             import re
                    #                             numbers = re.findall(r'\d+', package_part)
                    #                             if numbers:
                    #                                 package_value = float(numbers[0])
                    #                         except:
                    #                             package_value = 0.0
                                    
                    #                 # استخراج تاريخ الانتهاء (تأريخ أو تاريخ)
                    #                 expiry_key = None
                    #                 if 'تأريخ الانتهاء:' in full_balance_text:
                    #                     expiry_key = 'تأريخ الانتهاء:'
                    #                 elif 'تاريخ الانتهاء:' in full_balance_text:
                    #                     expiry_key = 'تاريخ الانتهاء:'
                                    
                    #                 if expiry_key:
                    #                     expiry_part = full_balance_text.split(expiry_key)[1]
                    #                     if 'اقل مبلغ سداد:' in expiry_part:
                    #                         expiry_part = expiry_part.split('اقل مبلغ سداد:')[0].strip()
                    #                     elif 'أقل مبلغ سداد:' in expiry_part:
                    #                         expiry_part = expiry_part.split('أقل مبلغ سداد:')[0].strip()
                    #                     else:
                    #                         expiry_part = expiry_part.strip()
                    #                     expiry_date = expiry_part
                                    
                    #                 # استخراج أقل مبلغ سداد (اقل أو أقل)
                    #                 payment_key = None
                    #                 if 'اقل مبلغ سداد:' in full_balance_text:
                    #                     payment_key = 'اقل مبلغ سداد:'
                    #                 elif 'أقل مبلغ سداد:' in full_balance_text:
                    #                     payment_key = 'أقل مبلغ سداد:'
                                    
                    #                 if payment_key:
                    #                     payment_part = full_balance_text.split(payment_key)[1]
                    #                     if 'السرعة:' in payment_part:
                    #                         payment_part = payment_part.split('السرعة:')[0].strip()
                    #                     else:
                    #                         payment_part = payment_part.strip()
                    #                     min_payment = payment_part
                                    
                    #                 # استخراج السرعة
                    #                 if 'السرعة:' in full_balance_text:
                    #                     speed_part = full_balance_text.split('السرعة:')[1].strip()
                    #                     speed = speed_part
                                
                    #         except Exception as e:
                    #             print(f"[ERROR] خطأ في استخراج البيانات: {str(e)}")
                    #             balance = res.get('data', {}).get('balance', 'غير متوفر')
                    #             balance_value = 0.0
                    #             package_value = 0.0
                    #             expiry_date = ''
                    #             min_payment = ''
                    #             speed = ''
                            
                    #         # إدراج في number_history
                    #         c.execute("""
                    #             INSERT INTO number_history 
                    #             (number_id, balance, balance_value, package_value, expiry_date, min_payment, speed, created_at)
                    #             VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    #         """, (number_id, balance, balance_value, package_value, expiry_date, min_payment, speed, datetime.utcnow().isoformat()))
                            
                    #         # تحديث آخر بيانات في جدول numbers
                    #         c.execute("""
                    #             UPDATE numbers 
                    #             SET last_balance=?, last_balance_value=?, last_balance_timestamp=?
                    #             WHERE id=?
                    #         """, (balance, balance_value, datetime.utcnow().isoformat(), number_id))
                    
                    # conn.commit()
            except Exception as e:
                print(f"[ERROR] خطأ في معالجة الرقم {num}: {str(e)}")
                results.append({"number": num, "type": ntype, "error": f"خطأ في المعالجة: {str(e)}"})

        try:
            report = format_arabic_report(results, client_id)
            send_whatsapp(from_phone, report)
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
    # with db_conn() as conn:
    #     c = conn.cursor()
    #     c.execute("""
    #         SELECT c.id, c.name, c.whatsapp, 
    #                COUNT(n.id) as number_count,
    #                GROUP_CONCAT(n.number) as numbers
    #         FROM clients c
    #         LEFT JOIN numbers n ON c.id = n.client_id
    #         GROUP BY c.id, c.name, c.whatsapp
    #     """)
    #     clients = c.fetchall()
    from sqlalchemy import func

    # استخدام SQLAlchemy
    clients = db.session.query(
        Customer.id,
        Customer.name,
        Customer.whatsapp,
        func.count(Number.id).label('number_count'),
        func.group_concat(Number.number).label('numbers')
    ).outerjoin(Number).group_by(Customer.id, Customer.name, Customer.whatsapp).all()
        
    return render_template('dashboard.html', clients=clients)

@app.route('/client/<int:client_id>/pdf')
@login_required
def download_client_pdf(client_id):
    """تحميل تقرير PDF للعميل"""
    try:
        # جلب أرقام العميل
        numbers = Number.query.filter_by(client_id=client_id).all()
        nums = [(n.number, n.type) for n in numbers]
        
        # استعلام الأرقام
        results = []
        for (num, ntype) in nums:
            try:
                result = query_number(num)
                # result يحتوي على: {"number": ..., "type": ..., "endpoint": ..., "data": ..., "query": ...}
                if 'error' not in result:
                    results.append(result)
                    print(f"[INFO] تم استعلام {num} بنجاح")
                else:
                    print(f"[WARN] خطأ في نتيجة {num}: {result.get('error')}")
                    results.append({"number": num, "error": result.get('error'), 'data': {}, 'query': {}, 'endpoint': 'adsl'})
            except Exception as e:
                print(f"[ERROR] خطأ في استعلام {num}: {e}")
                import traceback
                traceback.print_exc()
                results.append({"number": num, "error": str(e), 'data': {}, 'query': {}, 'endpoint': 'adsl'})
        
        # إنشاء PDF
        pdf_path = generate_pdf_report(results, client_id)
        
        if pdf_path and os.path.exists(pdf_path):
            return send_file(pdf_path, as_attachment=True, 
                           download_name=f'report_{client_id}_{datetime.now().strftime("%Y%m%d")}.pdf')
        else:
            flash('فشل في إنشاء ملف PDF', 'error')
            return redirect(url_for('client_detail', client_id=client_id))
    
    except Exception as e:
        print(f"[ERROR] خطأ في تحميل PDF: {e}")
        flash(f'خطأ: {str(e)}', 'error')
        return redirect(url_for('client_detail', client_id=client_id))

@app.route('/client/<int:client_id>')
@login_required
def client_detail(client_id):
    """صفحة تفاصيل العميل مع أرقامه"""
    # with db_conn() as conn:
    #     c = conn.cursor()
        
    #     # جلب بيانات العميل
    #     c.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
    #     client = c.fetchone()
    customer = Customer.query.get_or_404(client_id)
    client = {
        'id': customer.id,
        'name': customer.name,
        'whatsapp': customer.whatsapp,
        'created_at': customer.created_at,
        'auto_query_time': customer.auto_query_time,
        'auto_query_enabled': customer.auto_query_enabled
    }

    # الأرقام
    numbers_list = Number.query.filter_by(client_id=client_id).order_by(Number.id.desc()).all()
    numbers = [{
        'id': n.id,
        'number': n.number,
        'type': n.type,
        'last_balance': n.last_balance,
        'last_balance_value': n.last_balance_value,
        'last_balance_timestamp': n.last_balance_timestamp
    } for n in numbers_list]
        
        # if not client:
        #     return "العميل غير موجود", 404
            
        # # تحويل إلى dict
        # client = {
        #     'id': client[0],
        #     'name': client[1], 
        #     'whatsapp': client[2],
        #     'created_at': client[3] if len(client) > 3 else None
        # }
        
        # # جلب أرقام العميل
        # c.execute("""
        #     SELECT id, number, type, last_balance, last_balance_value, last_balance_timestamp
        #     FROM numbers 
        #     WHERE client_id = ? 
        #     ORDER BY id DESC
        # """, (client_id,))
        
        # numbers = []
        # for row in c.fetchall():
        #     numbers.append({
        #         'id': row[0],
        #         'number': row[1],
        #         'type': row[2],
        #         'last_balance': row[3],
        #         'last_balance_value': row[4],
        #         'last_balance_timestamp': row[5]
        #     })
    
    return render_template('client_detail.html', client=client, numbers=numbers)

# @app.route('/history')
# @login_required
# def history():
#     """صفحة عرض سجلات الاستعلام"""
#     with db_conn() as conn:
#         c = conn.cursor()
#         c.execute("""
#             SELECT 
#                 nh.id,
#                 n.number,
#                 n.type,
#                 nh.balance,
#                 nh.balance_value,
#                 nh.package_value,
#                 nh.expiry_date,
#                 nh.min_payment,
#                 nh.speed,
#                 nh.created_at,
#                 c.name as client_name
#             FROM number_history nh
#             JOIN numbers n ON nh.number_id = n.id
#             LEFT JOIN clients c ON n.client_id = c.id
#             ORDER BY nh.created_at DESC
#             LIMIT 100
#         """)
#         history_records = c.fetchall()
        
#         # إحصائيات سريعة
#         c.execute("SELECT COUNT(*) FROM number_history")
#         total_queries = c.fetchone()[0]
        
#         c.execute("""
#             SELECT COUNT(DISTINCT number_id) 
#             FROM number_history 
#             WHERE DATE(created_at) = DATE('now')
#         """)
#         today_numbers = c.fetchone()[0]
    
#     return render_template('history.html', 
#                          history_records=history_records,
#                          total_queries=total_queries,
#                          today_numbers=today_numbers)
@app.route('/history')
@login_required
def history():
    """صفحة عرض سجلات الاستعلام"""
    # استيراد الدوال المطلوبة
    from sqlalchemy import func
    from datetime import date
    
    # استخدام Query model - جلب كل البيانات التفصيلية
    history_records = db.session.query(
        Query.id,
        Query.phone_number,
        Query.avblnce,
        Query.balance_unit,
        Query.baga_amount,
        Query.expdate,
        Query.consumption_since_last,
        Query.daily_consumption,
        Query.amount_consumed,
        Query.amount_remaining,
        Query.days_remaining,
        Query.time_since_last,
        Query.notes,
        Query.query_time,
        Customer.name.label('customer_name')
    ).join(Customer, Query.customer_id == Customer.id)\
     .order_by(Query.query_time.desc())\
     .limit(100).all()
    
    # إحصائيات
    total_queries = Query.query.count()
    
    today_queries = Query.query.filter(
        func.date(Query.query_time) == date.today()
    ).count()
    
    return render_template('history.html',
                         history_records=history_records,
                         total_queries=total_queries,
                         today_numbers=today_queries)
# @app.route('/api/query_test/<number>')
# def test_query(number):
#     """API لاختبار استعلام رقم واحد مع حفظ النتائج"""
#     try:
#         result = query_number(number)
        
      
#         # حفظ النتيجة في number_history إذا كان الاستعلام ناجحاً
#         if result.get('data', {}).get('raw'):
#             try:
#                 import json
#                 from datetime import datetime
                
#                 raw_data = json.loads(result['data']['raw'])
#                 if raw_data.get("resultCode") == "0":
#                     with db_conn() as conn:
#                         c = conn.cursor()
#                         now = datetime.utcnow().isoformat()
                        
#                         # البحث عن الرقم أو إنشاؤه
#                         c.execute("SELECT id FROM numbers WHERE number = ?", (number,))
#                         number_record = c.fetchone()
                        
#                         if not number_record:
#                             # إنشاء رقم جديد (افتراضياً للعميل رقم 1)
#                             c.execute(
#                                 "INSERT INTO numbers (client_id, number, type) VALUES (1, ?, ?)",
#                                 (number, result.get('type', 'unknown'))
#                             )
#                             number_id = c.lastrowid
#                         else:
#                             number_id = number_record[0]
                        
#                         # استخراج البيانات بتحليل النص
#                         full_balance_text = raw_data.get('balance', raw_data.get('avblnce', 'غير متوفر'))
                        
#                         # تحليل النص لاستخراج البيانات المختلفة
#                         balance = 'غير متوفر'
#                         balance_value = 0.0
#                         package_value = 0.0
#                         expiry_date = ''
#                         min_payment = ''
#                         speed = ''
                        
#                         if full_balance_text and full_balance_text != 'غير متوفر':
#                             # استخراج رصيد الباقة
#                             if 'رصيد الباقة:' in full_balance_text:
#                                 balance_part = full_balance_text.split('رصيد الباقة:')[1].split('قيمة الباقة:')[0].strip()
#                                 balance = balance_part
                                
#                                 # استخراج القيمة الرقمية للرصيد
#                                 if 'GB' in balance or 'Gigabyte' in balance:
#                                     try:
#                                         balance_value = float(balance.split()[0])
#                                     except:
#                                         balance_value = 0.0
                            
#                             # استخراج قيمة الباقة
#                             if 'قيمة الباقة:' in full_balance_text:
#                                 # البحث عن النهاية المناسبة (تأريخ أو تاريخ)
#                                 package_part = full_balance_text.split('قيمة الباقة:')[1]
#                                 if 'تأريخ الانتهاء:' in package_part:
#                                     package_part = package_part.split('تأريخ الانتهاء:')[0].strip()
#                                 elif 'تاريخ الانتهاء:' in package_part:
#                                     package_part = package_part.split('تاريخ الانتهاء:')[0].strip()
                                
#                                 try:
#                                     # إزالة أي نص إضافي والحصول على الرقم فقط
#                                     package_value = float(package_part.replace('ريال', '').strip())
#                                 except:
#                                     try:
#                                         # محاولة استخراج الرقم من النص
#                                         import re
#                                         numbers = re.findall(r'\d+', package_part)
#                                         if numbers:
#                                             package_value = float(numbers[0])
#                                     except:
#                                         package_value = 0.0
                            
#                             # استخراج تاريخ الانتهاء (تأريخ أو تاريخ)
#                             expiry_key = None
#                             if 'تأريخ الانتهاء:' in full_balance_text:
#                                 expiry_key = 'تأريخ الانتهاء:'
#                             elif 'تاريخ الانتهاء:' in full_balance_text:
#                                 expiry_key = 'تاريخ الانتهاء:'
                            
#                             if expiry_key:
#                                 expiry_part = full_balance_text.split(expiry_key)[1]
#                                 if 'اقل مبلغ سداد:' in expiry_part:
#                                     expiry_part = expiry_part.split('اقل مبلغ سداد:')[0].strip()
#                                 elif 'أقل مبلغ سداد:' in expiry_part:
#                                     expiry_part = expiry_part.split('أقل مبلغ سداد:')[0].strip()
#                                 else:
#                                     expiry_part = expiry_part.strip()
#                                 expiry_date = expiry_part
                            
#                             # استخراج أقل مبلغ سداد (اقل أو أقل)
#                             payment_key = None
#                             if 'اقل مبلغ سداد:' in full_balance_text:
#                                 payment_key = 'اقل مبلغ سداد:'
#                             elif 'أقل مبلغ سداد:' in full_balance_text:
#                                 payment_key = 'أقل مبلغ سداد:'
                            
#                             if payment_key:
#                                 payment_part = full_balance_text.split(payment_key)[1]
#                                 if 'السرعة:' in payment_part:
#                                     payment_part = payment_part.split('السرعة:')[0].strip()
#                                 else:
#                                     payment_part = payment_part.strip()
#                                 min_payment = payment_part
                            
#                             # استخراج السرعة
#                             if 'السرعة:' in full_balance_text:
#                                 speed_part = full_balance_text.split('السرعة:')[1].strip()
#                                 speed = speed_part
                        
#                         # حفظ السجل في number_history
#                         c.execute(
#                             """
#                             INSERT INTO number_history 
#                             (number_id, balance, balance_value, package_value, expiry_date, 
#                              min_payment, speed, created_at)
#                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)
#                             """,
#                             (
#                                 number_id,
#                                 balance,
#                                 balance_value,
#                                 package_value,
#                                 expiry_date,
#                                 min_payment,
#                                 speed,
#                                 now
#                             )
#                         )
                        
#                         # تحديث آخر بيانات في جدول numbers
#                         c.execute("""
#                             UPDATE numbers 
#                             SET last_balance=?, last_balance_value=?, last_balance_timestamp=?
#                             WHERE id=?
#                         """, (balance, balance_value, now, number_id))
#                         conn.commit()
#                         print(f"[INFO] تم حفظ نتيجة الاستعلام للرقم {number} في السجلات")
                        
#             except Exception as save_error:
#                 print(f"[ERROR] فشل حفظ النتيجة في السجلات: {str(save_error)}")
        
#         return jsonify(result)
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

@app.route('/api/query_test/<number>')
def test_query(number):
    """API لاختبار استعلام رقم واحد مع حفظ النتائج"""
    try:
        result = query_number(number)
        
        # حفظ/تحديث الرقم في قاعدة البيانات إذا كان الاستعلام ناجحاً
        if result.get('data', {}).get('raw'):
            try:
                import json
                from datetime import datetime
                
                raw_data = json.loads(result['data']['raw'])
                
                if raw_data.get("resultCode") == "0":
                    now = datetime.utcnow()
                    
                    # استخراج البيانات الأساسية
                    full_balance_text = raw_data.get('balance', raw_data.get('avblnce', 'غير متوفر'))
                    
                    # تحليل النص لاستخراج قيمة الرصيد
                    balance = 'غير متوفر'
                    balance_value = 0.0
                    
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
                    
                    # البحث عن الرقم أو إنشاؤه باستخدام SQLAlchemy
                    existing_number = Number.query.filter_by(number=number).first()
                    
                    if existing_number:
                        # تحديث الرقم الموجود
                        print(f"[INFO] تحديث بيانات الرقم {number}")
                        existing_number.last_balance = balance
                        existing_number.last_balance_value = balance_value
                        existing_number.last_balance_timestamp = now
                        existing_number.type = result.get('type', 'unknown')
                        db.session.commit()
                        print(f"[INFO] ✅ تم تحديث الرقم {number}")
                    else:
                        # إنشاء رقم جديد (افتراضياً للعميل الأول)
                        print(f"[INFO] إنشاء رقم جديد {number}")
                        
                        # العثور على عميل افتراضي
                        default_customer = Customer.query.first()
                        if not default_customer:
                            # إنشاء عميل افتراضي إذا لم يكن موجوداً
                            default_customer = Customer(
                                name="عميل افتراضي",
                                whatsapp="000000000"
                            )
                            db.session.add(default_customer)
                            db.session.commit()
                        
                        new_number = Number(
                            client_id=default_customer.id,
                            number=number,
                            type=result.get('type', 'unknown'),
                            last_balance=balance,
                            last_balance_value=balance_value,
                            last_balance_timestamp=now
                        )
                        db.session.add(new_number)
                        db.session.commit()
                        print(f"[INFO] ✅ تم إنشاء الرقم {number}")
                    
                    print(f"[INFO] ✅ تم حفظ نتيجة الاستعلام للرقم {number}")
                        
            except Exception as save_error:
                print(f"[ERROR] ❌ فشل حفظ النتيجة في السجلات: {str(save_error)}")
                db.session.rollback()
        
        return jsonify(result)
    
    except Exception as e:
        print(f"[ERROR] ❌ خطأ في الاستعلام: {str(e)}")
        return jsonify({"error": str(e)}), 500


# @app.post("/dashboard/add_client")
# def dashboard_add_client():
#     name = request.form.get("name")
#     wa = request.form.get("whatsapp")
#     with db_conn() as conn:
#         c = conn.cursor()
#         c.execute("INSERT INTO clients (name, whatsapp) VALUES (?,?)", (name, wa))
#         conn.commit()
#     return redirect(url_for('dashboard'))
@app.post("/dashboard/add_client")
def dashboard_add_client():
    name = request.form.get("name")
    wa = request.form.get("whatsapp")
    
    new_customer = Customer(name=name, whatsapp=wa)
    db.session.add(new_customer)
    db.session.commit()
    
    return redirect(url_for('dashboard'))
# إضافة رقم جديد لعميل
@app.post("/dashboard/add_number")
def dashboard_add_number():
    client_id = request.form.get("client_id")
    number = request.form.get("number")
    number_type = request.form.get("type", "yemenet")  # افتراضي يمن نت
    
    # with db_conn() as conn:
    #     c = conn.cursor()
    #     c.execute("INSERT OR IGNORE INTO numbers (client_id, number, type) VALUES (?,?,?)", 
    #              (client_id, number, number_type))
    #     conn.commit()
    new_number = Number(
        client_id=int(client_id),
        number=number,
        type=number_type
    )
    db.session.add(new_number)
    db.session.commit()

    
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
    
    # with db_conn() as conn:
    #     c = conn.cursor()
    #     c.execute("UPDATE numbers SET number=?, type=? WHERE id=?", 
    #              (number, number_type, number_id))
    #     conn.commit()
        
    #     # الحصول على client_id للإعادة التوجيه
    #     c.execute("SELECT client_id FROM numbers WHERE id=?", (number_id,))
    #     client_id = c.fetchone()[0]
    try:
    # البحث عن الرقم وتحديثه
        number_obj = Number.query.get_or_404(number_id)
        
        # تحديث البيانات
        number_obj.number = number
        number_obj.type = number_type
        db.session.commit()
        
        # الحصول على client_id للإعادة التوجيه
        client_id = number_obj.client_id
        
        print(f"[INFO] ✅ تم تحديث الرقم {number_id}")
    
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] ❌ فشل في تحديث الرقم: {str(e)}")
        return redirect(url_for('dashboard'))
    if request.referrer and "/client/" in request.referrer:
        return redirect(f"/client/{client_id}")
    return redirect(url_for('dashboard'))

# حذف رقم
@app.post("/dashboard/delete_number")
def dashboard_delete_number():
    number_id = request.form.get("number_id")
    
    # with db_conn() as conn:
    #     c = conn.cursor()
    #     # الحصول على client_id قبل الحذف
    #     c.execute("SELECT client_id FROM numbers WHERE id=?", (number_id,))
    #     result = c.fetchone()
    #     client_id = result[0] if result else None
        
    #     # حذف السجلات المرتبطة أولاً
    #     c.execute("DELETE FROM number_history WHERE number_id=?", (number_id,))
    #     # ثم حذف الرقم
    #     c.execute("DELETE FROM numbers WHERE id=?", (number_id,))
    #     conn.commit()
    try:
    # البحث عن الرقم
        number_obj = Number.query.get(number_id)
        
        if not number_obj:
            print(f"[WARNING] ⚠️ الرقم {number_id} غير موجود")
            return redirect(url_for('dashboard'))
        
        # الحصول على client_id قبل الحذف
        client_id = number_obj.client_id
        
        # حذف جميع الاستعلامات المرتبطة بهذا الرقم من Query model
        Query.query.filter_by(phone_number=number_obj.number).delete()
        
        # حذف الرقم (SQLAlchemy سيحذف العلاقات المرتبطة تلقائياً)
        db.session.delete(number_obj)
        db.session.commit()
        
        print(f"[INFO] ✅ تم حذف الرقم {number_id} وجميع سجلاته")
        
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] ❌ فشل في حذف الرقم: {str(e)}")
        return redirect(url_for('dashboard'))

    if request.referrer and "/client/" in request.referrer and client_id:
        return redirect(f"/client/{client_id}")
    return redirect(url_for('dashboard'))


# GET: Show edit client page
@app.route('/client/<int:client_id>/edit')
@login_required
def edit_client_page(client_id):
    """صفحة تعديل بيانات العميل"""
    customer = Customer.query.get_or_404(client_id)
    numbers_count = Number.query.filter_by(client_id=client_id).count()
    
    client = {
        'id': customer.id,
        'name': customer.name,
        'whatsapp': customer.whatsapp,
        'created_at': customer.created_at,
        'auto_query_time': customer.auto_query_time,
        'auto_query_enabled': customer.auto_query_enabled
    }
    
    return render_template('edit_client.html', client=client, numbers_count=numbers_count)

# POST: Update client
@app.post("/client/<int:client_id>/edit")
@login_required
def update_client(client_id):
    """تحديث بيانات العميل"""
    try:
        customer = Customer.query.get_or_404(client_id)
        
        # تحديث البيانات الأساسية
        customer.name = request.form.get("name")
        customer.whatsapp = request.form.get("whatsapp")
        
        # تحديث إعدادات الاستعلام التلقائي
        auto_query_time_str = request.form.get("auto_query_time")
        if auto_query_time_str:
            from datetime import datetime
            time_obj = datetime.strptime(auto_query_time_str, '%H:%M').time()
            customer.auto_query_time = time_obj
        
        customer.auto_query_enabled = bool(request.form.get("auto_query_enabled"))
        
        db.session.commit()
        print(f"[INFO] ✅ تم تحديث العميل {client_id}")
        
        return redirect(f'/client/{client_id}')
    
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] ❌ فشل في تحديث العميل: {str(e)}")
        return redirect(url_for('dashboard'))

# Delete client (and its numbers)
@app.post("/dashboard/delete_client")
def dashboard_delete_client():
    cid = request.form.get("client_id")
    # with db_conn() as conn:
    #     c = conn.cursor()
    #     c.execute("DELETE FROM numbers WHERE client_id=?", (cid,))
    #     c.execute("DELETE FROM clients WHERE id=?", (cid,))
    #     conn.commit()
    try:
    # البحث عن العميل
        customer = Customer.query.get(cid)
        
        if not customer:
            print(f"[WARNING] ⚠️ العميل {cid} غير موجود")
            return redirect(url_for('dashboard'))
        
        # حذف جميع الاستعلامات المرتبطة بأرقام هذا العميل من Query model
        for number in customer.numbers:
            Query.query.filter_by(phone_number=number.number).delete()
        
        # حذف جميع الأرقام المرتبطة (أو سيتم حذفها تلقائياً إذا كان cascade معرف)
        Number.query.filter_by(client_id=cid).delete()
        
        # حذف العميل
        db.session.delete(customer)
        db.session.commit()
        
        print(f"[INFO] ✅ تم حذف العميل {cid} وجميع أرقامه وسجلاته")
        
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] ❌ فشل في حذف العميل: {str(e)}")
        
    return redirect(url_for('dashboard'))

# Delete number (الدالة المكررة محذوفة)
@app.post("/dashboard/delete_number_old")
def dashboard_delete_number_old():
    nid = request.form.get("number_id")
    # with db_conn() as conn:
    #     c = conn.cursor()
    #     c.execute("DELETE FROM numbers WHERE id=?", (nid,))
    #     conn.commit()
    try:
    # البحث عن الرقم
        number_obj = Number.query.get(nid)
        
        if not number_obj:
            print(f"[WARNING] ⚠️ الرقم {nid} غير موجود")
            return redirect(url_for('dashboard'))
        
        # حذف جميع الاستعلامات المرتبطة بهذا الرقم من Query model
        Query.query.filter_by(phone_number=number_obj.number).delete()
        
        # حذف الرقم
        db.session.delete(number_obj)
        db.session.commit()
        
        print(f"[INFO] ✅ تم حذف الرقم {nid}")
    
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] ❌ فشل في حذف الرقم: {str(e)}")
        
    
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
    
    # with db_conn() as conn:
    #     c = conn.cursor()
        
    #     # جلب قائمة العملاء
    #     c.execute("SELECT id, name, whatsapp FROM clients ORDER BY name")
    #     clients = [{'id': row[0], 'name': row[1], 'whatsapp': row[2]} for row in c.fetchall()]
        
    #     # جلب قائمة الأرقام مع معلومات العملاء
    #     c.execute("""
    #         SELECT n.id, n.number, n.type, c.name, c.whatsapp 
    #         FROM numbers n 
    #         JOIN clients c ON n.client_id = c.id 
    #         ORDER BY n.number
    #     """)
    #     numbers = [{
    #         'id': row[0], 
    #         'number': row[1], 
    #         'type': row[2], 
    #         'client_name': row[3],
    #         'client_whatsapp': row[4]
    #     } for row in c.fetchall()]
    
    # # جلب آخر الرسائل المرسلة
    # recent_messages = []
    # try:
    #     with open('message_logs.json', 'r', encoding='utf-8') as f:
    #         recent_messages = json.load(f)[-5:]  # آخر 5 رسائل
    # except (FileNotFoundError, json.JSONDecodeError):
    #     pass
    
    # return render_template('send_message.html', 
    #                      clients=clients, 
    #                      numbers=numbers,
    #                      recent_messages=recent_messages)
    try:
    # جلب قائمة العملاء باستخدام SQLAlchemy
        customers = Customer.query.order_by(Customer.name).all()
        clients = [
            {'id': c.id, 'name': c.name, 'whatsapp': c.whatsapp}
            for c in customers
        ]
        
        # جلب قائمة الأرقام مع معلومات العملاء
        numbers_query = db.session.query(
            Number.id,
            Number.number,
            Number.type,
            Customer.name,
            Customer.whatsapp
        ).join(Customer, Number.client_id == Customer.id)\
        .order_by(Number.number)\
        .all()
        
        numbers = [
            {
                'id': row[0],
                'number': row[1],
                'type': row[2],
                'client_name': row[3],
                'client_whatsapp': row[4]
            }
            for row in numbers_query
        ]
        
    except Exception as e:
        print(f"[ERROR] ❌ فشل في جلب البيانات: {str(e)}")
        clients = []
        numbers = []

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

# @app.route('/settings')
# @login_required
# def settings_page():
#     """صفحة إعدادات النظام"""
#     # تحميل الإعدادات الحالية
#     settings = {}
#     try:
#         if os.path.exists('settings.json'):
#             with open('settings.json', 'r', encoding='utf-8') as f:
#                 settings = json.load(f)
#     except Exception as e:
#         flash(f'خطأ في تحميل الإعدادات: {e}', 'error')
    
#     # إحصائيات النظام
#     stats = {
#         'total_users': 0,
#         'total_clients': 0,
#         'total_messages': 0,
#         'disk_usage': '0 MB',
#         'server_uptime': '0 يوم 00:00:00',
#         'version': '1.0.0',
#         'last_backup': 'غير متوفر'
#     }
    
#     # جلب إحصائيات قاعدة البيانات
#     try:
#         # تهيئة قاعدة البيانات إذا لم تكن موجودة
#         init_db()
        
#         with db_conn() as conn:
#             c = conn.cursor()
            
#             # التحقق من وجود الجداول أولاً
#             c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
#             if c.fetchone():
#                 # عدد المستخدمين
#                 c.execute("SELECT COUNT(*) FROM users")
#                 stats['total_users'] = c.fetchone()[0]
#             else:
#                 stats['total_users'] = 0
#                 flash('جدول المستخدمين غير موجود', 'warning')
            
#             # عدد العملاء
#             c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clients'")
#             if c.fetchone():
#                 c.execute("SELECT COUNT(*) FROM clients")
#                 stats['total_clients'] = c.fetchone()[0]
#             else:
#                 stats['total_clients'] = 0
#                 flash('جدول العملاء غير موجود', 'warning')
            
#             # عدد الرسائل
#             c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='logs'")
#             if c.fetchone():
#                 c.execute("SELECT COUNT(*) FROM logs")
#                 stats['total_messages'] = c.fetchone()[0]
#             else:
#                 stats['total_messages'] = 0
#                 flash('جدول السجلات غير موجود', 'warning')
            
#     except Exception as e:
#         flash(f'خطأ في جلب إحصائيات قاعدة البيانات: {e}', 'error')
#         # تعيين قيم افتراضية في حالة الخطأ
#         stats['total_users'] = 0
#         stats['total_clients'] = 0
#         stats['total_messages'] = 0
    
#     # حساب استخدام القرص (طريقة متوافقة مع Windows)
#     try:
#         import shutil
#         total, used, free = shutil.disk_usage('.')
#         total_gb = total / (1024 * 1024 * 1024)  # تحويل إلى جيجابايت
#         used_gb = used / (1024 * 1024 * 1024)
#         used_percent = (used / total) * 100
#         stats['disk_usage'] = f'{used_gb:.1f} GB / {total_gb:.1f} GB ({used_percent:.1f}%)'
#     except Exception as e:
#         print(f'Error calculating disk usage: {e}')
#         stats['disk_usage'] = 'غير متاح'
    
#     # وقت تشغيل الخادم
#     try:
#         with open('.server_start_time', 'r') as f:
#             start_time = float(f.read().strip())
#             uptime = time.time() - start_time
#             days = int(uptime // (24 * 3600))
#             uptime = uptime % (24 * 3600)
#             hours = int(uptime // 3600)
#             uptime %= 3600
#             minutes = int(uptime // 60)
#             stats['server_uptime'] = f'{days} يوم {hours:02d}:{minutes:02d}'
#     except:
#         pass
    
#     # آخر نسخة احتياطية
#     try:
#         if os.path.exists('backups'):
#             backups = [f for f in os.listdir('backups') if f.endswith('.db')]
#             if backups:
#                 last_backup = max(backups, key=lambda f: os.path.getmtime(os.path.join('backups', f)))
#                 stats['last_backup'] = time.strftime('%Y-%m-%d %H:%M', 
#                                                   time.localtime(os.path.getmtime(os.path.join('backups', last_backup))))
#     except:
#         pass
    
#     return render_template('settings.html', 
#                          settings=settings, 
#                          stats=stats,
#                          current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


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
    
    # جلب إحصائيات قاعدة البيانات باستخدام SQLAlchemy
    try:
        # عدد المستخدمين
        stats['total_users'] = User.query.count()
        
        # عدد العملاء
        stats['total_clients'] = Customer.query.count()
        
        # عدد السجلات (الرسائل)
        stats['total_messages'] = Log.query.count()
        
        print(f"[INFO] ✅ تم جلب الإحصائيات: {stats['total_users']} مستخدمين، {stats['total_clients']} عملاء، {stats['total_messages']} رسائل")
        
    except Exception as e:
        print(f'[ERROR] ❌ خطأ في جلب إحصائيات قاعدة البيانات: {e}')
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
        print(f'[ERROR] Error calculating disk usage: {e}')
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

# def create_database_backup():
#     """إنشاء نسخة احتياطية من قاعدة البيانات"""
#     try:
#         # إنشاء مجلد النسخ الاحتياطي إذا لم يكن موجوداً
#         backup_dir = Path('backups')
#         backup_dir.mkdir(exist_ok=True)
        
#         # إنشاء اسم ملف النسخة الاحتياطية
#         timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
#         backup_file = backup_dir / f'db_backup_{timestamp}.db'
        
#         # نسخ الملف
#         shutil.copy2(DB_PATH, backup_file)
        
#         # حذف النسخ القديمة (الاحتفاظ بـ 5 نسخ فقط)
#         backups = sorted(backup_dir.glob('db_backup_*.db'), key=os.path.getmtime, reverse=True)
#         for old_backup in backups[5:]:
#             old_backup.unlink()
            
#         return True, 'تم إنشاء نسخة احتياطية بنجاح', backup_file.name
#     except Exception as e:
#         return False, f'خطأ في إنشاء نسخة احتياطية: {str(e)}', None

def create_database_backup():
    """إنشاء نسخة احتياطية من قاعدة البيانات balance.db"""
    try:
        # إنشاء مجلد النسخ الاحتياطي إذا لم يكن موجوداً
        backup_dir = Path('backups')
        backup_dir.mkdir(exist_ok=True)
        
        # إنشاء اسم ملف النسخة الاحتياطية
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = backup_dir / f'balance_backup_{timestamp}.db'
        
        # مسار قاعدة البيانات balance.db (داخل مجلد instance)
        balance_db_path = Path('instance') / 'balance.db'
        
        if not balance_db_path.exists():
            return False, 'ملف balance.db غير موجود', None
        
        # نسخ الملف
        shutil.copy2(balance_db_path, backup_file)
        
        # حذف النسخ القديمة (الاحتفاظ بـ 5 نسخ فقط)
        backups = sorted(backup_dir.glob('balance_backup_*.db'), key=os.path.getmtime, reverse=True)
        for old_backup in backups[5:]:
            old_backup.unlink()
        
        print(f"[INFO] ✅ تم إنشاء نسخة احتياطية: {backup_file.name}")
        return True, 'تم إنشاء نسخة احتياطية بنجاح', backup_file.name
        
    except Exception as e:
        print(f"[ERROR] ❌ خطأ في إنشاء نسخة احتياطية: {str(e)}")
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

import requests

def send_message_flask(phone_number, message, media_file_path=None):
    """
    إرسال رسالة مع ملف إلى API النود.
    
    :param phone_number: رقم الهاتف المستلم
    :param message: نص الرسالة
    :param media_file_path: مسار الملف المرفق (اختياري)
    :return: dict (الرد من API)
    """
    url = "http://localhost:3000/api/send-message"  # استبدل بالمسار الصحيح للـ Node API

    data = {
        "phoneNumber": phone_number,
        "message": message
    }

    files = None
    if media_file_path:
        files = {"media": open(media_file_path, "rb")}

    try:
        response = requests.post(url, data=data, files=files)
        if files:
            files["media"].close()
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}

# @app.route('/api/status')
# def api_status():
#     """API للحصول على حالة النظام - متوافق مع JavaScript الجديد"""
#     try:
#         # الحصول على بيانات الجلسة من خادم Node.js
#         session_data = whatsapp_bot.get_session_data()
#         database_stats = whatsapp_bot.get_database_stats()
        
#         # إحصائيات النظام
#         stats = {
#             'clientReady': session_data.get('status') == 'connected',
#             'sessionActive': bool(session_data.get('phone_number')),
#             'errorCount': 0,
#             'messageQueueLength': database_stats.get('total_messages', 0),
#             'uptime': 0,
#             'memoryUsage': {'used': 0},
#             'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#         }
        
#         try:
#             with db_conn() as conn:
#                 c = conn.cursor()
                
#                 # عدد المستخدمين
#                 c.execute("SELECT COUNT(*) FROM users")
#                 stats['total_users'] = c.fetchone()[0]
                
#                 # عدد العملاء
#                 c.execute("SELECT COUNT(*) FROM clients")
#                 stats['total_clients'] = c.fetchone()[0]
                
#                 # عدد الرسائل
#                 c.execute("SELECT COUNT(*) FROM logs")
#                 stats['total_messages'] = c.fetchone()[0]
                
#         except Exception as e:
#             app.logger.error(f'خطأ في جلب إحصائيات قاعدة البيانات: {e}')
        
#         return jsonify({
#             'success': True,
#             'data': {
#                 'session': {
#                     'isClientReady': stats['clientReady'],
#                     'hasQRCode': session_data.get('qr_code') is not None,
#                     'sessionData': session_data,
#                     'clientState': None,
#                     'timestamp': stats['server_time'],
#                     'isRestarting': False
#                 },
#                 'stats': stats
#             },
#             'status': 'connected' if stats['clientReady'] else 'disconnected',
#             'server_time': stats['server_time']
#         })
#     except Exception as e:
#         return jsonify({
#             'success': False,
#             'message': f'خطأ في جلب حالة النظام: {str(e)}'
#         }), 500

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
        
        # جلب إحصائيات قاعدة البيانات باستخدام SQLAlchemy
        try:
            # عدد المستخدمين
            stats['total_users'] = User.query.count()
            
            # عدد العملاء
            stats['total_clients'] = Customer.query.count()
            
            # عدد الرسائل
            stats['total_messages'] = Log.query.count()
            
        except Exception as e:
            app.logger.error(f'خطأ في جلب إحصائيات قاعدة البيانات: {e}')
            stats['total_users'] = 0
            stats['total_clients'] = 0
            stats['total_messages'] = 0
        
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


# ========= Auto Query Scheduler =========
auto_query_running = True
auto_query_thread = None
last_auto_query_run = None

def auto_query_scheduler(): 
    """
    Background thread للاستعلام التلقائي اليومي
    يستخدم النظام الجديد: numbers + daily_queries
    """
    global last_auto_query_run
    
    # استيراد الدوال الجديدة
    from number_daily_updater import (
        update_number_and_save_daily,
        format_daily_report_from_numbers,
        handle_query_error
    )
    
    while auto_query_running:
        try:
            with app.app_context():
                now = datetime.now().time()
                customers = Customer.query.filter_by(auto_query_enabled=True).all()
                
                for customer in customers:
                    # التحقق من وقت الاستعلام التلقائي
                    if customer.auto_query_time and \
                       customer.auto_query_time.hour == now.hour and \
                       customer.auto_query_time.minute == now.minute:
                        
                        print(f"\n{'='*70}")
                        print(f"🔄 [AUTO] بدء الاستعلام التلقائي للعميل: {customer.name}")
                        print(f"{'='*70}")
                        
                        # الحصول على أرقام العميل
                        numbers = Number.query.filter_by(client_id=customer.id).all()
                        
                        if not numbers:
                            print(f"⚠️ [AUTO] لا توجد أرقام للعميل {customer.name}")
                            continue
                        
                        success_count = 0
                        error_count = 0
                        
                        # استعلام كل رقم وتحديث البيانات
                        for number_obj in numbers:
                            try:
                                print(f"\n📱 استعلام الرقم: {number_obj.number}")
                                
                                # 1. استعلام الرقم من API
                                query_result = query_number(number_obj.number)
                                
                                # عرض النتيجة الكاملة للتأكد
                                print(f"\n   📋 النتيجة الكاملة من API:")
                                print(f"   {json.dumps(query_result, indent=2, ensure_ascii=False)}")
                                
                                if 'error' in query_result:
                                    error_msg = query_result.get('error', 'خطأ غير معروف')
                                    print(f"   ❌ خطأ: {error_msg}")
                                    error_count += 1
                                    
                                    # معالجة الخطأ - حفظ بيانات بحالة خطأ
                                    number_obj = handle_query_error(number_obj, error_msg)
                                    db.session.commit()
                                    
                                    # حفظ سجل يومي بحالة الخطأ
                                    daily_record = DailyQuery(
                                        number_id=number_obj.id,
                                        query_date=date.today(),
                                        query_time=datetime.utcnow(),
                                        package_value=0.0,
                                        balance_gb=0.0,
                                        daily_consumption_gb=0.0,
                                        status="error",
                                        notes=error_msg,
                                        raw_data=json.dumps(query_result, ensure_ascii=False)
                                    )
                                    db.session.add(daily_record)
                                    db.session.commit()
                                    
                                    # حفظ log للخطأ
                                    log_entry = Log(
                                        customer_id=customer.id,
                                        number=number_obj.number,
                                        type=number_obj.type,
                                        response=json.dumps(query_result, ensure_ascii=False),
                                        created_at=datetime.utcnow()
                                    )
                                    db.session.add(log_entry)
                                    db.session.commit()
                                    continue
                                
                                # 2. تحديث جدول numbers + حفظ في daily_queries
                                print(f"\n   🔄 جاري تحديث البيانات...")

                                
                                # استخراج البيانات من المكان الصحيح
                                query_data = query_result.get('query', {}).get('raw', {})
                                print(f"   📦 البيانات المستخرجة للتحديث:")
                                print(f"      - avblnce_gb: {query_data.get('avblnce_gb')}")
                                print(f"      - baga_amount: {query_data.get('baga_amount')}")
                                print(f"      - expdate: {query_data.get('expdate')}")
                                print(f"      - days_remaining: {query_data.get('days_remaining')}")
                                
                                number_obj, daily_record = update_number_and_save_daily(
                                    number_obj,
                                    query_data,  # ✅ استخدام البيانات من raw
                                    raw_data=query_result
                                )
                                
                                print(f"\n   ✅ تم التحديث - البيانات بعد الحفظ:")
                                print(f"      📊 الرصيد السابق: {number_obj.previous_balance_gb:.2f} GB")
                                print(f"      📊 الرصيد الحالي: {number_obj.current_balance_gb:.2f} GB")
                                print(f"      📉 الاستهلاك اليومي: {number_obj.daily_consumption_gb:.2f} GB")
                                print(f"      💰 قيمة الباقة: {number_obj.package_value:.0f} ريال")
                                print(f"      📅 تاريخ الانتهاء: {number_obj.expiry_date}")
                                print(f"      ⏰ الأيام المتبقية: {number_obj.days_remaining}")
                                print(f"      💵 المبلغ المتبقي: {number_obj.amount_remaining:.2f} ريال")
                                print(f"      📝 الحالة: {number_obj.status}")
                                print(f"      📌 الملاحظات: {number_obj.notes}")
                                print(f"   💾 حفظ السجل اليومي: {daily_record.query_date}")
                                
                                # 3. حفظ log للنجاح (اختياري)
                                log_entry = Log(
                                    customer_id=customer.id,
                                    number=number_obj.number,
                                    type=number_obj.type,
                                    response=json.dumps(query_result, ensure_ascii=False),
                                    created_at=datetime.utcnow()
                                )
                                db.session.add(log_entry)
                                db.session.commit()
                                
                                success_count += 1
                                
                            except Exception as e:
                                print(f"   ❌ خطأ في معالجة {number_obj.number}: {e}")
                                import traceback
                                traceback.print_exc()
                                error_count += 1
                        
                        # 4. إرسال التقرير من البيانات المخزنة
                        try:
                            print(f"\n📤 جاري إرسال التقرير للعميل {customer.name}...")
                            
                            # إنشاء التقرير من جدول numbers (البيانات المخزنة)
                            report, one_d, tow_d = format_daily_report_from_numbers(customer.id)
                            
                            # إرسال عبر واتساب
                            send_whatsapp(customer.whatsapp, report)
                            
                            # إنشاء PDF (اختياري)
                            try:
                                pdf_path = create_pdf(one_d, tow_d, customer.name, customer.whatsapp, 'static/image/pdf.png')
                                print(f"   📄 تم إنشاء PDF: {pdf_path}")
                            except Exception as pdf_error:
                                print(f"   ⚠️ فشل إنشاء PDF: {pdf_error}")
                            
                            # تحديث وقت آخر استعلام
                            last_auto_query_run = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            
                            print(f"✅ [AUTO] تم إرسال التقرير بنجاح")
                            print(f"   📊 النتائج: {success_count} نجح، {error_count} فشل")
                            print(f"   📞 تم الإرسال إلى: {customer.whatsapp}")
                            
                        except Exception as e:
                            print(f"❌ [AUTO] فشل إرسال التقرير: {e}")
                            import traceback
                            traceback.print_exc()
                        
                        print(f"{'='*70}\n")
            
            # انتظار دقيقة واحدة قبل التحقق مرة أخرى
            time.sleep(60)
            
        except Exception as e:
            print(f"❌ [AUTO] خطأ في scheduler: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(60)



@app.route('/auto-query')
@login_required
def auto_query_page():
    return render_template('auto_query.html')

@app.get('/api/auto-query/status')
@login_required
def auto_query_status():
    total = Customer.query.count()
    enabled = Customer.query.filter_by(auto_query_enabled=True).count()
    numbers = Number.query.count()
    
    return jsonify({
        'running': auto_query_running,
        'total_customers': total,
        'enabled_customers': enabled,
        'total_numbers': numbers,
        'last_run': last_auto_query_run
    })

@app.get('/api/auto-query/schedule')
@login_required
def auto_query_schedule():
    customers = Customer.query.filter_by(auto_query_enabled=True).all()
    data = []
    for c in customers:
        data.append({
            'name': c.name,
            'numbers_count': Number.query.filter_by(client_id=c.id).count(),
            'auto_query_time': c.auto_query_time.strftime('%H:%M') if c.auto_query_time else '08:00',
            'enabled': c.auto_query_enabled,
            'last_auto_query': None
        })
    return jsonify({'customers': data})

@app.post('/api/auto-query/toggle')
@login_required
def toggle_auto_query():
    global auto_query_running, auto_query_thread
    
    if auto_query_running:
        auto_query_running = False
        if auto_query_thread:
            auto_query_thread.join(timeout=5)
        return jsonify({'running': False})
    else:
        auto_query_running = True
        auto_query_thread = threading.Thread(target=auto_query_scheduler, daemon=True)
        auto_query_thread.start()
        return jsonify({'running': True})
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

# if __name__ == '__main__':
   
#     init_db()
#     cli()
#     with app.app_context():
       
#         print("تم إنشاء قاعدة البيانات والجداول بنجاح")
#     # إنشاء ملف لتتبع وقت بدء التشغيل
#     with open('.server_start_time', 'w') as f:
#         f.write(str(time.time()))
    
#     # إنشاء مجلد النسخ الاحتياطي إذا لم يكن موجوداً
#     os.makedirs('backups', exist_ok=True)
    
#     # بدء مراقبة خادم Node.js
#     monitor_thread.start()
    
#     app.run(debug=True, host='0.0.0.0', port=5000)
# if __name__ == '__main__':
#     # إنشاء قاعدة البيانات والجداول باستخدام SQLAlchemy
#     with app.app_context():
#         # إنشاء جميع الجداول
#         db.create_all()
#         print("[INFO] ✅ تم إنشاء قاعدة البيانات والجداول بنجاح (balance.db)")
        
#         # إنشاء مستخدم admin افتراضي إذا لم يكن موجوداً
#         try:
#             admin_exists = User.query.filter_by(username='admin').first()
#             if not admin_exists:
#                 import hashlib
#                 hashed_password = hashlib.sha256('admin123'.encode('utf-8')).hexdigest()
#                 admin_user = User(
#                     username='admin',
#                     password=hashed_password,
#                     full_name='مدير النظام',
#                     email='admin@example.com',
#                     is_admin=True
#                 )
#                 db.session.add(admin_user)
#                 db.session.commit()
#                 print("[INFO] ✅ تم إنشاء مستخدم admin افتراضي (admin/admin123)")
#             else:
#                 print("[INFO] ℹ️ مستخدم admin موجود مسبقاً")
#         except Exception as e:
#             print(f"[ERROR] ❌ فشل في إنشاء مستخدم admin: {e}")
      
#     # بدء Auto Query Scheduler (افتراضياً مفعّل)
#     if auto_query_running:
#         auto_query_thread = threading.Thread(target=auto_query_scheduler, daemon=True)
#         auto_query_thread.start()
#         print("[INFO] ✅ تم تشغيل Auto Query Scheduler")
    
#     # تشغيل أوامر CLI إذا وجدت
#     cli()
#     # إنشاء ملف لتتبع وقت بدء التشغيل
#     with open('.server_start_time', 'w') as f:
#         f.write(str(time.time()))
    
#     # إنشاء مجلد النسخ الاحتياطي إذا لم يكن موجوداً
#     os.makedirs('backups', exist_ok=True)
#     os.makedirs('instance', exist_ok=True)  # للتأكد من وجود مجلد instance
    
#     # بدء مراقبة خادم Node.js
#     monitor_thread.start()
  
#     print("\n" + "="*50)
#     print("🚀 تشغيل خادم Flask على http://0.0.0.0:5000")
#     print("="*50 + "\n")
#     port = int(os.environ.get('PORT', 5000))
#     # app.run(host='0.0.0.0', port=port)
#     app.run(host='0.0.0.0', port=port)
if __name__ == '__main__':
    with app.app_context():
        # إنشاء جميع الجداول
        db.create_all()
        print("[INFO] ✅ تم إنشاء قاعدة البيانات والجداول بنجاح (balance.db)")

        # إنشاء مستخدم admin افتراضي إذا لم يكن موجوداً
        try:
            admin_exists = User.query.filter_by(username='admin').first()
            if not admin_exists:
                import hashlib
                hashed_password = hashlib.sha256('admin123'.encode('utf-8')).hexdigest()
                admin_user = User(
                    username='admin',
                    password=hashed_password,
                    full_name='مدير النظام',
                    email='admin@example.com',
                    is_admin=True
                )
                db.session.add(admin_user)
                db.session.commit()
                print("[INFO] ✅ تم إنشاء مستخدم admin افتراضي (admin/admin123)")
            else:
                print("[INFO] ℹ️ مستخدم admin موجود مسبقاً")
        except Exception as e:
            print(f"[ERROR] ❌ فشل في إنشاء مستخدم admin: {e}")

    # بدء Auto Query Scheduler إذا مفعل
    if auto_query_running:
        auto_query_thread = threading.Thread(target=auto_query_scheduler, daemon=True)
        auto_query_thread.start()
        print("[INFO] ✅ تم تشغيل Auto Query Scheduler")

    # تشغيل أوامر CLI إذا وجدت
    cli()

    # إنشاء مجلدات للنسخ الاحتياطي وinstance
    os.makedirs('backups', exist_ok=True)
    os.makedirs('instance', exist_ok=True)

    # بدء مراقبة خادم Node.js
    monitor_thread.start()

    # تحديد المنفذ من البيئة وتشغيل Flask
    port = int(os.environ.get('PORT', 5000))
    print(f"\n🚀 تشغيل خادم Flask على http://0.0.0.0:{port}\n")
    app.run(host='0.0.0.0', port=port)


