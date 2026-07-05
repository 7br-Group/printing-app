#!/data/data/com.termux/files/usr/bin/bash
# ============================================
# 📱 تثبيت نظام المطبعة على Android via Termux
# ============================================
# يعمل على Android ARM64 (معظم الأجهزة الحديثة)
# المتطلبات: Termux من F-Droid (مش Google Play)
# ============================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "========================================"
echo "  🖨️  تثبيت نظام إدارة المطبعة"
echo "     على Android via Termux"
echo "========================================"
echo -e "${NC}"
echo ""

# === 1. Update packages ===
echo -e "${YELLOW}[1/8] تحديث الحزم...${NC}"
pkg update -y && pkg upgrade -y

# === 2. Install basic deps ===
echo -e "${YELLOW}[2/8] تثبيت Python + Node.js + git + wget...${NC}"
pkg install -y python nodejs git wget

# === 3. Install Chromium for WhatsApp Web ===
echo -e "${YELLOW}[3/8] تثبيت Chromium (مطلوب لواتساب)...${NC}"
pkg install -y x11-repo
pkg install -y chromium

CHROMIUM_PATH=$(which chromium || which chromium-browser || echo "")
if [ -z "$CHROMIUM_PATH" ]; then
    echo -e "${RED}❌ Chromium متبقيش. رح نستخدم المسار اليدوي.${NC}"
    CHROMIUM_PATH="/data/data/com.termux/files/usr/bin/chromium-browser"
fi

# === 4. Install Python packages ===
echo -e "${YELLOW}[4/8] تثبيت مكتبات Python...${NC}"
pip install flask requests

# === 5. Clone the project ===
echo -e "${YELLOW}[5/8] تحميل المشروع من GitHub...${NC}"
PROJECT_DIR="$HOME/printing-app"

if [ -d "$PROJECT_DIR" ]; then
    echo "📂 المشروع موجود. تحديث..."
    cd "$PROJECT_DIR"
    git pull
else
    cd "$HOME"
    git clone https://github.com/7br-Group/printing-app.git
    cd "$PROJECT_DIR"
fi

# === 6. Install Node.js deps ===
echo -e "${YELLOW}[6/8] تثبيت خادم واتساب (NPM)...${NC}"
cd "$PROJECT_DIR/whatsapp_server"
npm install

# === 7. Create startup script ===
echo -e "${YELLOW}[7/8] إنشاء ملف التشغيل...${NC}"

cat > "$PROJECT_DIR/start_termux.sh" << 'SCRIPT'
#!/data/data/com.termux/files/usr/bin/bash
# =============================
# 🖨️ تشغيل نظام المطبعة على Android
# =============================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_DIR="$HOME/printing-app"
CHROMIUM_PATH="/data/data/com.termux/files/usr/bin/chromium-browser"

# Export puppeteer to find Chromium
export PUPPETEER_EXECUTABLE_PATH="$CHROMIUM_PATH"
export NODE_PATH="$PROJECT_DIR/whatsapp_server/node_modules"
export PATH="$PATH:/data/data/com.termux/files/usr/bin"

cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 إيقاف الخدمات...${NC}"
    kill $WA_PID 2>/dev/null
    kill $WEB_PID 2>/dev/null
    wait
    echo -e "${GREEN}✅ تم الإيقاف${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

echo -e "${CYAN}"
echo "========================================"
echo "  🖨️  تشغيل نظام إدارة المطبعة"
echo "========================================"
echo -e "${NC}"

cd "$PROJECT_DIR"

# 1. Start WhatsApp server
echo -e "${YELLOW}[1/2] تشغيل خادم واتساب...${NC}"
cd whatsapp_server
PUPPETEER_EXECUTABLE_PATH="$CHROMIUM_PATH" \
    npx node server.js &
WA_PID=$!
sleep 4
cd ..

# 2. Start Flask web app
echo -e "${YELLOW}[2/2] تشغيل واجهة الويب...${NC}"
WA_SERVER="http://localhost:3000" \
DATABASE_PATH="$PROJECT_DIR/printing_app.db" \
    python run_web.py &
WEB_PID=$!
sleep 3

echo ""
echo -e "${GREEN}========================================"
echo "  ✅ التطبيق شغال!"
echo "========================================"
echo -e "${NC}"
echo ""
echo -e "${CYAN}📱 افتح المتصفح على:${NC}"
echo "   http://localhost:5000"
echo ""
echo -e "${CYAN}🔑 كلمة السر:${NC} admin"
echo ""
echo -e "${CYAN}📲 عشان يبقى App:${NC}"
echo "   1. افتح http://localhost:5000 في Chrome"
echo "   2. اضغط على القائمة (⁝) ← Add to Home Screen"
echo "   3. هتلاقي أيقونة المطبعة على الشاشة الرئيسية"
echo ""
echo -e "${YELLOW}⚠️  لو عاوز توقف: اضغط Ctrl+C${NC}"
echo ""

wait
SCRIPT

chmod +x "$PROJECT_DIR/start_termux.sh"

# === 8. Done ===
echo -e "${YELLOW}[8/8] تم!${NC}"
echo ""
echo -e "${GREEN}========================================"
echo "  ✅ تم تثبيت نظام المطبعة بنجاح!"
echo "========================================"
echo -e "${NC}"
echo ""
echo -e "${CYAN}📍 للتشغيل:${NC}"
echo "   bash ~/printing-app/start_termux.sh"
echo ""
echo -e "${CYAN}📍 أو:${NC}"
echo "   cd ~/printing-app && bash start_termux.sh"
echo ""
echo -e "${CYAN}📲 بعد التشغيل:${NC}"
echo "   1. افتح Chrome وادخل: http://localhost:5000"
echo "   2. سجل دخول بكلمة: admin"
echo "   3. اضغط قائمة Chrome ← Add to Home Screen"
echo "   4. هتلاقي التطبيق على شاشتك الرئيسية!"
echo ""
echo -e "${YELLOW}⚠️  أول تشغيل:${NC}"
echo "   - هاتوصلك رسالة QR من واتساب"
echo "   - امسحها من واتساب Web عشان تفعيل البوت"
echo "   - الباسوورد: admin"
echo ""
echo -e "${YELLOW}📦 لو عاوز تحديث المشروع:${NC}"
echo "   cd ~/printing-app && git pull"
echo ""
