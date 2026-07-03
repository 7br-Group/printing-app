@echo off
chcp 65001 >nul
echo ====================================
echo   بناء تطبيق نظام المطبعة
echo ====================================
echo.

echo [1/3] تثبيت المكتبات...
venv\Scripts\pip.exe install PySide6 pyinstaller
if errorlevel 1 (
    echo خطأ في تثبيت المكتبات!
    pause
    exit /b 1
)

echo.
echo [2/3] بناء التطبيق...
venv\Scripts\pyinstaller.exe --onefile --windowed ^
    --name "PrintingApp" ^
    --add-data "resources;resources" ^
    --add-data "database;database" ^
    --add-data "gui;gui" ^
    --add-data "utils;utils" ^
    main.py

if errorlevel 1 (
    echo خطأ في البناء!
    pause
    exit /b 1
)

echo.
echo [3/3] نسخ قاعدة البيانات...
if exist database\printing_app.db (
    copy database\printing_app.db dist\ >nul 2>&1
    echo تم نسخ قاعدة البيانات
)

echo.
echo ====================================
echo   تم بناء التطبيق بنجاح!
echo   الملف: dist\PrintingApp.exe
echo   الحجم: ~46 MB
echo ====================================
echo.
echo اضغط على أي زر لفتح مجلد التطبيق...
pause >nul
explorer dist
