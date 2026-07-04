import sqlite3
import os
import sys
from datetime import datetime, timedelta


class DatabaseManager:
    def __init__(self, db_path=None):
        if db_path is None:
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, "printing_app.db")
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category_id INTEGER,
                sku TEXT UNIQUE,
                description TEXT,
                price REAL DEFAULT 0,
                cost_price REAL DEFAULT 0,
                quantity INTEGER DEFAULT 0,
                min_quantity INTEGER DEFAULT 5,
                color TEXT,
                size TEXT,
                image_path TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            );

            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                whatsapp TEXT,
                facebook_id TEXT,
                address TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS inquiries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                source TEXT CHECK(source IN ('whatsapp', 'facebook', 'phone', 'email', 'other')),
                message TEXT,
                response TEXT,
                product_id INTEGER,
                status TEXT CHECK(status IN ('pending', 'replied', 'closed')) DEFAULT 'pending',
                priority TEXT CHECK(priority IN ('low', 'medium', 'high')) DEFAULT 'medium',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                replied_at TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                invoice_number TEXT UNIQUE,
                total_amount REAL DEFAULT 0,
                discount REAL DEFAULT 0,
                tax REAL DEFAULT 0,
                final_amount REAL DEFAULT 0,
                payment_method TEXT DEFAULT 'cash',
                status TEXT CHECK(status IN ('pending', 'completed', 'cancelled')) DEFAULT 'completed',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER,
                product_id INTEGER,
                quantity INTEGER DEFAULT 1,
                unit_price REAL DEFAULT 0,
                total_price REAL DEFAULT 0,
                FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                movement_type CHECK(movement_type IN ('in', 'out', 'adjustment')),
                quantity INTEGER,
                reference TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()

    # ===== Categories =====
    def add_category(self, name, description=""):
        try:
            self.conn.execute(
                "INSERT INTO categories (name, description) VALUES (?, ?)",
                (name, description),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_categories(self):
        return self.conn.execute("SELECT * FROM categories ORDER BY name").fetchall()

    def delete_category(self, cat_id):
        self.conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        self.conn.commit()

    # ===== Products =====
    def add_product(self, data):
        cursor = self.conn.execute(
            """INSERT INTO products 
               (name, category_id, sku, description, price, cost_price, 
                quantity, min_quantity, color, size, image_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["name"], data.get("category_id"), data.get("sku"),
                data.get("description", ""), data.get("price", 0),
                data.get("cost_price", 0), data.get("quantity", 0),
                data.get("min_quantity", 5), data.get("color", ""),
                data.get("size", ""), data.get("image_path", ""),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_product(self, product_id, data):
        self.conn.execute(
            """UPDATE products SET 
               name=?, category_id=?, sku=?, description=?, price=?, 
               cost_price=?, quantity=?, min_quantity=?, color=?, size=?,
               image_path=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (
                data["name"], data.get("category_id"), data.get("sku"),
                data.get("description", ""), data.get("price", 0),
                data.get("cost_price", 0), data.get("quantity", 0),
                data.get("min_quantity", 5), data.get("color", ""),
                data.get("size", ""), data.get("image_path", ""),
                product_id,
            ),
        )
        self.conn.commit()

    def delete_product(self, product_id):
        self.conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        self.conn.commit()

    def get_products(self, search="", category_id=None):
        query = """
            SELECT p.*, c.name as category_name 
            FROM products p 
            LEFT JOIN categories c ON p.category_id = c.id 
            WHERE p.is_active = 1
        """
        params = []
        if search:
            query += " AND (p.name LIKE ? OR p.sku LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        if category_id:
            query += " AND p.category_id = ?"
            params.append(category_id)
        query += " ORDER BY p.name"
        return self.conn.execute(query, params).fetchall()

    def get_product_by_id(self, product_id):
        return self.conn.execute(
            """SELECT p.*, c.name as category_name 
               FROM products p 
               LEFT JOIN categories c ON p.category_id = c.id 
               WHERE p.id = ?""",
            (product_id,),
        ).fetchone()

    def get_low_stock_products(self):
        return self.conn.execute(
            """SELECT p.*, c.name as category_name 
               FROM products p 
               LEFT JOIN categories c ON p.category_id = c.id 
               WHERE p.is_active = 1 AND p.quantity <= p.min_quantity 
               ORDER BY p.quantity ASC"""
        ).fetchall()

    def update_stock(self, product_id, quantity_change, movement_type, reference="", notes=""):
        product = self.get_product_by_id(product_id)
        if not product:
            return False
        new_qty = product["quantity"] + quantity_change
        if new_qty < 0:
            return False
        self.conn.execute(
            "UPDATE products SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_qty, product_id),
        )
        self.conn.execute(
            """INSERT INTO stock_movements 
               (product_id, movement_type, quantity, reference, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (product_id, movement_type, abs(quantity_change), reference, notes),
        )
        self.conn.commit()
        return True

    # ===== Customers =====
    def add_customer(self, data):
        cursor = self.conn.execute(
            """INSERT INTO customers (name, phone, email, whatsapp, facebook_id, address, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data["name"], data.get("phone", ""), data.get("email", ""),
                data.get("whatsapp", ""), data.get("facebook_id", ""),
                data.get("address", ""), data.get("notes", ""),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_customers(self, search=""):
        query = "SELECT * FROM customers"
        params = []
        if search:
            query += " WHERE name LIKE ? OR phone LIKE ? OR whatsapp LIKE ?"
            params.extend([f"%{search}%"] * 3)
        query += " ORDER BY name"
        return self.conn.execute(query, params).fetchall()

    def get_customer_by_id(self, customer_id):
        return self.conn.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()

    # ===== Inquiries =====
    def add_inquiry(self, data):
        cursor = self.conn.execute(
            """INSERT INTO inquiries 
               (customer_id, source, message, product_id, priority)
               VALUES (?, ?, ?, ?, ?)""",
            (
                data.get("customer_id"), data.get("source", "other"),
                data.get("message", ""), data.get("product_id"),
                data.get("priority", "medium"),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_inquiries(self, status=None, source=None):
        query = """
            SELECT i.*, c.name as customer_name, c.phone as customer_phone,
                   p.name as product_name
            FROM inquiries i 
            LEFT JOIN customers c ON i.customer_id = c.id
            LEFT JOIN products p ON i.product_id = p.id
            WHERE 1=1
        """
        params = []
        if status:
            query += " AND i.status = ?"
            params.append(status)
        if source:
            query += " AND i.source = ?"
            params.append(source)
        query += " ORDER BY i.created_at DESC"
        return self.conn.execute(query, params).fetchall()

    def reply_to_inquiry(self, inquiry_id, response):
        self.conn.execute(
            """UPDATE inquiries 
               SET response = ?, status = 'replied', replied_at = CURRENT_TIMESTAMP 
               WHERE id = ?""",
            (response, inquiry_id),
        )
        self.conn.commit()

    def close_inquiry(self, inquiry_id):
        self.conn.execute(
            "UPDATE inquiries SET status = 'closed' WHERE id = ?", (inquiry_id,)
        )
        self.conn.commit()

    # ===== Sales =====
    def add_sale(self, customer_id, items, discount=0, tax=0, payment_method="cash", notes=""):
        total = sum(item["quantity"] * item["unit_price"] for item in items)
        final = total - discount + tax
        invoice = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        cursor = self.conn.execute(
            """INSERT INTO sales 
               (customer_id, invoice_number, total_amount, discount, tax, 
                final_amount, payment_method, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (customer_id, invoice, total, discount, tax, final, payment_method, notes),
        )
        sale_id = cursor.lastrowid

        for item in items:
            self.conn.execute(
                """INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, total_price)
                   VALUES (?, ?, ?, ?, ?)""",
                (sale_id, item["product_id"], item["quantity"],
                 item["unit_price"], item["quantity"] * item["unit_price"]),
            )
            self.update_stock(
                item["product_id"], -item["quantity"], "out",
                reference=invoice, notes=f"Sale {invoice}",
            )

        self.conn.commit()
        return sale_id

    def get_sales(self, date_from=None, date_to=None):
        query = """
            SELECT s.*, c.name as customer_name
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            WHERE s.status = 'completed'
        """
        params = []
        if date_from:
            query += " AND DATE(s.created_at) >= ?"
            params.append(date_from)
        if date_to:
            query += " AND DATE(s.created_at) <= ?"
            params.append(date_to)
        query += " ORDER BY s.created_at DESC"
        return self.conn.execute(query, params).fetchall()

    def get_sale_items(self, sale_id):
        return self.conn.execute(
            """SELECT si.*, p.name as product_name
               FROM sale_items si
               LEFT JOIN products p ON si.product_id = p.id
               WHERE si.sale_id = ?""",
            (sale_id,),
        ).fetchall()

    def get_sales_summary(self, days=30):
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        row = self.conn.execute(
            """SELECT COUNT(*) as total_sales, 
                      COALESCE(SUM(final_amount), 0) as total_revenue,
                      COALESCE(AVG(final_amount), 0) as avg_sale
               FROM sales 
               WHERE status = 'completed' AND DATE(created_at) >= ?""",
            (date_from,),
        ).fetchone()
        return dict(row)

    # ===== Stock Movements =====
    def get_stock_movements(self, product_id=None, limit=50):
        query = """
            SELECT sm.*, p.name as product_name
            FROM stock_movements sm
            LEFT JOIN products p ON sm.product_id = p.id
            WHERE 1=1
        """
        params = []
        if product_id:
            query += " AND sm.product_id = ?"
            params.append(product_id)
        query += " ORDER BY sm.created_at DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(query, params).fetchall()

    # ===== Settings =====
    def get_setting(self, key, default=None):
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key, value):
        self.conn.execute(
            """INSERT OR REPLACE INTO settings (key, value, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)""",
            (key, value),
        )
        self.conn.commit()

    # ===== Dashboard Stats =====
    def get_dashboard_stats(self):
        stats = {}
        stats["total_products"] = self.conn.execute(
            "SELECT COUNT(*) FROM products WHERE is_active = 1"
        ).fetchone()[0]
        stats["low_stock_count"] = self.conn.execute(
            "SELECT COUNT(*) FROM products WHERE is_active = 1 AND quantity <= min_quantity"
        ).fetchone()[0]
        stats["total_customers"] = self.conn.execute(
            "SELECT COUNT(*) FROM customers"
        ).fetchone()[0]
        stats["pending_inquiries"] = self.conn.execute(
            "SELECT COUNT(*) FROM inquiries WHERE status = 'pending'"
        ).fetchone()[0]
        stats["today_sales"] = self.conn.execute(
            """SELECT COUNT(*) FROM sales 
               WHERE status = 'completed' AND DATE(created_at) = DATE('now')"""
        ).fetchone()[0]
        stats["today_revenue"] = self.conn.execute(
            """SELECT COALESCE(SUM(final_amount), 0) FROM sales 
               WHERE status = 'completed' AND DATE(created_at) = DATE('now')"""
        ).fetchone()[0]
        stats["month_revenue"] = self.conn.execute(
            """SELECT COALESCE(SUM(final_amount), 0) FROM sales 
               WHERE status = 'completed' 
               AND created_at >= DATE('now', 'start of month')"""
        ).fetchone()[0]
        stats["total_stock_value"] = self.conn.execute(
            "SELECT COALESCE(SUM(quantity * price), 0) FROM products WHERE is_active = 1"
        ).fetchone()[0]
        return stats

    def backup_database(self, backup_path):
        import shutil
        self.conn.close()
        shutil.copy2(self.db_path, backup_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        return True

    def restore_database(self, backup_path):
        import shutil
        if not os.path.exists(backup_path):
            return False
        try:
            self.conn.close()
            shutil.copy2(backup_path, self.db_path)
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
            return True
        except:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
            return False
