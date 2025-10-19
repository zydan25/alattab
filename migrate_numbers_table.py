"""
Migration Script: إضافة حقول الاستعلام اليومي لجدول الأرقام
تاريخ: 2025-10-19
الهدف: تحديث جدول numbers ليحتوي على بيانات الاستعلام الكاملة
"""

import sqlite3
from pathlib import Path
from datetime import datetime

def migrate_numbers_table():
    """إضافة الحقول الجديدة لجدول الأرقام"""
    
    db_path = Path('instance/balance.db')
    
    if not db_path.exists():
        print(f"❌ قاعدة البيانات غير موجودة: {db_path}")
        return False
    
    print(f"📊 جاري تحديث قاعدة البيانات: {db_path}")
    print("="*70)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # قائمة الحقول الجديدة - مبسطة للاستعلام اليومي فقط
        new_columns = [
            # معلومات الباقة والرصيد
            ("package_value", "REAL DEFAULT 0.0"),
            ("current_balance_gb", "REAL DEFAULT 0.0"),
            
            # تواريخ ووقت
            ("expiry_date", "TIMESTAMP"),
            ("days_remaining", "INTEGER"),
            ("current_query_time", "TIMESTAMP"),
            ("previous_query_time", "TIMESTAMP"),
            
            # الاستهلاك اليومي (الفرق من الأمس)
            ("previous_balance_gb", "REAL DEFAULT 0.0"),
            ("daily_consumption_gb", "REAL DEFAULT 0.0"),
            
            # المبالغ المالية
            ("amount_consumed", "REAL DEFAULT 0.0"),
            ("amount_remaining", "REAL DEFAULT 0.0"),
            
            # الحالة والملاحظات
            ("status", "VARCHAR(20)"),
            ("notes", "VARCHAR(255)"),
        ]
        
        # التحقق من الأعمدة الموجودة
        cursor.execute("PRAGMA table_info(numbers)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        print(f"✅ الأعمدة الموجودة حالياً: {len(existing_columns)}")
        
        # إضافة الأعمدة الجديدة
        added_count = 0
        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                try:
                    sql = f"ALTER TABLE numbers ADD COLUMN {col_name} {col_type}"
                    cursor.execute(sql)
                    print(f"   ✅ تمت إضافة: {col_name} ({col_type})")
                    added_count += 1
                except sqlite3.OperationalError as e:
                    print(f"   ⚠️ خطأ في إضافة {col_name}: {e}")
            else:
                print(f"   ⏭️ موجود مسبقاً: {col_name}")
        
        # حفظ التغييرات
        conn.commit()
        
        # عرض بنية الجدول النهائية
        cursor.execute("PRAGMA table_info(numbers)")
        final_columns = cursor.fetchall()
        
        print("\n" + "="*70)
        print(f"📋 بنية جدول numbers النهائية ({len(final_columns)} عمود):")
        print("="*70)
        for col in final_columns:
            col_id, name, col_type, not_null, default, pk = col
            pk_mark = "🔑" if pk else "  "
            null_mark = "❌" if not_null else "✅"
            print(f"{pk_mark} {null_mark} {name:30s} {col_type}")
        
        print("\n" + "="*70)
        print(f"✅ تم الانتهاء بنجاح!")
        print(f"📊 تمت إضافة {added_count} عمود جديد")
        print("="*70)
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n❌ خطأ أثناء التحديث: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("\n🔧 بدء عملية Migration")
    print("="*70)
    success = migrate_numbers_table()
    
    if success:
        print("\n✅ تم التحديث بنجاح!")
        print("💡 يمكنك الآن تشغيل التطبيق")
    else:
        print("\n❌ فشل التحديث!")
        print("💡 يرجى التحقق من الأخطاء أعلاه")
