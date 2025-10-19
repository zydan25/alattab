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


class Number(db.Model):
    """جدول الأرقام مع بيانات الاستعلام اليومي - مبسط"""
    __tablename__ = "numbers"
    
    # ====== المعلومات الأساسية ======
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    client_id = db.Column(db.Integer, db.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    number = db.Column(db.String, nullable=False)
    type = db.Column(db.String, nullable=False)  # yemenet أو yemen4g
    
    # ====== بيانات الباقة والرصيد (من آخر استعلام يومي) ======
    package_value = db.Column(db.Float, default=0.0)  # قيمة الباقة بالريال
    current_balance_gb = db.Column(db.Float, default=0.0)  # الرصيد الحالي بالجيجا
    
    # ====== التواريخ والوقت ======
    expiry_date = db.Column(db.DateTime)  # تاريخ انتهاء الباقة
    days_remaining = db.Column(db.Integer)  # الأيام المتبقية
    current_query_time = db.Column(db.DateTime)  # وقت الاستعلام الحالي
    previous_query_time = db.Column(db.DateTime)  # وقت الاستعلام السابق (الأمس)
    
    # ====== الاستهلاك اليومي (الفرق من الأمس) ======
    previous_balance_gb = db.Column(db.Float, default=0.0)  # الرصيد في الاستعلام السابق
    daily_consumption_gb = db.Column(db.Float, default=0.0)  # الاستهلاك اليومي = السابق - الحالي
    
    # ====== المبالغ المالية ======
    amount_consumed = db.Column(db.Float, default=0.0)  # المبلغ المستهلك (ريال)
    amount_remaining = db.Column(db.Float, default=0.0)  # المبلغ المتبقي (ريال)
    
    # ====== الحالة والملاحظات ======
    status = db.Column(db.String(20))  # الحالة: active, warning, critical, expired
    notes = db.Column(db.String(255))  # ملاحظات تلقائية (مثل: تم التسديد، قرب الانتهاء)
    
    __table_args__ = (
        db.UniqueConstraint('client_id', 'number', name='uix_client_number'),
    )
    
    def __repr__(self):
        return f'<Number {self.number} - {self.current_balance_gb}GB>'
    
    def calculate_daily_consumption(self):
        """حساب الاستهلاك اليومي من الفرق بين الأمس واليوم"""
        if self.previous_balance_gb and self.current_balance_gb:
            # التعامل مع حالة التعبئة (إذا زاد الرصيد)
            if self.current_balance_gb > self.previous_balance_gb:
                # تم التسديد - نحتاج للباقة لحساب الاستهلاك الصحيح
                # الاستهلاك = الرصيد السابق + حجم الباقة الجديدة - الرصيد الحالي
                return 0.0  # سيتم الحساب في دالة التحديث
            else:
                # استهلاك عادي
                return self.previous_balance_gb - self.current_balance_gb
        return 0.0
    
    def to_dict(self):
        """تحويل بيانات الرقم إلى قاموس"""
        return {
            'id': self.id,
            'number': self.number,
            'type': self.type,
            'package_value': self.package_value,
            'current_balance_gb': self.current_balance_gb,
            'previous_balance_gb': self.previous_balance_gb,
            'daily_consumption_gb': self.daily_consumption_gb,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'days_remaining': self.days_remaining,
            'amount_consumed': self.amount_consumed,
            'amount_remaining': self.amount_remaining,
            'status': self.status,
            'notes': self.notes,
            'current_query_time': self.current_query_time.isoformat() if self.current_query_time else None,
            'previous_query_time': self.previous_query_time.isoformat() if self.previous_query_time else None
        }


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
