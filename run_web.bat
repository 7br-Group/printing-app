@echo off
title خادم الويب - نظام المطبعة
echo ====================================
echo   تشغيل خادم الويب للمشاركة المحلية
echo ====================================
echo.
echo الرابط المحلي: http://localhost:5000
echo الرابط للشبكة: http://%COMPUTERNAME%:5000
echo الباسوورد: admin
echo.
echo للخروج اضغط Ctrl+C
echo ====================================
echo.

set "WA_SERVER=http://localhost:3000"
set "DATABASE_PATH=%~dp0printing_app.db"

"%~dp0venv\Scripts\python.exe" "%~dp0run_web.py"

if errorlevel 1 (
    echo.
    echo حدث خطأ! تأكد من وجود venv و run_web.py
    pause
)
