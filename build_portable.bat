@echo off
chcp 65001 >nul
echo ============================================
echo   بناء النسخة المحمولة - Portable Build
echo ============================================
echo.

set "OUTPUT_DIR=dist\PrintingApp_Portable"

echo [1/6] تنظيف المجلد القديم...
if exist "%OUTPUT_DIR%" rmdir /s /q "%OUTPUT_DIR%"
mkdir "%OUTPUT_DIR%"
mkdir "%OUTPUT_DIR%\whatsapp_server"

echo [2/6] بناء التطبيق الرئيسي (PyInstaller)...
venv\Scripts\pyinstaller.exe --onedir --windowed ^
    --name "PrintingApp" ^
    --add-data "resources;resources" ^
    --add-data "database;database" ^
    --add-data "gui;gui" ^
    --add-data "utils;utils" ^
    --collect-all PySide6 ^
    main.py

if errorlevel 1 (
    echo خطأ في بناء التطبيق!
    pause
    exit /b 1
)

echo [3/6] نسخ التطبيق للمجلد المحمول...
xcopy /E /I /Y "dist\PrintingApp" "%OUTPUT_DIR%\app" >nul

echo [4/6] نسخ خادم واتساب...
xcopy /E /I /Y "whatsapp_server" "%OUTPUT_DIR%\whatsapp_server" >nul

echo [5/6] نسخ قاعدة البيانات...
copy "printing_app.db" "%OUTPUT_DIR%\" >nul 2>&1
copy "resources\styles.qss" "%OUTPUT_DIR%\resources\" >nul 2>&1

echo [6/6] إنشاء مشغل Portable...
(
echo @echo off
echo chcp 65001 ^>nul
echo echo ====================================
echo echo   نظام إدارة المطبعة - Portable
echo echo ====================================
echo echo.
echo set "BASE_DIR=%%~dp0"
echo set "PATH=%%BASE_DIR%%whatsapp_server;%%PATH%%"
echo echo بدء تشغيل التطبيق...
echo start /B "" "%%BASE_DIR%%whatsapp_server\node.exe" "%%BASE_DIR%%whatsapp_server\server.js"
echo echo تم تشغيل خادم واتساب
echo echo.
echo "%%BASE_DIR%%app\PrintingApp.exe"
) > "%OUTPUT_DIR%\Run.bat"

echo.
echo ============================================
echo   تم بناء النسخة المحمولة بنجاح!
echo   المسار: %OUTPUT_DIR%
echo ============================================
echo.
echo محتويات النسخة المحمولة:
dir /a-d /s "%OUTPUT_DIR%" 2>nul | findstr /i /v "File(s)" | findstr /i /v "Dir(s)" | findstr /i /v "Total" | findstr /i "bytes"
echo.
echo اضغط على أي زر لفتح المجلد...
pause >nul
explorer "%OUTPUT_DIR%"
