@echo off
echo ========================================
echo اعداد قاعدة البيانات
echo ========================================
echo.

REM انشاء مجلد instance
if not exist instance mkdir instance
echo تم انشاء مجلد instance

REM تشغيل السكريبت
python quick_setup.py

echo.
echo ========================================
echo انتهى الاعداد
echo ========================================
pause
