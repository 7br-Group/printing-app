const express = require('express');
const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcode = require('qrcode');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(express.json());

let client = null;
let connected = false;
let connecting = false;
let phone = '';
let currentQr = '';
let lastQr = '';
let autoReplies = {};
let welcomeMessage = '';
let reconnectAttempts = 0;
const MAX_RECONNECT_DELAY = 60000;

const conversations = {};
const ORDER_STEPS = { NONE: 'none', AWAITING_QUANTITY: 'awaiting_quantity', AWAITING_PAYMENT: 'awaiting_payment', CONFIRMED: 'confirmed' };
const customerInterests = {};

const DB_PATH = process.env.DATABASE_PATH || path.join(__dirname, '..', 'printing_app.db');

function getDb() {
    try { return new (require('sqlite3')).Database(DB_PATH); }
    catch { return null; }
}

let productsCache = [];
async function refreshProducts() {
    try {
        const db = getDb();
        if (!db) return;
        await new Promise(resolve => {
            db.all('SELECT id, name, description, price, quantity, image_path FROM products WHERE is_active = 1', (err, rows) => {
                if (!err) productsCache = rows || [];
                db.close();
                resolve();
            });
        });
    } catch {}
}
refreshProducts();
setInterval(refreshProducts, 30000);

// Clean old conversations every 5 minutes
setInterval(() => {
    const cutoff = Date.now() - 86400000;
    for (const num of Object.keys(conversations)) {
        if ((conversations[num].timestamp || 0) < cutoff) delete conversations[num];
    }
    for (const num of Object.keys(customerInterests)) {
        let hasRecent = false;
        for (const key of Object.keys(customerInterests[num] || {})) {
            if (customerInterests[num][key].count <= 0) delete customerInterests[num][key];
            else hasRecent = true;
        }
        if (!hasRecent) delete customerInterests[num];
    }
}, 300000);

// ===== Egyptian Arabic Synonym Map =====
const EGYPTIAN_SYNONYMS = {
    'سعر': ['سعر', 'كام', 'بكام', 'ثمن', 'قيمة', 'المبلغ', 'فلوس', 'تكلفة', 'price'],
    'عايز': ['عايز', 'عاوز', 'عي', 'حابب', 'نفسي', 'أريد', 'اريد', 'محتاج', 'بدي', 'بغى', 'ابي', 'want', 'need'],
    'مج': ['مج', 'كوباية', 'كوب', 'كاسة', 'كاس', 'فنجان', 'كوبايه', 'mug', 'cup', 'glass'],
    'تيشيرت': ['تيشيرت', 'تيشرت', 'قميص', 't-shirt', 'tshirt', 'shirt', 't_shirt'],
    'شنطة': ['شنطة', 'حقيبة', 'bag', 'شنط'],
    'قلم': ['قلم', 'pen', 'أقلام', 'اقلام'],
    'استيكر': ['استيكر', 'ستيكر', 'لاصق', 'sticker', 'ملصق'],
    'طباعة': ['طباعة', 'طباعه', 'طبع', 'print', 'printing', 'مطبوعات'],
    'هدية': ['هدية', 'هديه', 'هدايا', 'gift', 'present'],
    'دعاية': ['دعاية', 'دعايه', 'اعلان', 'إعلان', 'بروشور', 'brochure', 'فلاير', 'flyer', 'بروشت'],
    'بطاقة': ['بطاقة', 'كارت', 'card', 'فيزيت', 'visit', 'personal'],
    'كمية': ['كمية', 'كميه', 'عدد', 'كثرة', 'quantity', 'amount'],
    'طلب': ['طلب', 'أطلب', 'اطلب', 'order', 'شراء', 'اشترى', 'اشتري', 'شرا', 'بيع'],
    'متى': ['متى', 'امتى', 'إمتى', 'وقت', 'موعد', 'تاريخ', 'when', 'time'],
    'متوفر': ['متوفر', 'موجود', 'في', 'عندك', 'available', 'موجوده'],
    'توصيل': ['توصيل', 'delivery', 'شحن', 'وصل', 'يوصل', 'دليفري'],
    'خصم': ['خصم', 'تخفيض', 'discount', 'عرض', 'offers', 'عروض'],
    'وكم': ['وكم', 'وكام', 'وكمان'],
};

const BUYING_KEYWORDS = ['عايز', 'عاوز', 'عي', 'محتاج', 'بدي', 'أطلب', 'اطلب', 'طلب', 'شراء', 'اشتري', 'اشترى', 'ابي'];
const INQUIRY_KEYWORDS = ['سعر', 'كام', 'بكام', 'كم', 'price', 'موجود', 'متوفر', 'عندك', 'في'];
const GREETING_KEYWORDS = ['السلام', 'السلام عليكم', 'سلام', 'مرحبا', 'أهلا', 'اهلا', 'hello', 'hi', 'صباح', 'مساء'];
const LIST_KEYWORDS = ['عندك', 'المنتجات', 'products', 'القائمة', 'list', 'فيه', 'معاك'];
const PAYMENT_KEYWORDS = {
    'كاش': ['كاش', 'cash', 'نقد', 'نقدا'],
    'بطاقة ائتمان': ['كارد', 'card', 'بطاقه', 'بطاقة', 'فيزا', 'mastercard'],
    'فودافون كاش': ['فودافون', 'vodafone', 'فودافون كاش'],
    'انستاباي': ['انستا', 'insta', 'انستاباي', 'تحويل', 'حواله'],
};

function normalizeArabic(text) {
    return text.replace(/[إأٱآا]/g, 'ا').replace(/[ى]/g, 'ي').replace(/[ؤ]/g, 'و').replace(/[ة]/g, 'ه').replace(/[ئ]/g, 'ي').toLowerCase();
}

function extractNumber(text) {
    const arabicNums = { '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4', '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9' };
    let n = text;
    for (const [ar, en] of Object.entries(arabicNums)) n = n.replace(new RegExp(ar, 'g'), en);
    const m = n.match(/\d+/g);
    return m ? parseInt(m[0]) : null;
}

function matchProduct(message, products) {
    if (!products || !products.length) return null;
    const normalized = normalizeArabic(message);
    const requestedNumber = extractNumber(message);
    let bestMatch = null, bestScore = 0;
    for (const product of products) {
        const prodName = normalizeArabic(product.name);
        let score = 0;
        for (const word of prodName.split(/\s+/)) {
            if (word.length > 1 && normalized.includes(word)) score += 10;
        }
        for (const [, synonyms] of Object.entries(EGYPTIAN_SYNONYMS)) {
            for (const syn of synonyms) {
                const synNorm = normalizeArabic(syn);
                if (normalized.includes(synNorm)) { score += 5; if (prodName.includes(synNorm)) score += 15; break; }
            }
        }
        if (requestedNumber !== null && prodName.includes(requestedNumber.toString())) score += 50;
        if (score > bestScore) { bestScore = score; bestMatch = product; }
    }
    return bestScore >= 10 ? bestMatch : null;
}

function hasBuyingIntent(msg) { const n = normalizeArabic(msg); return BUYING_KEYWORDS.some(k => n.includes(normalizeArabic(k))); }
function isGreeting(msg) { const n = normalizeArabic(msg); return GREETING_KEYWORDS.some(k => n.includes(normalizeArabic(k))); }
function isListProductsRequest(msg) { const n = normalizeArabic(msg); return LIST_KEYWORDS.some(k => n.includes(normalizeArabic(k))); }

function detectPaymentMethod(msg) {
    const n = normalizeArabic(msg);
    for (const [method, keywords] of Object.entries(PAYMENT_KEYWORDS)) {
        if (keywords.some(k => n.includes(k))) return method;
    }
    return null;
}

function getProductImagePath(product) {
    if (!product || !product.image_path) return null;
    if (fs.existsSync(product.image_path)) return product.image_path;
    const rel = path.join(path.dirname(DB_PATH), product.image_path);
    return fs.existsSync(rel) ? rel : null;
}

function formatProductReply(product, prefix = '') {
    return `${prefix}*${product.name}*\n💰 السعر: ${product.price} ج.م\n📦 الحالة: ${product.quantity > 0 ? 'متوفر' : 'غير متوفر حالياً'}`;
}

function formatProductList(products) {
    if (!products || !products.length) return 'لا توجد منتجات متاحة حالياً';
    return '*قائمة المنتجات المتاحة:*\n\n' + products.map((p, i) => `${i + 1}. *${p.name}* — ${p.price} ج.م`).join('\n') + '\n\nأرسل اسم المنتج لمعرفة سعره\nأو أرسل "عايز (اسم المنتج)" للشراء';
}

async function getAutoReply(message, fromNumber) {
    const normalized = normalizeArabic(message);
    const conv = conversations[fromNumber];

    // ── Check auto-replies from settings ──────────────────────────
    for (const [keyword, reply] of Object.entries(autoReplies)) {
        if (normalized.includes(normalizeArabic(keyword))) {
            return reply;
        }
    }

    // ── Order flow: awaiting quantity ─────────────────────────────
    if (conv && conv.step === ORDER_STEPS.AWAITING_QUANTITY) {
        const qty = extractNumber(message);
        if (qty && qty > 0) {
            conv.quantity = qty;
            conv.step = ORDER_STEPS.AWAITING_PAYMENT;
            return `حضرتك عايز ${qty} قطعة من *${conv.productName}*\n\nاختر طريقة الدفع:\n1️⃣ كاش\n2️⃣ بطاقة ائتمان\n3️⃣ فودافون كاش\n4️⃣ انستاباي`;
        }
        if (normalized.includes('لا') || normalized.includes('مش') || normalized.includes('الف')) {
            conv.step = ORDER_STEPS.NONE;
            return 'تمام، لو احتجت أي حاجة تاني أنا موجود 🤝';
        }
        return 'من فضلك اكتب العدد المطلوب (مثلاً: 5)\nأو أرسل "لا" للإلغاء';
    }

    // ── Order flow: awaiting payment → confirm order ──────────────
    if (conv && conv.step === ORDER_STEPS.AWAITING_PAYMENT) {
        const method = detectPaymentMethod(message);
        if (method) {
            conv.paymentMethod = method;
            conv.step = ORDER_STEPS.CONFIRMED;
            saveOrderToDB(conv, fromNumber, message);
            return `✅ *تم تسجيل طلبك!*\n\nالمنتج: *${conv.productName}*\nالكمية: ${conv.quantity}\nطريقة الدفع: ${method}\n\nسنقوم بالتواصل معك قريباً لتأكيد الطلب.\nشكراً لتسوقك معنا! 🙏`;
        }
        return 'طريقة الدفع غير معروفة. اختر:\n1️⃣ كاش\n2️⃣ بطاقة ائتمان\n3️⃣ فودافون كاش\n4️⃣ انستاباي';
    }

    if (isGreeting(message) && welcomeMessage) return welcomeMessage;
    if (isListProductsRequest(message)) return formatProductList(productsCache);

    // ── Match product ─────────────────────────────────────────────
    const matchedProduct = matchProduct(message, productsCache);
    if (matchedProduct) {
        if (!customerInterests[fromNumber]) customerInterests[fromNumber] = {};
        const key = matchedProduct.id;
        if (!customerInterests[fromNumber][key]) customerInterests[fromNumber][key] = { productId: key, productName: matchedProduct.name, count: 0 };
        customerInterests[fromNumber][key].count++;

        conversations[fromNumber] = {
            productId: key,
            productName: matchedProduct.name,
            productPrice: matchedProduct.price,
            step: ORDER_STEPS.NONE,
            lastMessage: message,
            timestamp: Date.now()
        };

        if (hasBuyingIntent(message)) {
            conversations[fromNumber].step = ORDER_STEPS.AWAITING_QUANTITY;
            let r = formatProductReply(matchedProduct);
            if (matchedProduct.description) r += `\n📝 ${matchedProduct.description}`;
            return r + `\n\nكم قطعة عايز من *${matchedProduct.name}*؟`;
        }

        let r = formatProductReply(matchedProduct);
        if (matchedProduct.description) r += `\n📝 ${matchedProduct.description}`;
        r += `\n\nعايز تشتري؟ أرسل "عايز ${matchedProduct.name}"`;

        saveInquiry(fromNumber, message, matchedProduct.id, `استفسار عن ${matchedProduct.name}: ${message}`, 'medium');
        return r;
    }

    if (conv && conv.productId && (normalized.includes('تأكيد') || normalized.includes('أكيد') || normalized.includes('اكيد') || normalized.includes('تم'))) {
        if (conv.step === ORDER_STEPS.CONFIRMED) return 'طلبك مسجل بالفعل! سنتواصل معك قريباً ✅';
        if (conv.step === ORDER_STEPS.NONE) { conversations[fromNumber].step = ORDER_STEPS.AWAITING_QUANTITY; return `كم قطعة عايز من *${conv.productName}*؟`; }
    }

    if (conv && conv.productId && conv.step !== ORDER_STEPS.CONFIRMED) return `هل تزال مهتماً بـ *${conv.productName}*؟\nأرسل "سعر ${conv.productName}" أو "عايز ${conv.productName}"`;

    saveInquiry(fromNumber, message, null, message, 'low');
    return null;
}

// ── Helper: save inquiry ──────────────────────────────────────────
function saveInquiry(fromNumber, message, productId, inquiryMsg, priority) {
    const db = getDb();
    if (!db) return;
    // Find or create customer
    db.get('SELECT id FROM customers WHERE whatsapp = ?', [fromNumber], (err, row) => {
        if (err) { db.close(); return; }
        const customerId = row ? row.id : null;
        db.run(
            'INSERT INTO inquiries (customer_id, source, message, product_id, status, priority) VALUES (?, ?, ?, ?, ?, ?)',
            [customerId, 'whatsapp', inquiryMsg, productId, 'pending', priority],
            () => db.close()
        );
    });
}

// ── Helper: save confirmed order ──────────────────────────────────
function saveOrderToDB(conv, fromNumber, originalMessage) {
    const db = getDb();
    if (!db) return;

    // Find or create customer
    db.get('SELECT id FROM customers WHERE whatsapp = ?', [fromNumber], (err, row) => {
        if (err) { db.close(); return; }
        let customerId = row ? row.id : null;

        if (!customerId) {
            // Create new customer
            const name = conv.customerName || fromNumber;
            db.run(
                'INSERT INTO customers (name, whatsapp, phone) VALUES (?, ?, ?)',
                [name, fromNumber, fromNumber],
                function() {
                    customerId = this.lastID;
                    createInquiryAndSale(db, customerId, conv, fromNumber);
                }
            );
        } else {
            createInquiryAndSale(db, customerId, conv, fromNumber);
        }
    });
}

function createInquiryAndSale(db, customerId, conv, fromNumber) {
    const productPrice = conv.productPrice || 0;
    const totalAmount = productPrice * conv.quantity;

    const inquiryMsg = `🛒 *طلب واتساب جديد*\n\nالعميل: ${fromNumber}\nالمنتج: ${conv.productName}\nالكمية: ${conv.quantity}\nسعر القطعة: ${productPrice} ج.م\nالإجمالي: ${totalAmount} ج.م\nطريقة الدفع: ${conv.paymentMethod || 'غير محدد'}\n\n📝 الرسالة الأصلية: ${conv.lastMessage || ''}`;

    db.run(
        'INSERT INTO inquiries (customer_id, source, message, product_id, status, priority) VALUES (?, ?, ?, ?, ?, ?)',
        [customerId, 'whatsapp', inquiryMsg, conv.productId, 'pending', 'high'],
        (err) => {
            if (err) { db.close(); return; }
            db.close();
        }
    );
}

function initClient() {
    if (client) { try { client.destroy(); } catch {} client = null; }
    connecting = true;
    connected = false;

    const browsers = [
        process.env.PUPPETEER_EXECUTABLE_PATH,
        require('puppeteer').executablePath(),
        'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        process.env.LOCALAPPDATA + '\\Google\\Chrome\\Application\\chrome.exe',
        process.env.PROGRAMFILES + '\\Google\\Chrome\\Application\\chrome.exe',
        (process.env['PROGRAMFILES(X86)'] || 'C:\\Program Files (x86)') + '\\Google\\Chrome\\Application\\chrome.exe',
        '/data/data/com.termux/files/usr/bin/chromium',
        '/data/data/com.termux/files/usr/bin/chromium-browser',
        '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome', '/snap/bin/chromium',
    ].filter(Boolean);

    let browserPath = null;
    for (const bp of browsers) { try { if (fs.existsSync(bp)) { browserPath = bp; break; } } catch {} }

    const opts = {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--no-first-run', '--no-zygote', '--disable-gpu', '--window-size=800,600'],
    };
    if (browserPath) opts.executablePath = browserPath;

    client = new Client({
        authStrategy: new LocalAuth({ dataPath: process.env.WWEBJS_AUTH_PATH || path.join(__dirname, '.wwebjs_auth') }),
        puppeteer: opts,
    });

    client.on('qr', async qr => {
        currentQr = qr;
        try { lastQr = await qrcode.toDataURL(qr); } catch {}
        connected = false;
        reconnectAttempts = 0;
        console.log('QR Code received, scan with WhatsApp!');
    });

    client.on('authenticated', () => {
        console.log('WhatsApp authenticated!');
        reconnectAttempts = 0;
    });

    client.on('ready', () => {
        connected = true; connecting = false;
        phone = (client.info && client.info.wid && client.info.wid.user) || '';
        currentQr = '';
        refreshProducts();
        reconnectAttempts = 0;
        console.log('WhatsApp connected: ' + phone);
    });

    client.on('auth_failure', msg => {
        console.error('Auth failure:', msg);
        connected = false; connecting = false; phone = '';
        scheduleReconnect();
    });

    client.on('disconnected', reason => {
        console.log('WhatsApp disconnected:', reason);
        connected = false; connecting = false; phone = ''; currentQr = '';
        scheduleReconnect();
    });

    client.on('message', async msg => {
        if (msg.from === 'status@broadcast' || msg.isGroup) return;
        try {
            const contact = await msg.getContact();
            const name = contact.pushname || contact.name || msg.from;
            const number = msg.from.replace('@c.us', '');

            const db = getDb();
            if (db) {
                db.get('SELECT id FROM customers WHERE whatsapp = ?', [number], (err, row) => {
                    if (err) { db.close(); return; }
                    if (!row) db.run('INSERT INTO customers (name, whatsapp, phone) VALUES (?, ?, ?)', [name || number, number, number], () => db.close());
                    else db.close();
                });
            }

            if (!conversations[number]) conversations[number] = {};
            conversations[number].customerName = name;
            conversations[number].lastMessage = msg.body;
            conversations[number].timestamp = Date.now();
            const result = await getAutoReply(msg.body, number);
            if (result) setTimeout(() => { try { client.sendMessage(msg.from, result); } catch {} }, 1500);

            const matched = matchProduct(msg.body, productsCache);
            if (matched) {
                const imgPath = getProductImagePath(matched);
                if (imgPath) setTimeout(() => { try { client.sendMessage(msg.from, MessageMedia.fromFilePath(imgPath)); } catch {} }, 2500);
            }
        } catch (e) { console.error('Message handler error:', e.message); }
    });

    client.initialize().catch(err => {
        console.error('Client init error:', err);
        connected = false; connecting = false;
        scheduleReconnect();
    });
}

function scheduleReconnect() {
    const delay = Math.min(5000 * Math.pow(2, reconnectAttempts), MAX_RECONNECT_DELAY);
    reconnectAttempts++;
    console.log(`Reconnecting in ${Math.round(delay / 1000)}s (attempt ${reconnectAttempts})`);
    setTimeout(() => {
        if (!connected) initClient();
    }, delay);
}

app.get('/api/ping', (req, res) => res.json({ ok: true }));

app.get('/api/status', (req, res) => {
    res.json({ connected, connecting, qr: !!currentQr, phone, qrDataUrl: lastQr || null, products: productsCache.length });
});

app.post('/api/replies', (req, res) => {
    const { replies, welcome } = req.body;
    if (replies) autoReplies = replies;
    if (welcome !== undefined) welcomeMessage = welcome;
    console.log('Auto-replies updated:', Object.keys(autoReplies).length, 'keywords');
    res.json({ success: true });
});

app.post('/api/send', (req, res) => {
    if (!client || !connected) return res.json({ success: false, error: 'Not connected' });
    const chatId = req.body.to.includes('@c.us') ? req.body.to : `${req.body.to}@c.us`;
    client.sendMessage(chatId, req.body.message).then(() => res.json({ success: true })).catch(e => res.json({ success: false, error: e.message }));
});

app.get('/api/qr', (req, res) => res.json({ qr: lastQr || null }));

app.get('/api/products', async (req, res) => { await refreshProducts(); res.json(productsCache); });

app.get('/api/conversations', (req, res) => {
    const active = {};
    for (const [num, data] of Object.entries(conversations)) {
        if (Date.now() - (data.timestamp || 0) < 86400000) active[num] = data;
    }
    res.json(active);
});

app.get('/api/interests', (req, res) => res.json(customerInterests));

const PORT = parseInt(process.env.PORT || '3000');
app.listen(PORT, () => {
    console.log(`WhatsApp server running on http://localhost:${PORT}`);
    refreshProducts().then(() => {
        console.log(`Loaded ${productsCache.length} products from DB`);
        initClient();
    });
});
