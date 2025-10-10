"""
سكريبت بسيط لإنشاء جداول قاعدة البيانات
"""
import os
import sys
from datetime import time
from flask_migrate import Migrate
from flask.cli import FlaskGroup

cli = FlaskGroup(app)


   

# تحميل المتغيرات من .env
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ تم تحميل ملف .env")
except ImportError:
    print("⚠️ python-dotenv غير مثبت")

from flask import Flask
from database_config import DatabaseConfig
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, column
from datetime import datetime

# إنشاء تطبيق Flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DatabaseConfig.get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = DatabaseConfig.get_engine_options()

# إنشاء كائن قاعدة البيانات
db: SQLAlchemy = SQLAlchemy(app)
migrate = Migrate(app, db)
print("\n" + "="*70)
print("📊 معلومات قاعدة البيانات:")
db_info = DatabaseConfig.get_info()
for key, value in db_info.items():
    print(f"   {key}: {value}")
print("="*70 + "\n")

# تعريف الجداول
# class Package(db.Model):
#     """جدول الباقات"""
#     __tablename__ = 'package'
    
#     id = column(db.Integer, primary_key=True)
#     value = column(db.Integer, nullable=False)
#     volume = column(db.Float, nullable=False)
    
    # def __repr__(self):
    #     return f'<Package {self.value}ريال - {self.volume}GB>'
# افتراضات الموديل (مثال — تأكد أنّ هذه الحقول موجودة في موديلاتك)
class Package(db.Model):
    """جدول الباقات"""
    __tablename__ = 'package'
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Float, nullable=False)   # قيمة الباقة (نقود)
    volume = db.Column(db.Float, nullable=False)  # حجم الباقة بالـ GB
    def to_dict(self):
        return {
            "id": self.id,
            "value": self.value,
            "volume": self.volume
        }
    def __repr__(self):
        return f'<Package {self.value}ريال - {self.volume}GB>'

class Query(db.Model):
    """جدول الاستعلامات"""
    __tablename__ = 'query'
    
    id = Column(db.Integer, primary_key=True)
    phone_number = Column(db.String(32), nullable=False)
    query_time = Column(db.DateTime, default=datetime.utcnow)
    raw_data = Column(db.Text, nullable=False)

    avblnce = Column(db.Float)                 # بالـ GB بعد التحويل
    balance_unit = Column(db.String(10))       # "GB" أو "MB" أو "YER" أو "UNKNOWN"
    baga_amount = Column(db.Float)             # قيمة الباقة كما في الاستعلام
    expdate = Column(db.DateTime)
    days_remaining = db.Column(db.Integer, nullable=True)
    remainAmount = Column(db.Float)
    minamtobill = Column(db.Float)
    daily = Column(db.Boolean, default=False)

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
    auto_query_time = db.Column(db.Time, default=time(8, 0))  # مثلاً 08:00 صباحًا

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


# class Query(db.Model):
#     """جدول الاستعلامات"""
#     __tablename__ = 'query'
    
#     id = column(db.Integer, primary_key=True)
#     phone_number = column(db.String(20), nullable=False, index=True)
#     query_time = column(db.DateTime, default=datetime.utcnow, index=True)
#     raw_data = column(db.Text, nullable=False)
    
#     avblnce = column(db.Float)
#     baga_amount = column(db.Float)
#     expdate = column(db.DateTime)
#     remainAmount = column(db.Float)
#     minamtobill = column(db.Float)
    
#     daily = column(db.Boolean, default=False, index=True)
#     consumption_since_last = column(db.Float, default=0.0)
#     daily_consumption = column(db.Float, default=0.0)
    
#     notes = column(db.String(200))
#     time_since_last = column(db.String(20))
    
#     def __repr__(self):
#         return f'<Query {self.phone_number} - {self.query_time}>'


def main():
    # إنشاء مجلد instance إذا لم يكن موجوداً
    import os
    os.makedirs('instance', exist_ok=True)
    print("✅ تم التأكد من وجود مجلد instance\n")
    
    print("🔧 جاري إنشاء الجداول...")
    
    with app.app_context():
        # إنشاء جميع الجداول
        db.create_all()
        
        print("✅ تم إنشاء جميع الجداول بنجاح!\n")
        
        # عرض الجداول الموجودة
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        print(f"📊 الجداول الموجودة ({len(tables)}):")
        for table in tables:
            columns = inspector.get_columns(table)
            print(f"\n   📋 جدول: {table}")
            print(f"   عدد الأعمدة: {len(columns)}")
            print("   الأعمدة:")
            for col in columns:
                col_type = str(col['type'])
                nullable = "✅" if col['nullable'] else "❌"
                primary = "🔑" if col.get('primary_key') else "  "
                print(f"      {primary} {nullable} {col['name']:20s} - {col_type}")
        
        print("\n" + "="*70)
        print("✅ تم الانتهاء بنجاح!")
        print("="*70 + "\n")
        
        # إضافة بعض البيانات التجريبية
        print("💾 هل تريد إضافة بيانات تجريبية؟ (y/n): ", end="")
        try:
            choice = input().strip().lower()
            if choice == 'y':
                # إضافة باقات تجريبية
                packages = [
                    Package(value=50, volume=10.0),
                    Package(value=100, volume=25.0),
                    Package(value=150, volume=40.0),
                ]
                
                for pkg in packages:
                    existing = Package.query.filter_by(value=pkg.value).first()
                    if not existing:
                        db.session.add(pkg)
                
                db.session.commit()
                print("✅ تم إضافة باقات تجريبية!")
                
                # عرض الباقات
                all_packages = Package.query.all()
                print(f"\n📦 الباقات المضافة ({len(all_packages)}):")
                for pkg in all_packages:
                    print(f"   • {pkg.value} ريال = {pkg.volume} جيجا")
        except KeyboardInterrupt:
            print("\n⏭️ تم التخطي")
        except Exception as e:
            print(f"⚠️ خطأ: {e}")

if __name__ == '__main__':
    try:
        main()
        cli()
    except Exception as e:
        print(f"\n❌ خطأ: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
