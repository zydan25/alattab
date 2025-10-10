"""
إعداد سريع - إنشاء قاعدة البيانات والجداول
"""
import os
import sys

# إنشاء مجلد instance
os.makedirs('instance', exist_ok=True)
print("✅ تم إنشاء مجلد instance")

# تحميل المتغيرات
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# إنشاء التطبيق
app = Flask(__name__)

# إعدادات قاعدة البيانات
DATABASE_URI = os.environ.get('DATABASE_URI', 'sqlite:///instance/balance.db')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

print(f"\n📊 قاعدة البيانات: {DATABASE_URI}\n")

db = SQLAlchemy(app)

# تعريف الجداول
class Package(db.Model):
    __tablename__ = 'package'
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Integer, nullable=False)
    volume = db.Column(db.Float, nullable=False)

class Query(db.Model):
    __tablename__ = 'query'
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), nullable=False, index=True)
    query_time = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    raw_data = db.Column(db.Text, nullable=False)
    avblnce = db.Column(db.Float)
    baga_amount = db.Column(db.Float)
    expdate = db.Column(db.DateTime)
    remainAmount = db.Column(db.Float)
    minamtobill = db.Column(db.Float)
    daily = db.Column(db.Boolean, default=False, index=True)
    consumption_since_last = db.Column(db.Float, default=0.0)
    daily_consumption = db.Column(db.Float, default=0.0)
    notes = db.Column(db.String(200))
    time_since_last = db.Column(db.String(20))

# إنشاء الجداول
print("🔧 جاري إنشاء الجداول...")
with app.app_context():
    db.create_all()
    print("✅ تم إنشاء الجداول بنجاح!\n")
    
    # عرض الجداول
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    print(f"📋 الجداول ({len(tables)}):")
    for table in tables:
        print(f"   ✓ {table}")
    
    # إضافة باقات تجريبية
    print("\n💾 إضافة باقات تجريبية...")
    packages_data = [
        (50, 10.0),
        (100, 25.0),
        (150, 40.0),
    ]
    
    for value, volume in packages_data:
        existing = Package.query.filter_by(value=value).first()
        if not existing:
            pkg = Package(value=value, volume=volume)
            db.session.add(pkg)
    
    db.session.commit()
    
    all_packages = Package.query.all()
    print(f"✅ تم إضافة {len(all_packages)} باقة:")
    for pkg in all_packages:
        print(f"   • {pkg.value} ريال = {pkg.volume} GB")

print("\n" + "="*50)
print("✅ الإعداد اكتمل بنجاح!")
print("="*50)
