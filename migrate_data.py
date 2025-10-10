"""
سكريبت نقل البيانات من db.sqlite3 إلى balance.db
ينقل: العملاء (clients → customers) والأرقام (numbers → numbers)
"""

import sqlite3
from app import app, db, Customer, Number
from datetime import datetime

def migrate_data():
    """نقل البيانات من db.sqlite3 إلى balance.db"""
    
    print("\n" + "="*60)
    print("🔄 بدء نقل البيانات من db.sqlite3 إلى balance.db")
    print("="*60 + "\n")
    
    # الاتصال بقاعدة البيانات القديمة
    try:
        old_db = sqlite3.connect('db.sqlite3')
        old_cursor = old_db.cursor()
        print("✅ تم الاتصال بـ db.sqlite3")
    except Exception as e:
        print(f"❌ فشل الاتصال بـ db.sqlite3: {e}")
        return
    
    with app.app_context():
        # ==========================================
        # 1. نقل العملاء (clients → Customer)
        # ==========================================
        print("\n📋 نقل العملاء...")
        try:
            # جلب جميع العملاء من القاعدة القديمة
            old_cursor.execute("SELECT id, name, whatsapp FROM clients")
            clients_data = old_cursor.fetchall()
            
            clients_count = 0
            skipped_count = 0
            
            for old_id, name, whatsapp in clients_data:
                # التحقق من عدم وجود العميل مسبقاً
                existing = Customer.query.filter_by(whatsapp=whatsapp).first()
                
                if existing:
                    print(f"   ⚠️  تخطي: {name} ({whatsapp}) - موجود مسبقاً")
                    skipped_count += 1
                    continue
                
                # إنشاء عميل جديد
                new_customer = Customer(
                    name=name,
                    whatsapp=whatsapp,
                    created_at=datetime.utcnow()
                )
                
                db.session.add(new_customer)
                clients_count += 1
                print(f"   ✅ {name} ({whatsapp})")
            
            db.session.commit()
            print(f"\n✅ تم نقل {clients_count} عميل، تخطي {skipped_count} موجودين مسبقاً")
            
        except Exception as e:
            print(f"❌ خطأ في نقل العملاء: {e}")
            db.session.rollback()
            old_db.close()
            return
        
        # ==========================================
        # 2. نقل الأرقام (numbers → Number)
        # ==========================================
        print("\n📱 نقل الأرقام...")
        try:
            # جلب جميع الأرقام من القاعدة القديمة
            old_cursor.execute("""
                SELECT n.id, n.client_id, n.number, n.type, 
                       n.last_balance, n.last_balance_value, n.last_balance_timestamp,
                       c.whatsapp
                FROM numbers n
                JOIN clients c ON n.client_id = c.id
            """)
            numbers_data = old_cursor.fetchall()
            
            numbers_count = 0
            skipped_count = 0
            error_count = 0
            
            for old_id, old_client_id, number, num_type, last_balance, last_balance_value, last_balance_timestamp, client_whatsapp in numbers_data:
                # البحث عن العميل في القاعدة الجديدة عبر whatsapp
                customer = Customer.query.filter_by(whatsapp=client_whatsapp).first()
                
                if not customer:
                    print(f"   ❌ خطأ: لم يتم العثور على العميل لرقم {number}")
                    error_count += 1
                    continue
                
                # التحقق من عدم وجود الرقم مسبقاً
                existing = Number.query.filter_by(
                    client_id=customer.id,
                    number=number
                ).first()
                
                if existing:
                    print(f"   ⚠️  تخطي: {number} ({num_type}) - موجود مسبقاً")
                    skipped_count += 1
                    continue
                
                # تحويل timestamp إذا كان موجوداً
                timestamp = None
                if last_balance_timestamp:
                    try:
                        timestamp = datetime.fromisoformat(last_balance_timestamp)
                    except:
                        timestamp = datetime.utcnow()
                
                # إنشاء رقم جديد
                new_number = Number(
                    client_id=customer.id,
                    number=number,
                    type=num_type,
                    last_balance=last_balance,
                    last_balance_value=last_balance_value,
                    last_balance_timestamp=timestamp
                )
                
                db.session.add(new_number)
                numbers_count += 1
                print(f"   ✅ {number} ({num_type}) → {customer.name}")
            
            db.session.commit()
            print(f"\n✅ تم نقل {numbers_count} رقم، تخطي {skipped_count} موجودين، {error_count} أخطاء")
            
        except Exception as e:
            print(f"❌ خطأ في نقل الأرقام: {e}")
            db.session.rollback()
            old_db.close()
            return
    
    # إغلاق الاتصال بالقاعدة القديمة
    old_db.close()
    
    # ==========================================
    # ملخص
    # ==========================================
    print("\n" + "="*60)
    print("✅ اكتمل نقل البيانات بنجاح!")
    print("="*60)
    print(f"\n📊 الإحصائيات النهائية:")
    
    with app.app_context():
        total_customers = Customer.query.count()
        total_numbers = Number.query.count()
        
        print(f"   👥 إجمالي العملاء في balance.db: {total_customers}")
        print(f"   📱 إجمالي الأرقام في balance.db: {total_numbers}")
    
    print("\n" + "="*60)
    print("🎉 يمكنك الآن تشغيل التطبيق: python app.py")
    print("="*60 + "\n")


if __name__ == '__main__':
    # تأكيد من المستخدم
    print("\n⚠️  تحذير: هذا السكريبت سينقل البيانات من db.sqlite3 إلى balance.db")
    print("   - سيتم نقل: العملاء والأرقام فقط")
    print("   - لن يتم حذف أي بيانات من db.sqlite3")
    print("   - البيانات الموجودة في balance.db لن تُحذف، سيتم التخطي إذا كانت موجودة\n")
    
    confirm = input("هل تريد المتابعة؟ (yes/no): ").strip().lower()
    
    if confirm in ['yes', 'y', 'نعم']:
        migrate_data()
    else:
        print("\n❌ تم إلغاء العملية")
