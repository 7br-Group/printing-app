#!/bin/bash
# ============================================
# تثبيت نظام المطبعة على Android via Termux
# ============================================

echo "📱 بدأ تثبيت نظام المطبعة على Android..."
echo ""

# 1. تحديث Termux
echo "[1/6] تحديث الحزم..."
pkg update -y && pkg upgrade -y

# 2. تثبيت Python + Node.js + Git
echo "[2/6] تثبيت Python + Node.js + Git..."
pkg install -y python nodejs git

# 3. تثبيت pip dependencies
echo "[3/6] تثبيت مكتبات Python..."
pip install flask requests

# 4. تحميل المشروع
echo "[4/6] تحميل المشروع..."
cd ~
git clone https://github.com/7br-Group/printing-app.git
cd printing-app

# 5. تثبيت Node.js dependencies للواتساب
echo "[5/6] تثبيت خادم واتساب..."
cd whatsapp_server
npm install
cd ..

# 6. إنشاء ملف التشغيل
echo "[6/6] تجهيز التشغيل..."
cat > ~/printing-app/start_termux.sh << 'EOF'
#!/bin/bash
echo "===================================="
echo "  🖨️  تشغيل نظام المطبعة"
echo "===================================="
echo ""

# Kill old processes
pkill -f "node.*server.js" 2>/dev/null
pkill -f "python.*app.py" 2>/dev/null

cd ~/printing-app

# Start WhatsApp server
echo "[1] تشغيل خادم واتساب..."
cd whatsapp_server
node server.js &
sleep 3
cd ..

# Start Flask web app
echo "[2] تشغيل الواجهة..."
WA_SERVER=http://localhost:3000 DATABASE_PATH=~/printing-app/printing_app.db \
    python run_web.py &
sleep 2

echo ""
echo "✅ التطبيق شغال!"
echo "📱 افتح المتصفح على: http://localhost:5000"
echo "🔑 كلمة السر: admin"
echo ""
echo "⚠️  لو عاوز توقف: اضغط Ctrl+C"
echo ""

# Wait
wait
EOF

chmod +x ~/printing-app/start_termux.sh

echo ""
echo "===================================="
echo "  ✅ تم التثبيت بنجاح!"
echo "===================================="
echo ""
echo "📍 لتشغيل التطبيق:"
echo "   cd ~/printing-app && bash start_termux.sh"
echo ""
echo "📍 أو أمر مختصر:"
echo "   bash ~/printing-app/start_termux.sh"
echo ""
