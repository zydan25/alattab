"""
سكريبت اختبار الاتصال بقاعدة البيانات
"""
import os
import sys

# تحميل المتغيرات من .env
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ تم تحميل ملف .env")
except ImportError:
    print("⚠️ لم يتم تثبيت python-dotenv، سيتم استخدام متغيرات البيئة فقط")

from flask import Flask
from database_config import DatabaseConfig, test_database_connection

def main():
    print("\n" + "="*70)
    print("🧪 اختبار الاتصال بقاعدة البيانات")
    print("="*70 + "\n")
    
    # عرض الإعدادات الحالية
    print("📋 الإعدادات الحالية:")
    db_info = DatabaseConfig.get_info()
    for key, value in db_info.items():
        print(f"   {key}: {value}")
    print()
    
    # إنشاء تطبيق Flask للاختبار
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = DatabaseConfig.get_database_uri()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = DatabaseConfig.get_engine_options()
    
    # اختبار الاتصال
    print("🔌 جاري اختبار الاتصال...")
    success = test_database_connection(app)
    
    if success:
        print("\n✅ نجح الاتصال! يمكنك الآن استخدام قاعدة البيانات.")
        
        # محاولة إنشاء الجداول
        try:
            from flask_sqlalchemy import SQLAlchemy
            with app.app_context():
                db = SQLAlchemy(app)
                
                # استيراد النماذج
                from app import Package, Query
                
                # إنشاء الجداول
                db.create_all()
                print("✅ تم إنشاء جميع الجداول بنجاح!")
                
                # عرض الجداول الموجودة
                from sqlalchemy import inspect
                inspector = inspect(db.engine)
                tables = inspector.get_table_names()
                print(f"\n📊 الجداول الموجودة ({len(tables)}):")
                for table in tables:
                    columns = inspector.get_columns(table)
                    print(f"   • {table} ({len(columns)} عمود)")
                
        except Exception as e:
            print(f"⚠️ تحذير: {str(e)}")
        
        return 0
    else:
        print("\n❌ فشل الاتصال! يرجى التحقق من الإعدادات.")
        print("\n💡 نصائح:")
        print("   1. تأكد من تثبيت المكتبات المطلوبة:")
        print("      pip install -r requirements-database.txt")
        print("   2. تحقق من إعدادات قاعدة البيانات في ملف .env")
        print("   3. تأكد من تشغيل خادم قاعدة البيانات (MySQL/PostgreSQL)")
        return 1

if __name__ == '__main__':
    sys.exit(main())
