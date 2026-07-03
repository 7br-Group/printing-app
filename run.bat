@echo off
echo ====================================
echo   تشغيل نظام المطبعة
echo ====================================
echo.
set "PATH=%~dp0whatsapp_server;%PATH%"
venv\Scripts\python.exe main.py
if errorlevel 1 (
    echo.
    echo حدث خطأ أثناء التشغيل!
    pause
)
