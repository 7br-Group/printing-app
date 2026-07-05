import os, sys, json, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from database.db_manager import DatabaseManager
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'printing-app-secret-key-change-in-production')
app.config['RTL'] = True

WA_SERVER = os.environ.get('WA_SERVER', 'http://localhost:3000')

def get_db():
    db_path = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(__file__), '..', 'printing_app.db'))
    return DatabaseManager(db_path)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == 'admin':
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        return render_template('login.html', error='كلمة المرور خطأ')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    db = get_db()
    stats = db.get_dashboard_stats()
    low_stock = db.get_low_stock_products()
    db.close()
    return render_template('dashboard.html', stats=stats, low_stock=low_stock)

@app.route('/products')
@login_required
def products():
    db = get_db()
    products = db.get_products()
    categories = db.get_categories()
    db.close()
    return render_template('products.html', products=products, categories=categories)

@app.route('/api/products', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def api_products():
    db = get_db()
    try:
        if request.method == 'GET':
            search = request.args.get('search', '')
            cat_id = request.args.get('category_id', type=int)
            products = db.get_products(search=search, category_id=cat_id)
            return jsonify([dict(p) for p in products])
        elif request.method == 'POST':
            pid = db.add_product(request.json)
            return jsonify({'id': pid, 'success': True})
        elif request.method == 'PUT':
            data = request.json
            db.update_product(data['id'], data)
            return jsonify({'success': True})
        elif request.method == 'DELETE':
            db.delete_product(request.args.get('id', type=int))
            return jsonify({'success': True})
    finally:
        db.close()

@app.route('/customers')
@login_required
def customers():
    return render_template('customers.html')

@app.route('/api/customers', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def api_customers():
    db = get_db()
    try:
        if request.method == 'GET':
            search = request.args.get('search', '')
            customers = db.get_customers(search=search)
            return jsonify([dict(c) for c in customers])
        elif request.method == 'POST':
            cid = db.add_customer(request.json)
            return jsonify({'id': cid, 'success': True})
        elif request.method == 'PUT':
            data = request.json
            db.conn.execute(
                "UPDATE customers SET name=?, phone=?, whatsapp=?, email=?, facebook_id=?, address=?, notes=? WHERE id=?",
                (data['name'], data.get('phone',''), data.get('whatsapp',''), data.get('email',''),
                 data.get('facebook_id',''), data.get('address',''), data.get('notes',''), data['id'])
            )
            db.conn.commit()
            return jsonify({'success': True})
        elif request.method == 'DELETE':
            db.conn.execute("DELETE FROM customers WHERE id = ?", (request.args.get('id', type=int),))
            db.conn.commit()
            return jsonify({'success': True})
    finally:
        db.close()

@app.route('/inquiries')
@login_required
def inquiries():
    return render_template('inquiries.html')

@app.route('/api/inquiries', methods=['GET', 'POST'])
@login_required
def api_inquiries():
    db = get_db()
    try:
        if request.method == 'GET':
            inquiries = db.get_inquiries(status=request.args.get('status'), source=request.args.get('source'))
            return jsonify([dict(i) for i in inquiries])
        elif request.method == 'POST':
            data = request.json
            if data.get('action') == 'reply':
                db.reply_to_inquiry(data['id'], data['response'])
            elif data.get('action') == 'close':
                db.close_inquiry(data['id'])
            elif data.get('action') == 'create':
                db.add_inquiry(data)
            return jsonify({'success': True})
    finally:
        db.close()

@app.route('/sales')
@login_required
def sales():
    db = get_db()
    try:
        from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        to_date = datetime.now().strftime('%Y-%m-%d')
        products = db.get_products()
        customers = db.get_customers()
        return render_template('sales.html', products=products, customers=customers)
    finally:
        db.close()

@app.route('/api/sales', methods=['GET', 'POST'])
@login_required
def api_sales():
    db = get_db()
    try:
        if request.method == 'GET':
            sales = db.get_sales(date_from=request.args.get('from'), date_to=request.args.get('to'))
            return jsonify([dict(s) for s in sales])
        elif request.method == 'POST':
            data = request.json
            sid = db.add_sale(customer_id=data.get('customer_id'), items=data['items'],
                              discount=data.get('discount', 0), tax=data.get('tax', 0))
            return jsonify({'id': sid, 'success': True})
    finally:
        db.close()

@app.route('/inventory')
@login_required
def inventory():
    db = get_db()
    try:
        products = db.get_products()
        movements = db.get_stock_movements()
        categories = db.get_categories()
        return render_template('inventory.html', products=products, movements=movements, categories=categories)
    finally:
        db.close()

@app.route('/api/inventory', methods=['POST'])
@login_required
def api_inventory():
    db = get_db()
    try:
        data = request.json
        if data.get('action') == 'adjust':
            db.update_stock(data['product_id'], data['change'], data['movement_type'], notes=data.get('notes', ''))
        elif data.get('action') == 'add_category':
            db.add_category(data['name'], data.get('description', ''))
        elif data.get('action') == 'delete_category':
            db.delete_category(data['id'])
        return jsonify({'success': True})
    finally:
        db.close()

@app.route('/api/inventory/movements')
@login_required
def api_movements():
    db = get_db()
    try:
        movements = db.get_stock_movements()
        return jsonify([dict(m) for m in movements])
    finally:
        db.close()

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def api_settings():
    db = get_db()
    try:
        if request.method == 'GET':
            keys = ['company_name', 'company_phone', 'company_whatsapp', 'auto_welcome', 'auto_replies']
            return jsonify({k: db.get_setting(k, '') for k in keys})
        elif request.method == 'POST':
            for key, value in request.json.items():
                db.set_setting(key, value)
            return jsonify({'success': True})
    finally:
        db.close()

@app.route('/api/whatsapp/status')
@login_required
def whatsapp_status():
    try:
        resp = requests.get(f"{WA_SERVER}/api/status", timeout=3)
        return jsonify(resp.json())
    except requests.ConnectTimeout:
        return jsonify({'connected': False, 'connecting': False, 'qr': False, 'phone': '', 'error': 'timeout'})
    except requests.ConnectionError:
        return jsonify({'connected': False, 'connecting': False, 'qr': False, 'phone': '', 'error': 'offline'})
    except:
        return jsonify({'connected': False, 'connecting': False, 'qr': False, 'phone': '', 'error': 'unknown'})

@app.route('/api/whatsapp/replies', methods=['POST'])
@login_required
def whatsapp_replies():
    try:
        data = request.json
        requests.post(f"{WA_SERVER}/api/replies", json=data, timeout=2)
        db = get_db()
        db.set_setting('auto_welcome', data.get('welcome', ''))
        db.set_setting('auto_replies', json.dumps(data.get('replies', {}), ensure_ascii=False))
        db.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/whatsapp/send', methods=['POST'])
@login_required
def whatsapp_send():
    try:
        resp = requests.post(f"{WA_SERVER}/api/send", json=request.json, timeout=5)
        return jsonify(resp.json())
    except requests.ConnectionError:
        return jsonify({'success': False, 'error': 'سيرفر واتساب غير متصل'})
    except:
        return jsonify({'success': False, 'error': 'فشل الإرسال'})

@app.route('/api/whatsapp/products')
@login_required
def whatsapp_products():
    try:
        resp = requests.get(f"{WA_SERVER}/api/products", timeout=3)
        return jsonify(resp.json())
    except:
        return jsonify([])

@app.route('/api/whatsapp/conversations')
@login_required
def whatsapp_conversations():
    try:
        resp = requests.get(f"{WA_SERVER}/api/conversations", timeout=3)
        return jsonify(resp.json())
    except:
        return jsonify({})

@app.route('/api/whatsapp/interests')
@login_required
def whatsapp_interests():
    try:
        resp = requests.get(f"{WA_SERVER}/api/interests", timeout=3)
        return jsonify(resp.json())
    except:
        return jsonify({})

@app.route('/api/stats')
@login_required
def api_stats():
    db = get_db()
    try:
        return jsonify(db.get_dashboard_stats())
    finally:
        db.close()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
