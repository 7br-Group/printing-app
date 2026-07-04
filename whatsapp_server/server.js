const express = require('express');
const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcode = require('qrcode');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(express.json());

let client = null;
let connected = false;
let phone = '';
let currentQr = '';
let lastQr = '';
let autoReplies = {};
let welcomeMessage = '';

// Conversation memory: { phoneNumber: { productId, productName, step, lastMessage, quantity, paymentMethod } }
const conversations = {};

// Order flow states
const ORDER_STEPS = {
    NONE: 'none',
    AWAITING_QUANTITY: 'awaiting_quantity',
    AWAITING_PAYMENT: 'awaiting_payment',
    CONFIRMED: 'confirmed'
};

// Customer product interest tracking
const customerInterests = {}; // { phoneNumber: { productId, productName, count } }

const DB_PATH = path.join(__dirname, '..', 'printing_app.db');

function getDb() {
    try {
        const sqlite3 = require('sqlite3');
        return new sqlite3.Database(DB_PATH);
    } catch {
        return null;
    }
}

function getProducts() {
    const db = getDb();
    if (!db) return [];
    try {
        const rows = [];
        db.each('SELECT id, name, description, price, quantity FROM products WHERE is_active = 1', (err, row) => {
            if (!err) rows.push(row);
        });
        db.close();
        return rows;
    } catch {
        db.close();
        return [];
    }
}

function getProductsSync() {
    const db = getDb();
    if (!db) return [];
    try {
        const { Database } = require('sqlite3');
        const sql = 'SELECT id, name, description, price, quantity FROM products WHERE is_active = 1';
        return new Promise((resolve, reject) => {
            db.all(sql, (err, rows) => {
                db.close();
                if (err) resolve([]);
                else resolve(rows || []);
            });
        });
    } catch { return []; }
}

let productsCache = [];
let productsLastRefresh = 0;

async function refreshProducts() {
    try {
        const db = getDb();
        if (!db) return;
        await new Promise((resolve) => {
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
    return text
        .replace(/[إأٱآا]/g, 'ا')
        .replace(/[ى]/g, 'ي')
        .replace(/[ؤ]/g, 'و')
        .replace(/[ة]/g, 'ه')
        .replace(/[ئ]/g, 'ي')
        .toLowerCase();
}

function extractNumber(text) {
    const arabicNums = { '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4', '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9' };
    let normalized = text;
    for (const [ar, en] of Object.entries(arabicNums)) {
        normalized = normalized.replace(new RegExp(ar, 'g'), en);
    }
    const matches = normalized.match(/\d+/g);
    return matches ? parseInt(matches[0]) : null;
}

function matchProduct(message, products) {
    if (!products || products.length === 0) return null;
    const normalized = normalizeArabic(message);

    // Try to extract a number from the message
    const requestedNumber = extractNumber(message);

    let bestMatch = null;
    let bestScore = 0;

    for (const product of products) {
        const prodName = normalizeArabic(product.name);
        let score = 0;

        // Check if product name appears in message
        const nameWords = prodName.split(/\s+/);
        for (const word of nameWords) {
            if (word.length > 1 && normalized.includes(word)) {
                score += 10;
            }
        }

        // Check synonyms
        for (const [category, synonyms] of Object.entries(EGYPTIAN_SYNONYMS)) {
            const catNorm = normalizeArabic(category);
            if (normalized.includes(catNorm)) {
                score += 5;
                // Check if any synonym of this category is in the product name
                for (const syn of synonyms) {
                    const synNorm = normalizeArabic(syn);
                    if (prodName.includes(synNorm)) {
                        score += 15;
                        break;
                    }
                }
            } else {
                for (const syn of synonyms) {
                    const synNorm = normalizeArabic(syn);
                    if (normalized.includes(synNorm)) {
                        score += 5;
                        if (prodName.includes(synNorm)) {
                            score += 15;
                            break;
                        }
                    }
                }
            }
        }

        // If there's a number and the product name contains that number, boost score
        if (requestedNumber !== null && prodName.includes(requestedNumber.toString())) {
            score += 50;
        }

        if (score > bestScore) {
            bestScore = score;
            bestMatch = product;
        }
    }

    // Minimum threshold to avoid false positives
    return bestScore >= 10 ? bestMatch : null;
}

function hasBuyingIntent(message) {
    const normalized = normalizeArabic(message);
    for (const kw of BUYING_KEYWORDS) {
        if (normalized.includes(normalizeArabic(kw))) return true;
    }
    return false;
}

function isInquiry(message) {
    const normalized = normalizeArabic(message);
    for (const kw of INQUIRY_KEYWORDS) {
        if (normalized.includes(normalizeArabic(kw))) return true;
    }
    return false;
}

function isGreeting(message) {
    const normalized = normalizeArabic(message);
    for (const kw of GREETING_KEYWORDS) {
        if (normalized.includes(normalizeArabic(kw))) return true;
    }
    return false;
}

function matchKeyword(message) {
    const normalized = normalizeArabic(message);
    for (const [keyword, reply] of Object.entries(autoReplies)) {
        const normKeyword = normalizeArabic(keyword);
        if (normalized.includes(normKeyword)) {
            return reply;
        }
        // Also check synonyms
        for (const [category, synonyms] of Object.entries(EGYPTIAN_SYNONYMS)) {
            if (normKeyword.includes(normalizeArabic(category))) {
                for (const syn of synonyms) {
                    if (normalized.includes(normalizeArabic(syn))) {
                        return reply;
                    }
                }
            }
        }
    }
    return null;
}

function formatProductReply(product, prefix = '') {
    const price = product.price ? `${product.price} ج.م` : 'غير محدد';
    const available = product.quantity > 0 ? 'متوفر' : 'غير متوفر حالياً';
    return `${prefix}*${product.name}*\n💰 السعر: ${price}\n📦 الحالة: ${available}`;
}

function formatProductList(products) {
    if (!products || products.length === 0) return 'لا توجد منتجات متاحة حالياً';
    let reply = '*قائمة المنتجات المتاحة:*\n\n';
    products.forEach((p, i) => {
        reply += `${i+1}. *${p.name}* — ${p.price} ج.م\n`;
    });
    reply += '\nأرسل اسم المنتج لمعرفة سعره\nأو أرسل "عايز (اسم المنتج)" للشراء';
    return reply;
}

function isListProductsRequest(message) {
    const norm = normalizeArabic(message);
    for (const kw of LIST_KEYWORDS) {
        if (norm.includes(normalizeArabic(kw))) return true;
    }
    return false;
}

function detectPaymentMethod(message) {
    const norm = normalizeArabic(message);
    for (const [method, keywords] of Object.entries(PAYMENT_KEYWORDS)) {
        for (const kw of keywords) {
            if (norm.includes(kw)) return method;
        }
    }
    return null;
}

function getProductImagePath(product) {
    if (!product || !product.image_path) return null;
    const imgPath = product.image_path;
    if (fs.existsSync(imgPath)) return imgPath;
    // Try relative to DB_PATH
    const relPath = path.join(path.dirname(DB_PATH), imgPath);
    if (fs.existsSync(relPath)) return relPath;
    return null;
}

async function getAutoReply(message, fromNumber) {
    const normalized = normalizeArabic(message);

    // Check for existing conversation (order flow)
    const conv = conversations[fromNumber];

    // === ORDER FLOW: Awaiting quantity ===
    if (conv && conv.step === ORDER_STEPS.AWAITING_QUANTITY) {
        const qty = extractNumber(message);
        if (qty && qty > 0) {
            conv.quantity = qty;
            conv.step = ORDER_STEPS.AWAITING_PAYMENT;
            return `حضرتك عايز ${qty} قطعة من *${conv.productName}*\n\nإزاي تحب تدفع؟\n1️⃣ كاش\n2️⃣ بطاقة ائتمان\n3️⃣ فودافون كاش\n4️⃣ انستاباي`;
        }
        if (normalized.includes('لا') || normalized.includes('مش') || normalized.includes('الف')) {
            conv.step = ORDER_STEPS.NONE;
            return 'تمام، لو احتجت أي حاجة تاني أنا موجود 🤝';
        }
        return `من فضلك اكتب العدد المطلوب (مثلاً: 5)\nأو أرسل "لا" للإلغاء`;
    }

    // === ORDER FLOW: Awaiting payment ===
    if (conv && conv.step === ORDER_STEPS.AWAITING_PAYMENT) {
        const method = detectPaymentMethod(message);
        if (method) {
            conv.paymentMethod = method;
            conv.step = ORDER_STEPS.CONFIRMED;

            // Save as high-priority inquiry
            const db = getDb();
            if (db) {
                const inquiryMsg = `🛒 *طلب جديد*\nالمنتج: ${conv.productName}\nالكمية: ${conv.quantity}\nطريقة الدفع: ${method}\تيلفون: ${fromNumber}`;
                db.run(
                    `INSERT INTO inquiries (customer_id, source, message, product_id, status, priority)
                     VALUES (NULL, 'whatsapp', ?, ?, 'pending', 'high')`,
                    [inquiryMsg, conv.productId]
                );
                db.close();
            }

            return `✅ *تم تسجيل طلبك!*\n\nالمنتج: *${conv.productName}*\nالكمية: ${conv.quantity}\nطريقة الدفع: ${method}\n\nسنقوم بالتواصل معك قريباً لتأكيد الطلب وشحن المنتج.\nشكراً لتسوقك معنا! 🙏`;
        }
        return `طريقة الدفع غير معروفة. اختر:\n1️⃣ كاش\n2️⃣ بطاقة ائتمان\n3️⃣ فودافون كاش\n4️⃣ انستاباي`;
    }

    // === Greeting ===
    if (isGreeting(message) && welcomeMessage) {
        return welcomeMessage;
    }

    // === Refresh products ===
    await refreshProducts();

    // === Check if asking for product list ===
    if (isListProductsRequest(message)) {
        return formatProductList(productsCache);
    }

    // === Try to match a product ===
    const matchedProduct = matchProduct(message, productsCache);

    if (matchedProduct) {
        // Track this customer's interest
        if (!customerInterests[fromNumber]) {
            customerInterests[fromNumber] = {};
        }
        const interestKey = matchedProduct.id;
        if (!customerInterests[fromNumber][interestKey]) {
            customerInterests[fromNumber][interestKey] = { productId: matchedProduct.id, productName: matchedProduct.name, count: 0 };
        }
        customerInterests[fromNumber][interestKey].count++;

        // Set conversation memory with product
        conversations[fromNumber] = {
            productId: matchedProduct.id,
            productName: matchedProduct.name,
            step: ORDER_STEPS.NONE,
            lastMessage: message,
            timestamp: Date.now()
        };

        // Buying intent
        if (hasBuyingIntent(message)) {
            // Start order flow: ask for quantity
            conversations[fromNumber].step = ORDER_STEPS.AWAITING_QUANTITY;
            let reply = formatProductReply(matchedProduct, '');
            if (matchedProduct.description) {
                reply += `\n📝 ${matchedProduct.description}`;
            }
            reply += `\n\nكم قطعة عايز من *${matchedProduct.name}*؟`;
            return reply;
        }

        // Price inquiry / info request
        let reply = formatProductReply(matchedProduct, '');
        if (matchedProduct.description) {
            reply += `\n📝 ${matchedProduct.description}`;
        }
        reply += `\n\nعايز تشتري؟ أرسل "عايز ${matchedProduct.name}"`;

        // Create inquiry in DB
        const db = getDb();
        if (db) {
            db.run(
                `INSERT INTO inquiries (customer_id, source, message, product_id, status, priority)
                 VALUES (NULL, 'whatsapp', ?, ?, 'pending', 'medium')`,
                [`استفسار عن ${matchedProduct.name}: ${message}`, matchedProduct.id]
            );
            db.close();
        }
        return reply;
    }

    // === Check for order confirmation keywords ===
    if (conv && conv.productId && (normalized.includes('تأكيد') || normalized.includes('أكيد') || normalized.includes('اكيد') || normalized.includes('تم'))) {
        if (conv.step === ORDER_STEPS.CONFIRMED) {
            return 'طلبك مسجل بالفعل! سنتواصل معك قريباً ✅';
        }
        if (conv.step === ORDER_STEPS.NONE) {
            conversations[fromNumber].step = ORDER_STEPS.AWAITING_QUANTITY;
            let reply = `كم قطعة عايز من *${conv.productName}*؟`;
            return reply;
        }
    }

    // === Try keyword-based auto-reply ===
    const keywordReply = matchKeyword(message);
    if (keywordReply) {
        return keywordReply;
    }

    // === Generic inquiry - save to DB ===
    const db = getDb();
    if (db) {
        db.run(
            `INSERT INTO inquiries (customer_id, source, message, status, priority)
             VALUES (NULL, 'whatsapp', ?, 'pending', 'low')`,
            [message]
        );
        db.close();
    }

    // === Follow-up from conversation memory ===
    if (conv && conv.productId && conv.step !== ORDER_STEPS.CONFIRMED) {
        return `هل تزال مهتماً بـ *${conv.productName}*؟\nأرسل "سعر ${conv.productName}" أو "عايز ${conv.productName}"`;
    }

    // === Default reply ===
    return null;
}

function initClient() {
    // Find a working browser
    const possibleBrowsers = [
        'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
        'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        process.env.LOCALAPPDATA + '\\Google\\Chrome\\Application\\chrome.exe',
        process.env.PROGRAMFILES + '\\Google\\Chrome\\Application\\chrome.exe',
        (process.env['PROGRAMFILES(X86)'] || 'C:\\Program Files (x86)') + '\\Google\\Chrome\\Application\\chrome.exe',
    ];
    let browserPath = null;
    try {
        const p = require('puppeteer');
        const defaultPath = p.executablePath();
        if (fs.existsSync(defaultPath)) browserPath = defaultPath;
    } catch {}
    if (!browserPath) {
        for (const bp of possibleBrowsers) {
            try { if (fs.existsSync(bp)) { browserPath = bp; break; } } catch {}
        }
    }

    const launchOptions = {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--no-first-run',
            '--no-zygote',
        ]
    };
    if (browserPath) launchOptions.executablePath = browserPath;

    client = new Client({
        authStrategy: new LocalAuth({ dataPath: path.join(__dirname, '.wwebjs_auth') }),
        puppeteer: launchOptions
    });

    client.on('qr', async (qr) => {
        currentQr = qr;
        try {
            lastQr = await qrcode.toDataURL(qr);
        } catch (e) {
            console.error('QR error:', e);
        }
        connected = false;
        console.log('QR Code received, scan it with WhatsApp!');
    });

    client.on('ready', () => {
        connected = true;
        phone = client.info.wid.user || '';
        currentQr = '';
        refreshProducts();
        console.log(`WhatsApp connected: ${phone}`);
    });

    client.on('authenticated', () => {
        console.log('WhatsApp authenticated!');
    });

    client.on('auth_failure', (msg) => {
        console.error('Auth failure:', msg);
        connected = false;
    });

    client.on('disconnected', (reason) => {
        connected = false;
        phone = '';
        console.log('WhatsApp disconnected:', reason);
    });

    client.on('message', async (msg) => {
        if (msg.from === 'status@broadcast') return;
        if (msg.isGroup) return;

        const contact = await msg.getContact();
        const name = contact.pushname || contact.name || msg.from;
        const number = msg.from.replace('@c.us', '');

        // Save customer to DB
        const db = getDb();
        if (db) {
            db.get('SELECT id FROM customers WHERE whatsapp = ?', [number], (err, row) => {
                if (err) { db.close(); return; }
                if (!row) {
                    db.run(
                        `INSERT INTO customers (name, whatsapp, phone) VALUES (?, ?, ?)`,
                        [name || number, number, number],
                        function(err) {
                            if (err) console.error('Customer insert error:', err);
                            db.close();
                        }
                    );
                } else {
                    db.close();
                }
            });
        }

        // Store conversation memory
        conversations[number] = { lastMessage: msg.body, timestamp: Date.now() };

        // Get smart reply
        const result = await getAutoReply(msg.body, number);
        if (result) {
            setTimeout(() => {
                client.sendMessage(msg.from, result);
            }, 1500);
        }

        // Send product image if one was matched
        const matchedProduct = matchProduct(msg.body, productsCache);
        if (matchedProduct) {
            const imgPath = getProductImagePath(matchedProduct);
            if (imgPath) {
                setTimeout(() => {
                    try {
                        const media = MessageMedia.fromFilePath(imgPath);
                        client.sendMessage(msg.from, media);
                    } catch (e) {
                        console.error('Image send error:', e.message);
                    }
                }, 2500);
            }
        }
    });

    client.initialize().catch(err => {
        console.error('Client init error:', err);
        setTimeout(initClient, 5000);
    });
}

app.get('/api/status', (req, res) => {
    res.json({
        connected: connected,
        qr: currentQr ? true : false,
        phone: phone,
        qrDataUrl: lastQr || null,
        products: productsCache.length
    });
});

app.post('/api/replies', (req, res) => {
    const { replies, welcome } = req.body;
    if (replies) autoReplies = replies;
    if (welcome !== undefined) welcomeMessage = welcome;
    console.log('Auto-replies updated:', Object.keys(autoReplies).length, 'keywords');
    res.json({ success: true });
});

app.post('/api/send', (req, res) => {
    const { to, message } = req.body;
    if (!client || !connected) {
        return res.json({ success: false, error: 'Not connected' });
    }
    const chatId = to.includes('@c.us') ? to : `${to}@c.us`;
    client.sendMessage(chatId, message).then(() => {
        res.json({ success: true });
    }).catch(err => {
        res.json({ success: false, error: err.message });
    });
});

app.get('/api/qr', (req, res) => {
    if (lastQr) {
        res.json({ qr: lastQr });
    } else {
        res.json({ qr: null, message: 'No QR yet' });
    }
});

app.get('/api/products', async (req, res) => {
    await refreshProducts();
    res.json(productsCache);
});

app.get('/api/conversations', (req, res) => {
    const active = {};
    for (const [num, data] of Object.entries(conversations)) {
        if (Date.now() - data.timestamp < 86400000) {
            active[num] = data;
        }
    }
    res.json(active);
});

app.get('/api/interests', (req, res) => {
    res.json(customerInterests);
});

const PORT = 3000;
app.listen(PORT, () => {
    console.log(`WhatsApp server running on http://localhost:${PORT}`);
    refreshProducts().then(() => {
        console.log(`Loaded ${productsCache.length} products from DB`);
        initClient();
    });
});
