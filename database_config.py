"""
إعدادات قاعدة البيانات - دعم متعدد لـ SQLite, MySQL, PostgreSQL
"""
import os
from urllib.parse import quote_plus

class DatabaseConfig:
    """
    تكوين قاعدة البيانات مع دعم متعدد
    
    طريقة الاستخدام:
    1. SQLite (افتراضي): 
       DATABASE_TYPE=sqlite
       
    2. MySQL:
       DATABASE_TYPE=mysql
       DATABASE_HOST=localhost
       DATABASE_PORT=3306
       DATABASE_USER=root
       DATABASE_PASSWORD=password
       DATABASE_NAME=whatsapp_bot
       
    3. PostgreSQL:
       DATABASE_TYPE=postgresql
       DATABASE_HOST=localhost
       DATABASE_PORT=5432
       DATABASE_USER=postgres
       DATABASE_PASSWORD=password
       DATABASE_NAME=whatsapp_bot
    """
    
    # نوع قاعدة البيانات (sqlite, mysql, postgresql)
    DATABASE_TYPE = os.environ.get('DATABASE_TYPE', 'sqlite')
    
    # إعدادات قاعدة البيانات الخارجية
    DATABASE_HOST = os.environ.get('DATABASE_HOST', 'localhost')
    DATABASE_PORT = os.environ.get('DATABASE_PORT', None)
    DATABASE_USER = os.environ.get('DATABASE_USER', '')
    DATABASE_PASSWORD = os.environ.get('DATABASE_PASSWORD', '')
    DATABASE_NAME = os.environ.get('DATABASE_NAME', 'whatsapp_bot')
    DATABASE_CHARSET = os.environ.get('DATABASE_CHARSET', 'utf8mb4')
    
    # إعدادات SQLite
    SQLITE_DB_PATH = os.environ.get('SQLITE_DB_PATH', 'instance/balance.db')
    
    # إعدادات الاتصال
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_SIZE = int(os.environ.get('DB_POOL_SIZE', 10))
    SQLALCHEMY_POOL_TIMEOUT = int(os.environ.get('DB_POOL_TIMEOUT', 30))
    SQLALCHEMY_POOL_RECYCLE = int(os.environ.get('DB_POOL_RECYCLE', 3600))
    SQLALCHEMY_MAX_OVERFLOW = int(os.environ.get('DB_MAX_OVERFLOW', 20))
    
    @staticmethod
    def get_database_uri():
        """
        بناء URI قاعدة البيانات بناءً على النوع المحدد
        
        الأولوية:
        1. DATABASE_URI (رابط مباشر)
        2. بناء الرابط من الإعدادات المنفصلة
        """
        # الطريقة الأولى: استخدام DATABASE_URI المباشر
        direct_uri = os.environ.get('DATABASE_URI', '').strip()
        if direct_uri:
            print(f"✅ استخدام DATABASE_URI المباشر")
            return direct_uri
        
        # الطريقة الثانية: بناء URI من الإعدادات المنفصلة
        db_type = DatabaseConfig.DATABASE_TYPE.lower()
        
        if db_type == 'sqlite':
            # SQLite - قاعدة بيانات محلية
            return f'sqlite:///{DatabaseConfig.SQLITE_DB_PATH}'
        
        elif db_type == 'mysql':
            # MySQL - قاعدة بيانات خارجية
            port = DatabaseConfig.DATABASE_PORT or 3306
            password = quote_plus(DatabaseConfig.DATABASE_PASSWORD) if DatabaseConfig.DATABASE_PASSWORD else ''
            
            if password:
                uri = (f'mysql+pymysql://{DatabaseConfig.DATABASE_USER}:{password}'
                      f'@{DatabaseConfig.DATABASE_HOST}:{port}'
                      f'/{DatabaseConfig.DATABASE_NAME}'
                      f'?charset={DatabaseConfig.DATABASE_CHARSET}')
            else:
                uri = (f'mysql+pymysql://{DatabaseConfig.DATABASE_USER}'
                      f'@{DatabaseConfig.DATABASE_HOST}:{port}'
                      f'/{DatabaseConfig.DATABASE_NAME}'
                      f'?charset={DatabaseConfig.DATABASE_CHARSET}')
            return uri
        
        elif db_type == 'postgresql' or db_type == 'postgres':
            # PostgreSQL - قاعدة بيانات خارجية
            port = DatabaseConfig.DATABASE_PORT or 5432
            password = quote_plus(DatabaseConfig.DATABASE_PASSWORD) if DatabaseConfig.DATABASE_PASSWORD else ''
            
            if password:
                uri = (f'postgresql+psycopg2://{DatabaseConfig.DATABASE_USER}:{password}'
                      f'@{DatabaseConfig.DATABASE_HOST}:{port}'
                      f'/{DatabaseConfig.DATABASE_NAME}')
            else:
                uri = (f'postgresql+psycopg2://{DatabaseConfig.DATABASE_USER}'
                      f'@{DatabaseConfig.DATABASE_HOST}:{port}'
                      f'/{DatabaseConfig.DATABASE_NAME}')
            return uri
        
        else:
            # افتراضي: SQLite
            print(f"⚠️ نوع قاعدة البيانات '{db_type}' غير مدعوم. استخدام SQLite.")
            return f'sqlite:///{DatabaseConfig.SQLITE_DB_PATH}'
    
    @staticmethod
    def get_engine_options():
        """
        خيارات محرك قاعدة البيانات
        """
        db_type = DatabaseConfig.DATABASE_TYPE.lower()
        
        if db_type == 'sqlite':
            return {
                'pool_pre_ping': True,
                'connect_args': {'check_same_thread': False}
            }
        else:
            # MySQL أو PostgreSQL
            return {
                'pool_size': DatabaseConfig.SQLALCHEMY_POOL_SIZE,
                'pool_timeout': DatabaseConfig.SQLALCHEMY_POOL_TIMEOUT,
                'pool_recycle': DatabaseConfig.SQLALCHEMY_POOL_RECYCLE,
                'max_overflow': DatabaseConfig.SQLALCHEMY_MAX_OVERFLOW,
                'pool_pre_ping': True,  # للتحقق من الاتصال قبل الاستخدام
            }
    
    @staticmethod
    def get_info():
        """
        الحصول على معلومات الاتصال الحالية (للتشخيص)
        """
        db_type = DatabaseConfig.DATABASE_TYPE.lower()
        
        info = {
            'type': db_type,
            'uri': DatabaseConfig.get_database_uri().replace(
                DatabaseConfig.DATABASE_PASSWORD, '****' if DatabaseConfig.DATABASE_PASSWORD else ''
            ),
        }
        
        if db_type != 'sqlite':
            info.update({
                'host': DatabaseConfig.DATABASE_HOST,
                'port': DatabaseConfig.DATABASE_PORT,
                'database': DatabaseConfig.DATABASE_NAME,
                'user': DatabaseConfig.DATABASE_USER,
            })
        else:
            info['path'] = DatabaseConfig.SQLITE_DB_PATH
        
        return info


# دالة مساعدة للتحقق من الاتصال
def test_database_connection(app):
    """
    اختبار الاتصال بقاعدة البيانات
    """
    try:
        from sqlalchemy import text
        with app.app_context():
            from flask_sqlalchemy import SQLAlchemy
            db = SQLAlchemy(app)
            
            # محاولة تنفيذ استعلام بسيط
            db.session.execute(text('SELECT 1'))
            db.session.commit()
            
            print("✅ الاتصال بقاعدة البيانات ناجح!")
            print(f"📊 معلومات الاتصال: {DatabaseConfig.get_info()}")
            return True
    except Exception as e:
        print(f"❌ فشل الاتصال بقاعدة البيانات: {str(e)}")
        print(f"🔍 التكوين الحالي: {DatabaseConfig.get_info()}")
        return False
