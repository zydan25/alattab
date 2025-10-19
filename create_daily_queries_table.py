"""
Migration Script: إنشاء جدول الاستعلامات اليومية (DailyQuery)
تاريخ: 2025-10-19
الهدف: إضافة جدول جديد لتسجيل السجل اليومي للاستعلامات
"""

import sqlite3
from pathlib import Path
from datetime import datetime

def create_daily_queries_table():
    """إنشاء جدول daily_queries"""
    
    db_path = Path('instance/balance.db')
    
    if not db_path.exists():
        print(f"❌ قاعدة البيانات غير موجودة: {db_path}")
        return False
    
    print(f"📊 جاري إنشاء جدول daily_queries في: {db_path}")
    print("="*70)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # التحقق من وجود الجدول
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='daily_queries'
        """)
        
        if cursor.fetchone():
            print("⚠️ جدول daily_queries موجود مسبقاً")
            
            # عرض بنية الجدول
            cursor.execute("PRAGMA table_info(daily_queries)")
            columns = cursor.fetchall()
            
            print(f"\n📋 بنية الجدول الموجود ({len(columns)} عمود):")
            for col in columns:
                print(f"   {col[1]:30s} {col[2]}")
            
            conn.close()
            return True
        
        # إنشاء الجدول
        print("🔨 جاري إنشاء جدول daily_queries...")
        
        create_table_sql = """
        CREATE TABLE daily_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number_id INTEGER NOT NULL,
            query_date DATE NOT NULL,
            query_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- بيانات الباقة والرصيد
            package_value REAL DEFAULT 0.0,
            balance_gb REAL DEFAULT 0.0,
            
            -- التواريخ
            expiry_date TIMESTAMP,
            days_remaining INTEGER,
            
            -- الاستهلاك اليومي
            daily_consumption_gb REAL DEFAULT 0.0,
            
            -- المبالغ المالية
            amount_consumed REAL DEFAULT 0.0,
            amount_remaining REAL DEFAULT 0.0,
            
            -- الحالة
            status VARCHAR(20),
            notes VARCHAR(255),
            
            -- البيانات الخام
            raw_data TEXT,
            
            -- المفاتيح الأجنبية والقيود
            FOREIGN KEY (number_id) REFERENCES numbers(id) ON DELETE CASCADE,
            UNIQUE(number_id, query_date)
        )
        """
        
        cursor.execute(create_table_sql)
        print("   ✅ تم إنشاء الجدول")
        
        # إنشاء الفهارس
        print("\n🔍 جاري إنشاء الفهارس...")
        
        indexes = [
            ("idx_daily_number_id", "number_id"),
            ("idx_daily_query_date", "query_date"),
            ("idx_daily_number_date", "number_id, query_date")
        ]
        
        for idx_name, idx_columns in indexes:
            try:
                cursor.execute(f"""
                    CREATE INDEX {idx_name} 
                    ON daily_queries({idx_columns})
                """)
                print(f"   ✅ تم إنشاء الفهرس: {idx_name}")
            except sqlite3.OperationalError as e:
                print(f"   ⚠️ الفهرس {idx_name} موجود مسبقاً")
        
        # حفظ التغييرات
        conn.commit()
        
        # عرض بنية الجدول النهائية
        cursor.execute("PRAGMA table_info(daily_queries)")
        final_columns = cursor.fetchall()
        
        print("\n" + "="*70)
        print(f"📋 بنية جدول daily_queries النهائية ({len(final_columns)} عمود):")
        print("="*70)
        for col in final_columns:
            col_id, name, col_type, not_null, default, pk = col
            pk_mark = "🔑" if pk else "  "
            null_mark = "❌" if not_null else "✅"
            default_val = f" = {default}" if default else ""
            print(f"{pk_mark} {null_mark} {name:30s} {col_type}{default_val}")
        
        # عرض الفهارس
        cursor.execute("""
            SELECT name, sql FROM sqlite_master 
            WHERE type='index' AND tbl_name='daily_queries'
        """)
        indexes_info = cursor.fetchall()
        
        print("\n" + "="*70)
        print(f"🔍 الفهارس ({len(indexes_info)} فهرس):")
        print("="*70)
        for idx in indexes_info:
            print(f"   📌 {idx[0]}")
        
        print("\n" + "="*70)
        print("✅ تم إنشاء جدول daily_queries بنجاح!")
        print("="*70)
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n❌ خطأ أثناء الإنشاء: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_table():
    """التحقق من صحة الجدول"""
    db_path = Path('instance/balance.db')
    
    if not db_path.exists():
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # اختبار إدراج سجل
        print("\n🧪 اختبار إدراج سجل تجريبي...")
        
        # التحقق من وجود رقم للاختبار
        cursor.execute("SELECT id FROM numbers LIMIT 1")
        number = cursor.fetchone()
        
        if not number:
            print("⚠️ لا توجد أرقام للاختبار")
            conn.close()
            return True
        
        from datetime import date
        test_date = date.today()
        
        cursor.execute("""
            INSERT OR REPLACE INTO daily_queries 
            (number_id, query_date, balance_gb, daily_consumption_gb, status)
            VALUES (?, ?, ?, ?, ?)
        """, (number[0], test_date, 50.0, 2.5, 'active'))
        
        conn.commit()
        
        # التحقق من الإدراج
        cursor.execute("""
            SELECT * FROM daily_queries 
            WHERE number_id = ? AND query_date = ?
        """, (number[0], test_date))
        
        result = cursor.fetchone()
        
        if result:
            print("✅ تم إدراج واسترجاع السجل التجريبي بنجاح")
            
            # حذف السجل التجريبي
            cursor.execute("""
                DELETE FROM daily_queries 
                WHERE number_id = ? AND query_date = ?
            """, (number[0], test_date))
            conn.commit()
            print("✅ تم حذف السجل التجريبي")
        else:
            print("❌ فشل اختبار الجدول")
            conn.close()
            return False
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ خطأ في الاختبار: {str(e)}")
        return False


if __name__ == '__main__':
    print("\n🔧 بدء عملية إنشاء جدول DailyQuery")
    print("="*70)
    
    success = create_daily_queries_table()
    
    if success:
        print("\n✅ تم الإنشاء بنجاح!")
        
        # التحقق من الجدول
        if verify_table():
            print("\n✅ الجدول جاهز للاستخدام!")
        else:
            print("\n⚠️ يرجى التحقق من الجدول يدوياً")
    else:
        print("\n❌ فشل الإنشاء!")
        print("💡 يرجى التحقق من الأخطاء أعلاه")
