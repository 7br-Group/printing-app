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

const DB_PATH = path.join(__dirname, '..', 'printing_app.db');

function getDb() {
    try {
        const sqlite3 = require('sqlite3');
        return new sqlite3.Database(DB_PATH);
    } catch {
        return null;
    }
}

function saveInquiryToDb(customerName, message, phoneNum) {
    const db = getDb();
    if (!db) return;
    db.run(
        `INSERT INTO inquiries (customer_id, source, message, status, priority)
         VALUES (NULL, 'whatsapp', ?, 'pending', 'medium')`,
        [`${customerName}: ${message}`],
        (err) => {
            if (err) console.error('DB error:', err);
            db.close();
        }
    );
}

function ensureCustomerExists(phoneNum, name) {
    const db = getDb();
    if (!db) return null;
    db.get('SELECT id FROM customers WHERE whatsapp = ?', [phoneNum], (err, row) => {
        if (err) { db.close(); return; }
        if (!row) {
            db.run(
                `INSERT INTO customers (name, whatsapp, phone) VALUES (?, ?, ?)`,
                [name || phoneNum, phoneNum, phoneNum],
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

function getAutoReply(message) {
    const lower = message.toLowerCase();
    for (const [keyword, reply] of Object.entries(autoReplies)) {
        if (lower.includes(keyword.toLowerCase())) {
            return reply;
        }
    }
    return null;
}

function initClient() {
    const sessionPath = path.join(__dirname, '.wwebjs_auth');
    if (fs.existsSync(sessionPath)) {
        fs.rmSync(sessionPath, { recursive: true, force: true });
    }

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

        ensureCustomerExists(number, name);
        saveInquiryToDb(name, msg.body, number);

        if (welcomeMessage && !msg._data.isForwarded) {
            const chat = await msg.getChat();
            const messages = await chat.fetchMessages({ limit: 2 });
            if (messages.length <= 1) {
                setTimeout(() => {
                    client.sendMessage(msg.from, welcomeMessage);
                }, 1000);
            }
        }

        const reply = getAutoReply(msg.body);
        if (reply) {
            setTimeout(() => {
                client.sendMessage(msg.from, reply);
            }, 1500);
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
        qrDataUrl: lastQr || null
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

const PORT = 3000;
app.listen(PORT, () => {
    console.log(`WhatsApp server running on http://localhost:${PORT}`);
    initClient();
});
