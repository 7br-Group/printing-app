const express = require('express');
const { Client, LocalAuth } = require('whatsapp-web.js');
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

// Conversation memory: { phoneNumber: { productId, productName, step, lastMessage } }
const conversations = {};

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
        db.all('SELECT id, name, description, price, quantity FROM products WHERE is_active = 1', (err, rows) => {
            if (!err) productsCache = rows || [];
            db.close();
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
    const available = product.quantity > 0 ? `متوفر (${product.quantity} قطعة)` : 'غير متوفر حالياً';
    return `${prefix}*${product.name}*\n💰 السعر: ${price}\n📦 الحالة: ${available}`;
}

async function getAutoReply(message, fromNumber) {
    const normalized = normalizeArabic(message);

    // 1. Check greeting
    if (isGreeting(message) && welcomeMessage) {
        return welcomeMessage;
    }

    // 2. Refresh products from DB
    await refreshProducts();

    // 3. Try to match a product
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

        // Check if this is a buying intent
        if (hasBuyingIntent(message)) {
            // Customer wants to buy - save as high-priority inquiry
            const db = getDb();
            if (db) {
                const inquiryMsg = `🛒 *طلب شراء*\nالعميل: ${fromNumber}\nالمنتج: ${matchedProduct.name}\nالرسالة: ${message}`;
                db.run(
                    `INSERT INTO inquiries (customer_id, source, message, product_id, status, priority)
                     VALUES (NULL, 'whatsapp', ?, ?, 'pending', 'high')`,
                    [inquiryMsg, matchedProduct.id]
                );
                db.close();
            }
            return `${formatProductReply(matchedProduct, '✅ ')}\n\nهل تريد تأكيد الطلب؟\nأرسل "تأكيد" أو "أكيد"`;
        }

        // It's a price inquiry or info request
        if (isInquiry(message) || true) {
            let reply = formatProductReply(matchedProduct, '');
            if (matchedProduct.description) {
                reply += `\n📝 ${matchedProduct.description}`;
            }
            reply += `\n\nهل تريد شراء هذا المنتج؟ أرسل "عايز ${matchedProduct.name}"`;

            // Create a normal inquiry in DB
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
    }

    // 4. Try keyword-based auto-reply (with synonym support)
    const keywordReply = matchKeyword(message);
    if (keywordReply) {
        return keywordReply;
    }

    // 5. Generic inquiry - save to DB
    const db = getDb();
    if (db) {
        db.run(
            `INSERT INTO inquiries (customer_id, source, message, status, priority)
             VALUES (NULL, 'whatsapp', ?, 'pending', 'low')`,
            [message]
        );
        db.close();
    }

    // 6. Check conversation memory for follow-up
    const conv = conversations[fromNumber];
    if (conv && conv.productId) {
        return `هل تزال مهتماً بـ *${conv.productName}*؟\nأرسل "سعر ${conv.productName}" أو "عايز ${conv.productName}"`;
    }

    // 7. Default reply
    return null;
}

function initClient() {
    client = new Client({
        authStrategy: new LocalAuth({ dataPath: path.join(__dirname, '.wwebjs_auth') }),
        puppeteer: {
            headless: true,
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-accelerated-2d-canvas', '--no-first-run', '--no-zygote', '--single-process', '--disable-gpu']
        }
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
        const reply = await getAutoReply(msg.body, number);
        if (reply) {
            setTimeout(() => {
                client.sendMessage(msg.from, reply);
            }, 1500);
        }
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
