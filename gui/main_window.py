import os
import sys
import json
import base64
import requests
from datetime import datetime
from PySide6.QtCore import Qt, QTimer

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGridLayout, QMessageBox, QGroupBox, QDialog,
    QLineEdit, QTextEdit, QComboBox, QSpinBox,
    QDoubleSpinBox, QFormLayout, QDialogButtonBox,
    QFileDialog, QTabWidget, QDateEdit, QSizePolicy,
    QApplication, QInputDialog,
)
from PySide6.QtCore import Qt, QDate, QSize
from PySide6.QtGui import QFont, QIcon, QColor, QPixmap

from database.db_manager import DatabaseManager


# ===========================
# Helper: Load QSS
# ===========================
def load_stylesheet():
    qss_path = os.path.join(os.path.dirname(__file__), "..", "resources", "styles.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


# ===========================
# Customer Dialog
# ===========================
class CustomerDialog(QDialog):
    def __init__(self, db, customer_id=None):
        super().__init__()
        self.db = db
        self.customer_id = customer_id
        self.setWindowTitle("تعديل عميل" if customer_id else "إضافة عميل جديد")
        self.setMinimumWidth(450)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("اسم العميل")
        form.addRow("الاسم *:", self.name_input)

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("رقم الهاتف")
        form.addRow("الهاتف:", self.phone_input)

        self.whatsapp_input = QLineEdit()
        self.whatsapp_input.setPlaceholderText("رقم الواتساب")
        form.addRow("واتساب:", self.whatsapp_input)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("البريد الإلكتروني")
        form.addRow("البريد:", self.email_input)

        self.fb_input = QLineEdit()
        self.fb_input.setPlaceholderText("معرف فيسبوك")
        form.addRow("فيسبوك ID:", self.fb_input)

        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("العنوان")
        form.addRow("العنوان:", self.address_input)

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("ملاحظات")
        self.notes_input.setMaximumHeight(60)
        form.addRow("ملاحظات:", self.notes_input)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        save_btn = QPushButton("💾 حفظ")
        save_btn.setObjectName("successBtn")
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self.save)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("❌ إلغاء")
        cancel_btn.setObjectName("dangerBtn")
        cancel_btn.setMinimumHeight(40)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        if customer_id:
            self.load_customer()

    def load_customer(self):
        c = self.db.get_customer_by_id(self.customer_id)
        if c:
            self.name_input.setText(c["name"])
            self.phone_input.setText(c["phone"] or "")
            self.whatsapp_input.setText(c["whatsapp"] or "")
            self.email_input.setText(c["email"] or "")
            self.fb_input.setText(c["facebook_id"] or "")
            self.address_input.setText(c["address"] or "")
            self.notes_input.setText(c["notes"] or "")

    def save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "تنبيه", "اسم العميل مطلوب")
            return

        data = {
            "name": name,
            "phone": self.phone_input.text().strip(),
            "whatsapp": self.whatsapp_input.text().strip(),
            "email": self.email_input.text().strip(),
            "facebook_id": self.fb_input.text().strip(),
            "address": self.address_input.text().strip(),
            "notes": self.notes_input.toPlainText().strip(),
        }

        if self.customer_id:
            self.db.conn.execute(
                """UPDATE customers SET name=?, phone=?, whatsapp=?, email=?,
                   facebook_id=?, address=?, notes=? WHERE id=?""",
                (data["name"], data["phone"], data["whatsapp"], data["email"],
                 data["facebook_id"], data["address"], data["notes"], self.customer_id),
            )
            self.db.conn.commit()
        else:
            self.db.add_customer(data)
        self.accept()


# ===========================
# Stat Card Widget
# ===========================
class StatCard(QFrame):
    def __init__(self, title, value, icon_text="", color="#3498db"):
        super().__init__()
        self.setProperty("class", "stat-card")
        self.setFixedHeight(120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)

        top_row = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: #7f8c8d; font-size: 13px; font-weight: normal;")
        top_row.addWidget(title_label)

        if icon_text:
            icon_label = QLabel(icon_text)
            icon_label.setStyleSheet(f"color: {color}; font-size: 28px;")
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            top_row.addWidget(icon_label)

        layout.addLayout(top_row)

        self.value_label = QLabel(str(value))
        self.value_label.setStyleSheet(
            f"color: {color}; font-size: 28px; font-weight: bold;"
        )
        layout.addWidget(self.value_label)

    def update_value(self, value):
        self.value_label.setText(str(value))


# ===========================
# Dashboard
# ===========================
class DashboardWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        title = QLabel("لوحة التحكم")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        title.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(title)

        stats_grid = QGridLayout()
        stats_grid.setSpacing(15)

        stats = self.db.get_dashboard_stats()

        self.card_products = StatCard("إجمالي المنتجات", stats["total_products"], "📦", "#3498db")
        self.card_low_stock = StatCard("منتجات منخفضة", stats["low_stock_count"], "⚠️", "#e74c3c")
        self.card_customers = StatCard("العملاء", stats["total_customers"], "👥", "#27ae60")
        self.card_inquiries = StatCard("استفسارات معلقة", stats["pending_inquiries"], "💬", "#f39c12")
        self.card_today_sales = StatCard("مبيعات اليوم", stats["today_sales"], "🛒", "#9b59b6")
        self.card_today_revenue = StatCard("إيراد اليوم", f"{stats['today_revenue']:,.0f} ج.م", "💰", "#27ae60")
        self.card_month_revenue = StatCard("إيراد الشهر", f"{stats['month_revenue']:,.0f} ج.م", "📈", "#3498db")
        self.card_stock_value = StatCard("قيمة المخزون", f"{stats['total_stock_value']:,.0f} ج.م", "🏭", "#e67e22")

        cards = [
            (self.card_products, 0, 0), (self.card_low_stock, 0, 1),
            (self.card_customers, 0, 2), (self.card_inquiries, 0, 3),
            (self.card_today_sales, 1, 0), (self.card_today_revenue, 1, 1),
            (self.card_month_revenue, 1, 2), (self.card_stock_value, 1, 3),
        ]
        for card, row, col in cards:
            stats_grid.addWidget(card, row, col)

        layout.addLayout(stats_grid)

        low_stock_group = QGroupBox("⚠️ منتجات تحتاج إعادة طلب")
        low_stock_layout = QVBoxLayout(low_stock_group)

        self.low_stock_table = QTableWidget()
        self.low_stock_table.setColumnCount(5)
        self.low_stock_table.setHorizontalHeaderLabels(
            ["المنتج", "الفئة", "الكمية الحالية", "الحد الأدنى", "الحالة"]
        )
        self.low_stock_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.low_stock_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.low_stock_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        low_stock_layout.addWidget(self.low_stock_table)

        layout.addWidget(low_stock_group)
        self.load_low_stock()

    def load_low_stock(self):
        products = self.db.get_low_stock_products()
        self.low_stock_table.setRowCount(len(products))
        for i, p in enumerate(products):
            self.low_stock_table.setItem(i, 0, QTableWidgetItem(p["name"]))
            self.low_stock_table.setItem(i, 1, QTableWidgetItem(p["category_name"] or ""))
            self.low_stock_table.setItem(i, 2, QTableWidgetItem(str(p["quantity"])))
            self.low_stock_table.setItem(i, 3, QTableWidgetItem(str(p["min_quantity"])))
            status = "🔴 نقص حاد" if p["quantity"] == 0 else "🟡 منخفض"
            self.low_stock_table.setItem(i, 4, QTableWidgetItem(status))


# ===========================
# Products Management
# ===========================
class ProductsWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QHBoxLayout()
        title = QLabel("إدارة المنتجات")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        header.addWidget(title)
        header.addStretch()

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 بحث عن منتج...")
        self.search_input.setMinimumWidth(250)
        self.search_input.textChanged.connect(self.load_products)
        search_layout.addWidget(self.search_input)

        self.category_filter = QComboBox()
        self.category_filter.addItem("كل الفئات", None)
        self.category_filter.setMinimumWidth(150)
        self.category_filter.currentIndexChanged.connect(self.load_products)
        search_layout.addWidget(self.category_filter)

        header.addLayout(search_layout)
        layout.addLayout(header)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ إضافة منتج جديد")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self.add_product)
        btn_layout.addWidget(add_btn)

        edit_btn = QPushButton("✏️ تعديل")
        edit_btn.setObjectName("warningBtn")
        edit_btn.clicked.connect(self.edit_product)
        btn_layout.addWidget(edit_btn)

        delete_btn = QPushButton("🗑️ حذف")
        delete_btn.setObjectName("dangerBtn")
        delete_btn.clicked.connect(self.delete_product)
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "الاسم", "الفئة", "الكود", "السعر", "التكلفة", "الكمية", "الحد الأدنى"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnHidden(0, True)
        layout.addWidget(self.table)

        self.load_categories()
        self.load_products()

    def load_categories(self):
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("كل الفئات", None)
        for cat in self.db.get_categories():
            self.category_filter.addItem(cat["name"], cat["id"])
        self.category_filter.blockSignals(False)

    def load_products(self):
        search = self.search_input.text()
        cat_id = self.category_filter.currentData()
        products = self.db.get_products(search=search, category_id=cat_id)
        self.table.setRowCount(len(products))
        for i, p in enumerate(products):
            self.table.setItem(i, 0, QTableWidgetItem(str(p["id"])))
            self.table.setItem(i, 1, QTableWidgetItem(p["name"]))
            self.table.setItem(i, 2, QTableWidgetItem(p["category_name"] or ""))
            self.table.setItem(i, 3, QTableWidgetItem(p["sku"] or ""))
            self.table.setItem(i, 4, QTableWidgetItem(f"{p['price']:.2f}"))
            self.table.setItem(i, 5, QTableWidgetItem(f"{p['cost_price']:.2f}"))
            qty_item = QTableWidgetItem(str(p["quantity"]))
            if p["quantity"] <= p["min_quantity"]:
                qty_item.setForeground(QColor("#e74c3c"))
                qty_item.setFont(QFont("", -1, QFont.Weight.Bold))
            self.table.setItem(i, 6, qty_item)
            self.table.setItem(i, 7, QTableWidgetItem(str(p["min_quantity"])))

    def get_selected_id(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return int(self.table.item(rows[0].row(), 0).text())

    def add_product(self):
        dialog = ProductDialog(self.db)
        if dialog.exec():
            self.load_products()

    def edit_product(self):
        product_id = self.get_selected_id()
        if not product_id:
            QMessageBox.warning(self, "تنبيه", "اختر منتج أولاً")
            return
        dialog = ProductDialog(self.db, product_id)
        if dialog.exec():
            self.load_products()

    def delete_product(self):
        product_id = self.get_selected_id()
        if not product_id:
            QMessageBox.warning(self, "تنبيه", "اختر منتج أولاً")
            return
        reply = QMessageBox.question(
            self, "تأكيد", "هل أنت متأكد من حذف هذا المنتج؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_product(product_id)
            self.load_products()


class ProductDialog(QDialog):
    def __init__(self, db, product_id=None):
        super().__init__()
        self.db = db
        self.product_id = product_id
        self.setWindowTitle("تعديل منتج" if product_id else "إضافة منتج جديد")
        self.setMinimumWidth(500)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(12)

        self.name_input = QLineEdit()
        form.addRow("اسم المنتج *:", self.name_input)

        self.category_combo = QComboBox()
        self.category_combo.addItem("-- اختر فئة --", None)
        for cat in self.db.get_categories():
            self.category_combo.addItem(cat["name"], cat["id"])
        form.addRow("الفئة:", self.category_combo)

        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("كود المنتج (اختياري)")
        form.addRow("الكود (SKU):", self.sku_input)

        self.desc_input = QTextEdit()
        self.desc_input.setMaximumHeight(80)
        form.addRow("الوصف:", self.desc_input)

        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 999999)
        self.price_input.setSuffix(" ج.م")
        form.addRow("سعر البيع:", self.price_input)

        self.cost_input = QDoubleSpinBox()
        self.cost_input.setRange(0, 999999)
        self.cost_input.setSuffix(" ج.م")
        form.addRow("سعر التكلفة:", self.cost_input)

        self.qty_input = QSpinBox()
        self.qty_input.setRange(0, 999999)
        form.addRow("الكمية:", self.qty_input)

        self.min_qty_input = QSpinBox()
        self.min_qty_input.setRange(0, 999999)
        self.min_qty_input.setValue(5)
        form.addRow("الحد الأدنى:", self.min_qty_input)

        self.color_input = QLineEdit()
        form.addRow("اللون:", self.color_input)

        self.size_input = QLineEdit()
        form.addRow("المقاس:", self.size_input)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        save_btn = QPushButton("💾 حفظ")
        save_btn.setObjectName("successBtn")
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self.save)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("❌ إلغاء")
        cancel_btn.setObjectName("dangerBtn")
        cancel_btn.setMinimumHeight(40)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        if product_id:
            self.load_product()

    def load_product(self):
        p = self.db.get_product_by_id(self.product_id)
        if p:
            self.name_input.setText(p["name"])
            if p["category_id"]:
                idx = self.category_combo.findData(p["category_id"])
                if idx >= 0:
                    self.category_combo.setCurrentIndex(idx)
            self.sku_input.setText(p["sku"] or "")
            self.desc_input.setText(p["description"] or "")
            self.price_input.setValue(p["price"])
            self.cost_input.setValue(p["cost_price"])
            self.qty_input.setValue(p["quantity"])
            self.min_qty_input.setValue(p["min_quantity"])
            self.color_input.setText(p["color"] or "")
            self.size_input.setText(p["size"] or "")

    def save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "تنبيه", "اسم المنتج مطلوب")
            return

        data = {
            "name": name,
            "category_id": self.category_combo.currentData(),
            "sku": self.sku_input.text().strip(),
            "description": self.desc_input.toPlainText(),
            "price": self.price_input.value(),
            "cost_price": self.cost_input.value(),
            "quantity": self.qty_input.value(),
            "min_quantity": self.min_qty_input.value(),
            "color": self.color_input.text().strip(),
            "size": self.size_input.text().strip(),
        }

        if self.product_id:
            self.db.update_product(self.product_id, data)
        else:
            self.db.add_product(data)
        self.accept()


# ===========================
# Inventory Management
# ===========================
class InventoryWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("تتبع المخزون والجرد")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self.create_stock_tab(), "📦 المخزون")
        tabs.addTab(self.create_movements_tab(), "📋 حركات المخزون")
        tabs.addTab(self.create_categories_tab(), "🏷️ الفئات")
        layout.addWidget(tabs)

    def create_stock_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        btn_layout = QHBoxLayout()
        adjust_btn = QPushButton("📊 تعديل كمية")
        adjust_btn.setObjectName("primaryBtn")
        adjust_btn.clicked.connect(self.adjust_stock)
        btn_layout.addWidget(adjust_btn)

        reorder_btn = QPushButton("🔄 طلب إعادة توريد")
        reorder_btn.setObjectName("successBtn")
        reorder_btn.clicked.connect(self.reorder_stock)
        btn_layout.addWidget(reorder_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.stock_table = QTableWidget()
        self.stock_table.setColumnCount(7)
        self.stock_table.setHorizontalHeaderLabels([
            "ID", "المنتج", "الفئة", "الكمية", "الحد الأدنى", "السعر", "القيمة"
        ])
        self.stock_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stock_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.stock_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.stock_table.setColumnHidden(0, True)
        layout.addWidget(self.stock_table)

        self.load_stock()
        return widget

    def create_movements_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.movements_table = QTableWidget()
        self.movements_table.setColumnCount(6)
        self.movements_table.setHorizontalHeaderLabels([
            "التاريخ", "المنتج", "النوع", "الكمية", "المرجع", "ملاحظات"
        ])
        self.movements_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.movements_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.movements_table)

        self.load_movements()
        return widget

    def create_categories_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        btn_layout = QHBoxLayout()
        add_cat_btn = QPushButton("➕ إضافة فئة")
        add_cat_btn.setObjectName("primaryBtn")
        add_cat_btn.clicked.connect(self.add_category)
        btn_layout.addWidget(add_cat_btn)

        del_cat_btn = QPushButton("🗑️ حذف فئة")
        del_cat_btn.setObjectName("dangerBtn")
        del_cat_btn.clicked.connect(self.delete_category)
        btn_layout.addWidget(del_cat_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.categories_table = QTableWidget()
        self.categories_table.setColumnCount(3)
        self.categories_table.setHorizontalHeaderLabels(["ID", "اسم الفئة", "الوصف"])
        self.categories_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.categories_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.categories_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.categories_table.setColumnHidden(0, True)
        layout.addWidget(self.categories_table)

        self.load_categories()
        return widget

    def load_stock(self):
        products = self.db.get_products()
        self.stock_table.setRowCount(len(products))
        for i, p in enumerate(products):
            self.stock_table.setItem(i, 0, QTableWidgetItem(str(p["id"])))
            self.stock_table.setItem(i, 1, QTableWidgetItem(p["name"]))
            self.stock_table.setItem(i, 2, QTableWidgetItem(p["category_name"] or ""))
            qty = p["quantity"]
            qty_item = QTableWidgetItem(str(qty))
            if qty <= p["min_quantity"]:
                qty_item.setForeground(QColor("#e74c3c"))
                qty_item.setFont(QFont("", -1, QFont.Weight.Bold))
            self.stock_table.setItem(i, 3, qty_item)
            self.stock_table.setItem(i, 4, QTableWidgetItem(str(p["min_quantity"])))
            self.stock_table.setItem(i, 5, QTableWidgetItem(f"{p['price']:.2f}"))
            value = qty * p["price"]
            self.stock_table.setItem(i, 6, QTableWidgetItem(f"{value:,.2f}"))

    def load_movements(self):
        movements = self.db.get_stock_movements()
        self.movements_table.setRowCount(len(movements))
        for i, m in enumerate(movements):
            self.movements_table.setItem(i, 0, QTableWidgetItem(str(m["created_at"])))
            self.movements_table.setItem(i, 1, QTableWidgetItem(m["product_name"] or ""))
            type_map = {"in": "📥 وارد", "out": "📤 صادر", "adjustment": "📊 تعديل"}
            self.movements_table.setItem(i, 2, QTableWidgetItem(type_map.get(m["movement_type"], "")))
            self.movements_table.setItem(i, 3, QTableWidgetItem(str(m["quantity"])))
            self.movements_table.setItem(i, 4, QTableWidgetItem(m["reference"] or ""))
            self.movements_table.setItem(i, 5, QTableWidgetItem(m["notes"] or ""))

    def load_categories(self):
        categories = self.db.get_categories()
        self.categories_table.setRowCount(len(categories))
        for i, c in enumerate(categories):
            self.categories_table.setItem(i, 0, QTableWidgetItem(str(c["id"])))
            self.categories_table.setItem(i, 1, QTableWidgetItem(c["name"]))
            self.categories_table.setItem(i, 2, QTableWidgetItem(c["description"] or ""))

    def adjust_stock(self):
        rows = self.stock_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "تنبيه", "اختر منتج أولاً")
            return
        product_id = int(self.stock_table.item(rows[0].row(), 0).text())
        dialog = StockAdjustDialog(self.db, product_id)
        if dialog.exec():
            self.load_stock()
            self.load_movements()

    def reorder_stock(self):
        low = self.db.get_low_stock_products()
        if not low:
            QMessageBox.information(self, "معلومة", "لا يوجد منتجات منخفضة المخزون حالياً")
            return
        msg = "المنتجات التي تحتاج إعادة طلب:\n\n"
        for p in low:
            msg += f"• {p['name']}: الكمية {p['quantity']} (الحد الأدنى {p['min_quantity']})\n"
        QMessageBox.information(self, "طلب إعادة توريد", msg)

    def add_category(self):
        dialog = CategoryDialog(self.db)
        if dialog.exec():
            self.load_categories()

    def delete_category(self):
        rows = self.categories_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "تنبيه", "اختر فئة أولاً")
            return
        cat_id = int(self.categories_table.item(rows[0].row(), 0).text())
        reply = QMessageBox.question(
            self, "تأكيد", "هل أنت متأكد من حذف هذه الفئة؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_category(cat_id)
            self.load_categories()


class CategoryDialog(QDialog):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("إضافة فئة جديدة")
        self.setMinimumWidth(400)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("اسم الفئة")
        form.addRow("اسم الفئة *:", self.name_input)

        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("وصف الفئة (اختياري)")
        self.desc_input.setMaximumHeight(80)
        form.addRow("الوصف:", self.desc_input)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        save_btn = QPushButton("💾 حفظ")
        save_btn.setObjectName("successBtn")
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self.save)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("❌ إلغاء")
        cancel_btn.setObjectName("dangerBtn")
        cancel_btn.setMinimumHeight(40)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "تنبيه", "اسم الفئة مطلوب")
            return
        if self.db.add_category(name, self.desc_input.toPlainText()):
            self.accept()
        else:
            QMessageBox.warning(self, "تنبيه", "هذه الفئة موجودة بالفعل")


class StockAdjustDialog(QDialog):
    def __init__(self, db, product_id):
        super().__init__()
        self.db = db
        self.product_id = product_id
        self.setWindowTitle("تعديل المخزون")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        product = db.get_product_by_id(product_id)
        layout = QVBoxLayout(self)

        info = QLabel(f"المنتج: {product['name']}\nالكمية الحالية: {product['quantity']}")
        info.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        layout.addWidget(info)

        form = QFormLayout()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["📥 وارد (إضافة)", "📤 صارد (خصم)", "📊 تعديل"])
        form.addRow("نوع الحركة:", self.type_combo)

        self.qty_input = QSpinBox()
        self.qty_input.setRange(1, 999999)
        form.addRow("الكمية:", self.qty_input)

        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("ملاحظات (اختياري)")
        form.addRow("ملاحظات:", self.notes_input)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        save_btn = QPushButton("💾 حفظ")
        save_btn.setObjectName("successBtn")
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self.save)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("❌ إلغاء")
        cancel_btn.setObjectName("dangerBtn")
        cancel_btn.setMinimumHeight(40)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def save(self):
        type_idx = self.type_combo.currentIndex()
        qty = self.qty_input.value()
        notes = self.notes_input.text()

        if type_idx == 0:
            change = qty
            movement_type = "in"
        elif type_idx == 1:
            change = -qty
            movement_type = "out"
        else:
            product = self.db.get_product_by_id(self.product_id)
            new_qty = qty
            change = new_qty - product["quantity"]
            movement_type = "adjustment"

        if self.db.update_stock(self.product_id, change, movement_type, notes=notes):
            self.accept()
        else:
            QMessageBox.warning(self, "خطأ", "فشل في تعديل المخزون")


# ===========================
# Inquiries Management
# ===========================
class InquiriesWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("إدارة الاستفسارات")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        filter_layout = QHBoxLayout()
        self.status_filter = QComboBox()
        self.status_filter.addItems(["الكل", "⏳ معلق", "✅ تم الرد", "🔒 مغلق"])
        self.status_filter.currentIndexChanged.connect(self.load_inquiries)
        filter_layout.addWidget(QLabel("الحالة:"))
        filter_layout.addWidget(self.status_filter)

        self.source_filter = QComboBox()
        self.source_filter.addItems(["الكل", "واتساب", "فيسبوك", "هاتف", "بريد", "أخرى"])
        self.source_filter.currentIndexChanged.connect(self.load_inquiries)
        filter_layout.addWidget(QLabel("المصدر:"))
        filter_layout.addWidget(self.source_filter)

        filter_layout.addStretch()

        add_btn = QPushButton("➕ استفسار جديد")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self.add_inquiry)
        filter_layout.addWidget(add_btn)

        layout.addLayout(filter_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID", "العميل", "رقم الهاتف", "المنتج", "المصدر", "الرسالة", "الأولوية", "الحالة", "التاريخ"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnHidden(0, True)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        reply_btn = QPushButton("💬 رد على الاستفسار")
        reply_btn.setObjectName("successBtn")
        reply_btn.clicked.connect(self.reply_inquiry)
        btn_layout.addWidget(reply_btn)

        close_btn = QPushButton("🔒 إغلاق")
        close_btn.setObjectName("warningBtn")
        close_btn.clicked.connect(self.close_inquiry)
        btn_layout.addWidget(close_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.load_inquiries()

    def load_inquiries(self):
        status_map = {"الكل": None, "⏳ معلق": "pending", "✅ تم الرد": "replied", "🔒 مغلق": "closed"}
        source_map = {"الكل": None, "واتساب": "whatsapp", "فيسبوك": "facebook",
                      "هاتف": "phone", "بريد": "email", "أخرى": "other"}

        status = status_map.get(self.status_filter.currentText())
        source = source_map.get(self.source_filter.currentText())

        inquiries = self.db.get_inquiries(status=status, source=source)
        self.table.setRowCount(len(inquiries))

        source_display = {
            "whatsapp": "واتساب", "facebook": "فيسبوك",
            "phone": "هاتف", "email": "بريد", "other": "أخرى"
        }
        priority_display = {"low": "🟢 منخفضة", "medium": "🟡 متوسطة", "high": "🔴 عالية"}
        status_display = {"pending": "⏳ معلق", "replied": "✅ تم الرد", "closed": "🔒 مغلق"}

        for i, inq in enumerate(inquiries):
            self.table.setItem(i, 0, QTableWidgetItem(str(inq["id"])))
            self.table.setItem(i, 1, QTableWidgetItem(inq["customer_name"] or "غير معروف"))
            self.table.setItem(i, 2, QTableWidgetItem(inq["customer_phone"] or ""))
            self.table.setItem(i, 3, QTableWidgetItem(inq["product_name"] or ""))
            self.table.setItem(i, 4, QTableWidgetItem(source_display.get(inq["source"], "")))
            self.table.setItem(i, 5, QTableWidgetItem(inq["message"] or ""))
            self.table.setItem(i, 6, QTableWidgetItem(priority_display.get(inq["priority"], "")))
            self.table.setItem(i, 7, QTableWidgetItem(status_display.get(inq["status"], "")))
            self.table.setItem(i, 8, QTableWidgetItem(str(inq["created_at"])))

    def get_selected_id(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return int(self.table.item(rows[0].row(), 0).text())

    def add_inquiry(self):
        dialog = InquiryDialog(self.db)
        if dialog.exec():
            self.load_inquiries()

    def reply_inquiry(self):
        inquiry_id = self.get_selected_id()
        if not inquiry_id:
            QMessageBox.warning(self, "تنبيه", "اختر استفسار أولاً")
            return
        dialog = ReplyDialog(self.db, inquiry_id)
        if dialog.exec():
            self.load_inquiries()

    def close_inquiry(self):
        inquiry_id = self.get_selected_id()
        if not inquiry_id:
            QMessageBox.warning(self, "تنبيه", "اختر استفسار أولاً")
            return
        self.db.close_inquiry(inquiry_id)
        self.load_inquiries()


class InquiryDialog(QDialog):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("استفسار جديد")
        self.setMinimumWidth(450)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.customer_combo = QComboBox()
        self.customer_combo.addItem("-- اختر عميل (اختياري) --", None)
        for c in db.get_customers():
            self.customer_combo.addItem(f"{c['name']} - {c['phone'] or ''}", c["id"])
        form.addRow("العميل:", self.customer_combo)

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("رقم الهاتف")
        form.addRow("رقم الهاتف:", self.phone_input)

        self.source_combo = QComboBox()
        self.source_combo.addItems(["واتساب", "فيسبوك", "هاتف", "بريد", "أخرى"])
        form.addRow("المصدر:", self.source_combo)

        self.product_combo = QComboBox()
        self.product_combo.addItem("-- اختر منتج (اختياري) --", None)
        for p in db.get_products():
            self.product_combo.addItem(p["name"], p["id"])
        form.addRow("المنتج:", self.product_combo)

        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("رسالة الاستفسار...")
        form.addRow("الرسالة:", self.message_input)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["متوسطة", "منخفضة", "عالية"])
        form.addRow("الأولوية:", self.priority_combo)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        save_btn = QPushButton("💾 حفظ")
        save_btn.setObjectName("successBtn")
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self.save)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("❌ إلغاء")
        cancel_btn.setObjectName("dangerBtn")
        cancel_btn.setMinimumHeight(40)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def save(self):
        source_map = {"واتساب": "whatsapp", "فيسبوك": "facebook",
                      "هاتف": "phone", "بريد": "email", "أخرى": "other"}
        priority_map = {"منخفضة": "low", "متوسطة": "medium", "عالية": "high"}

        phone = self.phone_input.text().strip()
        msg = self.message_input.toPlainText()
        if phone:
            msg = f"[هاتف: {phone}] {msg}"

        data = {
            "customer_id": self.customer_combo.currentData(),
            "source": source_map.get(self.source_combo.currentText(), "other"),
            "message": msg,
            "product_id": self.product_combo.currentData(),
            "priority": priority_map.get(self.priority_combo.currentText(), "medium"),
        }

        self.db.add_inquiry(data)
        self.accept()


class ReplyDialog(QDialog):
    def __init__(self, db, inquiry_id):
        super().__init__()
        self.db = db
        self.inquiry_id = inquiry_id
        self.setWindowTitle("رد على الاستفسار")
        self.setMinimumWidth(450)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        layout = QVBoxLayout(self)

        inquiry = db.get_inquiries()
        inq = next((i for i in inquiry if i["id"] == inquiry_id), None)

        if inq:
            info = QLabel(
                f"العميل: {inq['customer_name'] or 'غير معروف'}\n"
                f"الرسالة: {inq['message'] or ''}"
            )
            info.setStyleSheet("padding: 10px; background: #f0f0f0; border-radius: 5px;")
            info.setWordWrap(True)
            layout.addWidget(info)

        self.reply_input = QTextEdit()
        self.reply_input.setPlaceholderText("اكتب ردك هنا...")
        layout.addWidget(self.reply_input)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        save_btn = QPushButton("💾 إرسال الرد")
        save_btn.setObjectName("successBtn")
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self.save)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("❌ إلغاء")
        cancel_btn.setObjectName("dangerBtn")
        cancel_btn.setMinimumHeight(40)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def save(self):
        response = self.reply_input.toPlainText().strip()
        if not response:
            QMessageBox.warning(self, "تنبيه", "اكتب رد أولاً")
            return
        self.db.reply_to_inquiry(self.inquiry_id, response)
        self.accept()


# ===========================
# Sales & Reports
# ===========================
class CustomersWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QHBoxLayout()
        title = QLabel("إدارة العملاء")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        header.addWidget(title)
        header.addStretch()

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 بحث عن عميل...")
        self.search_input.setMinimumWidth(250)
        self.search_input.textChanged.connect(self.load_customers)
        search_layout.addWidget(self.search_input)
        header.addLayout(search_layout)
        layout.addLayout(header)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ إضافة عميل جديد")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self.add_customer)
        btn_layout.addWidget(add_btn)

        edit_btn = QPushButton("✏️ تعديل")
        edit_btn.setObjectName("warningBtn")
        edit_btn.clicked.connect(self.edit_customer)
        btn_layout.addWidget(edit_btn)

        delete_btn = QPushButton("🗑️ حذف")
        delete_btn.setObjectName("dangerBtn")
        delete_btn.clicked.connect(self.delete_customer)
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID", "العميل", "رقم الهاتف", "المنتج", "المصدر", "الرسالة", "الأولوية", "الحالة", "التاريخ"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnHidden(0, True)
        layout.addWidget(self.table)

        self.load_customers()

    def load_customers(self):
        search = self.search_input.text() if hasattr(self, 'search_input') else ""
        customers = self.db.get_customers(search=search)
        self.table.setRowCount(len(customers))
        for i, c in enumerate(customers):
            self.table.setItem(i, 0, QTableWidgetItem(str(c["id"])))
            self.table.setItem(i, 1, QTableWidgetItem(c["name"]))
            self.table.setItem(i, 2, QTableWidgetItem(c["phone"] or ""))
            self.table.setItem(i, 3, QTableWidgetItem(c["whatsapp"] or ""))
            self.table.setItem(i, 4, QTableWidgetItem(c["facebook_id"] or ""))
            self.table.setItem(i, 5, QTableWidgetItem(c["email"] or ""))
            self.table.setItem(i, 6, QTableWidgetItem(c["address"] or ""))

    def get_selected_id(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return int(self.table.item(rows[0].row(), 0).text())

    def add_customer(self):
        dialog = CustomerDialog(self.db)
        if dialog.exec():
            self.load_customers()

    def edit_customer(self):
        customer_id = self.get_selected_id()
        if not customer_id:
            QMessageBox.warning(self, "تنبيه", "اختر عميل أولاً")
            return
        dialog = CustomerDialog(self.db, customer_id)
        if dialog.exec():
            self.load_customers()

    def delete_customer(self):
        customer_id = self.get_selected_id()
        if not customer_id:
            QMessageBox.warning(self, "تنبيه", "اختر عميل أولاً")
            return
        reply = QMessageBox.question(
            self, "تأكيد", "هل أنت متأكد من حذف هذا العميل؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
            self.db.conn.commit()
            self.load_customers()


class ReportsWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("المبيعات والتقارير")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self.create_new_sale_tab(), "🛒 فاتورة جديدة")
        tabs.addTab(self.create_sales_history_tab(), "📋 سجل المبيعات")
        tabs.addTab(self.create_reports_tab(), "📊 التقارير")
        layout.addWidget(tabs)

    def create_new_sale_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form = QFormLayout()
        self.sale_customer = QComboBox()
        self.sale_customer.addItem("-- اختر عميل (اختياري) --", None)
        for c in self.db.get_customers():
            self.sale_customer.addItem(c["name"], c["id"])
        form.addRow("العميل:", self.sale_customer)
        layout.addLayout(form)

        items_group = QGroupBox("المنتجات")
        items_layout = QVBoxLayout(items_group)

        add_item_layout = QHBoxLayout()
        self.sale_product = QComboBox()
        self.sale_product.setMinimumWidth(250)
        for p in self.db.get_products():
            self.sale_product.addItem(f"{p['name']} ({p['quantity']} متاح)", p["id"])
        add_item_layout.addWidget(self.sale_product)

        self.sale_qty = QSpinBox()
        self.sale_qty.setRange(1, 9999)
        self.sale_qty.setValue(1)
        add_item_layout.addWidget(QLabel("الكمية:"))
        add_item_layout.addWidget(self.sale_qty)

        add_item_btn = QPushButton("➕ إضافة")
        add_item_btn.clicked.connect(self.add_sale_item)
        add_item_layout.addWidget(add_item_btn)
        add_item_layout.addStretch()
        items_layout.addLayout(add_item_layout)

        self.sale_items_table = QTableWidget()
        self.sale_items_table.setColumnCount(5)
        self.sale_items_table.setHorizontalHeaderLabels([
            "ID المنتج", "المنتج", "الكمية", "السعر", "الإجمالي"
        ])
        self.sale_items_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sale_items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        items_layout.addWidget(self.sale_items_table)

        self.sale_items = []

        remove_item_btn = QPushButton("🗑️ حذف المنتج المحدد")
        remove_item_btn.clicked.connect(self.remove_sale_item)
        items_layout.addWidget(remove_item_btn)

        layout.addWidget(items_group)

        totals_layout = QHBoxLayout()
        totals_layout.setSpacing(30)

        self.discount_input = QDoubleSpinBox()
        self.discount_input.setRange(0, 999999)
        self.discount_input.setSuffix(" ج.م")
        totals_layout.addWidget(QLabel("الخصم:"))
        totals_layout.addWidget(self.discount_input)

        self.tax_input = QDoubleSpinBox()
        self.tax_input.setRange(0, 999999)
        self.tax_input.setSuffix(" ج.م")
        totals_layout.addWidget(QLabel("الضريبة:"))
        totals_layout.addWidget(self.tax_input)

        self.total_label = QLabel("الإجمالي: 0.00 ج.م")
        self.total_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #27ae60;")
        totals_layout.addWidget(self.total_label)

        totals_layout.addStretch()
        layout.addLayout(totals_layout)

        confirm_sale_btn = QPushButton("✅ تأكيد البيع")
        confirm_sale_btn.setObjectName("successBtn")
        confirm_sale_btn.clicked.connect(self.confirm_sale)
        layout.addWidget(confirm_sale_btn)

        return widget

    def add_sale_item(self):
        product_id = self.sale_product.currentData()
        if not product_id:
            return
        qty = self.sale_qty.value()
        product = self.db.get_product_by_id(product_id)
        if not product:
            return
        if qty > product["quantity"]:
            QMessageBox.warning(self, "تنبيه", f"الكمية المتاحة: {product['quantity']}")
            return

        self.sale_items.append({
            "product_id": product_id,
            "product_name": product["name"],
            "quantity": qty,
            "unit_price": product["price"],
        })
        self.refresh_sale_items()

    def remove_sale_item(self):
        rows = self.sale_items_table.selectionModel().selectedRows()
        if not rows:
            return
        del self.sale_items[rows[0].row()]
        self.refresh_sale_items()

    def refresh_sale_items(self):
        self.sale_items_table.setRowCount(len(self.sale_items))
        total = 0
        for i, item in enumerate(self.sale_items):
            item_total = item["quantity"] * item["unit_price"]
            total += item_total
            self.sale_items_table.setItem(i, 0, QTableWidgetItem(str(item["product_id"])))
            self.sale_items_table.setItem(i, 1, QTableWidgetItem(item["product_name"]))
            self.sale_items_table.setItem(i, 2, QTableWidgetItem(str(item["quantity"])))
            self.sale_items_table.setItem(i, 3, QTableWidgetItem(f"{item['unit_price']:.2f}"))
            self.sale_items_table.setItem(i, 4, QTableWidgetItem(f"{item_total:.2f}"))

        final = total - self.discount_input.value() + self.tax_input.value()
        self.total_label.setText(f"الإجمالي: {final:,.2f} ج.م")

    def confirm_sale(self):
        if not self.sale_items:
            QMessageBox.warning(self, "تنبيه", "أضف منتجات أولاً")
            return

        customer_id = self.sale_customer.currentData()
        self.db.add_sale(
            customer_id=customer_id,
            items=self.sale_items,
            discount=self.discount_input.value(),
            tax=self.tax_input.value(),
        )
        QMessageBox.information(self, "نجاح", "تم تسجيل البيع بنجاح!")
        self.sale_items.clear()
        self.refresh_sale_items()

    def create_sales_history_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        filter_layout = QHBoxLayout()
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        filter_layout.addWidget(QLabel("من:"))
        filter_layout.addWidget(self.date_from)

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        filter_layout.addWidget(QLabel("إلى:"))
        filter_layout.addWidget(self.date_to)

        search_btn = QPushButton("🔍 بحث")
        search_btn.clicked.connect(self.load_sales_history)
        filter_layout.addWidget(search_btn)
        filter_layout.addStretch()

        layout.addLayout(filter_layout)

        self.sales_table = QTableWidget()
        self.sales_table.setColumnCount(6)
        self.sales_table.setHorizontalHeaderLabels([
            "رقم الفاتورة", "العميل", "المبلغ", "الخصم", "الإجمالي", "التاريخ"
        ])
        self.sales_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sales_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.sales_table)

        self.load_sales_history()
        return widget

    def load_sales_history(self):
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")
        sales = self.db.get_sales(date_from=date_from, date_to=date_to)
        self.sales_table.setRowCount(len(sales))
        for i, s in enumerate(sales):
            self.sales_table.setItem(i, 0, QTableWidgetItem(s["invoice_number"]))
            self.sales_table.setItem(i, 1, QTableWidgetItem(s["customer_name"] or ""))
            self.sales_table.setItem(i, 2, QTableWidgetItem(f"{s['total_amount']:.2f}"))
            self.sales_table.setItem(i, 3, QTableWidgetItem(f"{s['discount']:.2f}"))
            self.sales_table.setItem(i, 4, QTableWidgetItem(f"{s['final_amount']:.2f}"))
            self.sales_table.setItem(i, 5, QTableWidgetItem(str(s["created_at"])))

    def create_reports_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        summary = self.db.get_sales_summary(30)
        stats_grid = QGridLayout()

        stats_grid.addWidget(StatCard("مبيعات آخر 30 يوم", summary["total_sales"], "", "#3498db"), 0, 0)
        stats_grid.addWidget(StatCard("الإيراد", f"{summary['total_revenue']:,.0f} ج.م", "", "#27ae60"), 0, 1)
        stats_grid.addWidget(StatCard("متوسط الفاتورة", f"{summary['avg_sale']:,.0f} ج.م", "", "#f39c12"), 0, 2)

        low = self.db.get_low_stock_products()
        stats_grid.addWidget(StatCard("منتجات منخفضة", len(low), "", "#e74c3c"), 1, 0)

        layout.addLayout(stats_grid)
        layout.addStretch()
        return widget


# ===========================
# Settings Widget
# ===========================
class SettingsWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("الإعدادات")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        general_group = QGroupBox("الإعدادات العامة")
        general_layout = QFormLayout(general_group)

        self.company_name = QLineEdit()
        self.company_name.setText(db.get_setting("company_name", "شركتي للطباعة"))
        general_layout.addRow("اسم الشركة:", self.company_name)

        self.company_phone = QLineEdit()
        self.company_phone.setText(db.get_setting("company_phone", ""))
        general_layout.addRow("هاتف الشركة:", self.company_phone)

        self.company_whatsapp = QLineEdit()
        self.company_whatsapp.setText(db.get_setting("company_whatsapp", ""))
        general_layout.addRow("واتساب الشركة:", self.company_whatsapp)

        save_btn = QPushButton("💾 حفظ الإعدادات")
        save_btn.setObjectName("successBtn")
        save_btn.clicked.connect(self.save_settings)
        general_layout.addRow("", save_btn)

        layout.addWidget(general_group)

        network_group = QGroupBox("🔗 الشبكة المحلية (مشاركة مع أجهزة أخرى)")
        network_layout = QFormLayout(network_group)

        self.server_mode = QComboBox()
        self.server_mode.addItems(["خادم (Server) - هذا الجهاز هو الرئيسي", "عميل (Client) - يتصل بخادم آخر"])
        self.server_mode.setCurrentIndex(0 if db.get_setting("network_mode", "server") == "server" else 1)
        self.server_mode.currentIndexChanged.connect(self.toggle_network_mode)
        network_layout.addRow("وضع الشبكة:", self.server_mode)

        self.server_url = QLineEdit()
        self.server_url.setPlaceholderText("http://192.168.1.100:5000")
        self.server_url.setText(db.get_setting("server_url", "http://localhost:5000"))
        network_layout.addRow("رابط الخادم:", self.server_url)

        self.server_port = QSpinBox()
        self.server_port.setRange(1024, 65535)
        self.server_port.setValue(int(db.get_setting("server_port", "5000")))
        network_layout.addRow("منفذ الخادم:", self.server_port)

        self.local_ip = QLineEdit()
        self.local_ip.setReadOnly(True)
        try:
            import socket
            hostname = socket.gethostname()
            self.local_ip.setText(f"{socket.gethostbyname(hostname)}:{self.server_port.value()}")
        except:
            self.local_ip.setText("غير معروف")
        network_layout.addRow("IP هذا الجهاز:", self.local_ip)

        info_label = QLabel("💡 في وضع الخادم، الأجهزة الأخرى تفتح المتصفح على الرابط أعلاه\nفي وضع العميل، البرنامج يتصل بالخادم المركزي")
        info_label.setStyleSheet("font-size: 12px; color: #7f8c8d; padding: 8px; background: #f8f9fa; border-radius: 5px;")
        info_label.setWordWrap(True)
        network_layout.addRow(info_label)

        layout.addWidget(network_group)

        backup_group = QGroupBox("النسخ الاحتياطي")
        backup_layout = QVBoxLayout(backup_group)

        backup_btn = QPushButton("💾 عمل نسخة احتياطية")
        backup_btn.setObjectName("primaryBtn")
        backup_btn.clicked.connect(self.backup_db)
        backup_layout.addWidget(backup_btn)

        layout.addWidget(backup_group)
        layout.addStretch()

    def toggle_network_mode(self):
        mode = "server" if self.server_mode.currentIndex() == 0 else "client"
        self.db.set_setting("network_mode", mode)

    def save_settings(self):
        self.db.set_setting("company_name", self.company_name.text())
        self.db.set_setting("company_phone", self.company_phone.text())
        self.db.set_setting("company_whatsapp", self.company_whatsapp.text())
        self.db.set_setting("server_url", self.server_url.text())
        self.db.set_setting("server_port", str(self.server_port.value()))
        self.db.set_setting("network_mode", "server" if self.server_mode.currentIndex() == 0 else "client")
        QMessageBox.information(self, "نجاح", "تم حفظ الإعدادات بنجاح")

    def backup_db(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "حفظ النسخة الاحتياطية",
            f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
            "Database (*.db)"
        )
        if path:
            self.db.backup_database(path)
            QMessageBox.information(self, "نجاح", f"تم حفظ النسخة الاحتياطية في:\n{path}")


# ===========================
# WhatsApp Integration Widget
# ===========================
WA_SERVER = "http://localhost:3000"

class IntegrationWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.server_started = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("ربط واتساب Web")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self.create_whatsapp_tab(), "📱 واتساب Web")
        tabs.addTab(self.create_auto_reply_tab(), "💬 الردود التلقائية")
        tabs.addTab(self.create_help_tab(), "❓ مساعدة")
        layout.addWidget(tabs)

        # Auto-start server immediately
        QTimer.singleShot(100, self.auto_start_server)

        # Timer to check status
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.check_status)
        self.status_timer.start(3000)

    def create_whatsapp_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        header = QLabel("واتساب - متصل تلقائياً")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #27ae60; margin-bottom: 10px;")
        layout.addWidget(header)

        info = QLabel(
            "🔹 الخادم يشتغل تلقائياً بمجرد فتح البرنامج\n"
            "🔹 مسح QR Code مرة واحدة فقط أول مرة\n"
            "🔹 بعد كده يتصل لوحده كل ما تفتح البرنامج\n\n"
            "لأول مرة فقط:\n"
            "1. انتظر ظهور QR Code على الشاشة\n"
            "2. افتح واتساب ← الإعدادات ← أجهزة مربوطة ← ربط جهاز\n"
            "3. امسح QR Code\n"
            "4. خلاص! بعد كده يتصل تلقائياً"
        )
        info.setStyleSheet("font-size: 13px; color: #2c3e50; padding: 15px; background: #e8f5e9; border-radius: 8px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        status_group = QGroupBox("حالة الاتصال")
        status_layout = QVBoxLayout(status_group)

        self.status_label = QLabel("🔴 غير متصل")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #e74c3c; padding: 10px;")
        status_layout.addWidget(self.status_label)

        self.phone_label = QLabel("")
        self.phone_label.setStyleSheet("font-size: 14px; color: #7f8c8d;")
        status_layout.addWidget(self.phone_label)

        layout.addWidget(status_group)

        qr_group = QGroupBox("QR Code - امسحه بواتساب")
        qr_layout = QVBoxLayout(qr_group)

        self.qr_label = QLabel("اضغط 'تشغيل الخادم' عشان يظهر الـ QR Code")
        self.qr_label.setStyleSheet("font-size: 14px; color: #7f8c8d; padding: 20px; background: #f8f9fa; border-radius: 8px;")
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setMinimumHeight(200)
        self.qr_label.setWordWrap(True)
        qr_layout.addWidget(self.qr_label)

        layout.addWidget(qr_group)

        btn_layout = QHBoxLayout()

        self.start_btn = QPushButton("▶️ تشغيل الخادم")
        self.start_btn.setObjectName("successBtn")
        self.start_btn.setMinimumHeight(50)
        self.start_btn.clicked.connect(self.start_server)
        btn_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹️ إيقاف الخادم")
        self.stop_btn.setObjectName("dangerBtn")
        self.stop_btn.setMinimumHeight(50)
        self.stop_btn.clicked.connect(self.stop_server)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)

        self.refresh_btn = QPushButton("🔄 تحديث الحالة")
        self.refresh_btn.setObjectName("primaryBtn")
        self.refresh_btn.setMinimumHeight(50)
        self.refresh_btn.clicked.connect(self.check_status)
        btn_layout.addWidget(self.refresh_btn)

        layout.addLayout(btn_layout)

        layout.addStretch()
        return widget

    def create_auto_reply_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        header = QLabel("الردود التلقائية على واتساب")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; margin-bottom: 10px;")
        layout.addWidget(header)

        info = QLabel("الردود دي هتتبعت تلقائياً لما حد يبعت رسالة على واتساب")
        info.setStyleSheet("font-size: 13px; color: #7f8c8d; padding: 10px;")
        layout.addWidget(info)

        welcome_group = QGroupBox("رسالة ترحيب")
        welcome_layout = QVBoxLayout(welcome_group)

        self.welcome_msg = QTextEdit()
        self.welcome_msg.setPlainText(self.db.get_setting(
            "auto_welcome",
            "مرحباً بك! 👋\nشكراً لتواصلك معنا.\nكيف نقدر نساعدك؟"
        ))
        self.welcome_msg.setMaximumHeight(100)
        welcome_layout.addWidget(self.welcome_msg)

        layout.addWidget(welcome_group)

        keywords_group = QGroupBox("ردود حسب الكلمات")
        keywords_layout = QVBoxLayout(keywords_group)

        self.keywords_table = QTableWidget()
        self.keywords_table.setColumnCount(2)
        self.keywords_table.setHorizontalHeaderLabels(["الكلمة", "الرد"])
        self.keywords_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        keywords_layout.addWidget(self.keywords_table)

        add_layout = QHBoxLayout()
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("الكلمة (مثال: سعر)")
        add_layout.addWidget(self.keyword_input)

        self.reply_input = QLineEdit()
        self.reply_input.setPlaceholderText("الرد التلقائي")
        add_layout.addWidget(self.reply_input)

        add_btn = QPushButton("➕ إضافة")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self.add_auto_reply)
        add_layout.addWidget(add_btn)

        keywords_layout.addLayout(add_layout)

        del_btn = QPushButton("🗑️ حذف المحدد")
        del_btn.setObjectName("dangerBtn")
        del_btn.clicked.connect(self.delete_auto_reply)
        keywords_layout.addWidget(del_btn)

        layout.addWidget(keywords_group)

        save_btn = QPushButton("💾 حفظ وتحديث الردود على الخادم")
        save_btn.setObjectName("successBtn")
        save_btn.setMinimumHeight(45)
        save_btn.clicked.connect(self.save_and_update_replies)
        layout.addWidget(save_btn)

        self.load_auto_replies()
        return widget

    def create_help_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        header = QLabel("كيف تربط واتساب Web")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; margin-bottom: 10px;")
        layout.addWidget(header)

        help_text = QLabel(
            "<h3>📱 التشغيل التلقائي:</h3>"
            "<p>الخادم يشتغل تلقائياً بمجرد فتح البرنامج</p>"
            "<p>أول مرة فقط هتظهر QR Code لمسحه</p>"
            "<p>بعد كده يتصل لوحده كل مرة</p>"
            "<br>"
            "<h3>📱 أول مرة:</h3>"
            "<p><b>1.</b> الخادم هيشتغل تلقائياً</p>"
            "<p><b>2.</b> هيظهر QR Code على الشاشة</p>"
            "<p><b>3.</b> افتح واتساب: الإعدادات ← أجهزة مربوطة ← ربط جهاز</p>"
            "<p><b>4.</b> امسح QR Code</p>"
            "<p><b>5.</b> خلاص! بعد كده يتصل تلقائياً</p>"
            "<br>"
            "<h3>💡 ملاحظات:</h3>"
            "<p>- التليفون لازم يكون متصل بالنت</p>"
            "<p>- ممكن تربط 4 أجهزة واتساب Web</p>"
            "<p>- لو حصل مشكلة، استخدم 'تحديث الحالة'</p>"
            "<p>- لو اتقطع نهائياً، ارجع للتبويب واتساب واضغط 'تشغيل الخادم'</p>"
            "<br>"
            "<h3>⚠️ تحذير:</h3>"
            "<p>- دي طريقة غير رسمية (WhatsApp Web.js)</p>"
            "<p>- ممكن واتساب يقفل الحساب مؤقتاً</p>"
        )
        help_text.setStyleSheet("font-size: 13px; color: #2c3e50; padding: 15px; background: #f8f9fa; border-radius: 8px;")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        layout.addStretch()
        return widget

    def find_server_dir(self):
        """Find whatsapp_server directory in multiple locations"""
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
        else:
            exe_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Check multiple locations
        possible_paths = [
            os.path.join(exe_dir, "whatsapp_server"),
            os.path.join(os.path.dirname(exe_dir), "whatsapp_server"),
            os.path.join(exe_dir, "printing_app", "whatsapp_server"),
        ]
        
        for path in possible_paths:
            if os.path.exists(os.path.join(path, "server.js")):
                return path
        
        return None

    def get_node_path(self, server_dir):
        """Find node executable in server directory or system PATH"""
        bundled = os.path.join(server_dir, "node.exe")
        if os.path.exists(bundled):
            return bundled
        return "node"

    def auto_start_server(self):
        """Auto-start WhatsApp server silently"""
        import subprocess
        import threading
        
        if self.server_started:
            return
        
        server_dir = self.find_server_dir()
        
        if not server_dir:
            return
        
        node_path = self.get_node_path(server_dir)
        
        def run_server():
            try:
                subprocess.run(
                    [node_path, "server.js"],
                    cwd=server_dir,
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception as e:
                print(f"Server error: {e}")
        
        # Start server in background thread
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        self.server_started = True
        self.status_label.setText("🟡 جاري تحميل واتساب...")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #f39c12; padding: 10px;")

    def start_server(self):
        import subprocess
        import threading
        
        server_dir = self.find_server_dir()
        
        if not server_dir:
            QMessageBox.warning(self, "خطأ", "ملف الخادم غير موجود!\nتأكد إن مجلد whatsapp_server موجود بجانب التطبيق")
            return
        
        node_path = self.get_node_path(server_dir)
        
        def run_server():
            try:
                subprocess.run(
                    [node_path, "server.js"],
                    cwd=server_dir,
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception as e:
                print(f"Server error: {e}")
        
        # Start server in background thread
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("🟡 جاري تشغيل الخادم...")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #f39c12; padding: 10px;")
        self.qr_label.setText("جاري تحميل واتساب...\nانتظر ظهور QR Code")

    def stop_server(self):
        import subprocess
        subprocess.run("taskkill /F /IM node.exe /T", shell=True, capture_output=True)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("🔴 غير متصل")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #e74c3c; padding: 10px;")
        self.qr_label.setText("الخادم متوقف")

    def check_status(self):
        try:
            resp = requests.get(f"{WA_SERVER}/api/status", timeout=2)
            data = resp.json()

            if data.get('connected'):
                self.status_label.setText("🟢 متصل بواتساب")
                self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #27ae60; padding: 10px;")
                self.phone_label.setText(f"الرقم: {data.get('phone', 'غير معروف')}")
                self.qr_label.setText("✅ واتساب متصل بنجاح!\nالردود التلقائية شغالة")
                self.qr_label.setPixmap(QPixmap())
                self.qr_label.setMinimumHeight(60)
                self.start_btn.setEnabled(False)
                self.stop_btn.setEnabled(True)
            elif data.get('qr'):
                self.status_label.setText("🟡 في انتظار مسح QR Code")
                self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #f39c12; padding: 10px;")
                self.fetch_and_show_qr()
                self.start_btn.setEnabled(False)
                self.stop_btn.setEnabled(True)
            else:
                self.status_label.setText("🔴 جاري التحميل...")
                self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #e74c3c; padding: 10px;")
        except:
            self.status_label.setText("🔴 الخادم متوقف")
            self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #e74c3c; padding: 10px;")
            self.phone_label.setText("")
            self.qr_label.setText("الخادم متوقف")
            self.qr_label.setPixmap(QPixmap())
            self.qr_label.setMinimumHeight(60)
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def fetch_and_show_qr(self):
        try:
            resp = requests.get(f"{WA_SERVER}/api/qr", timeout=2)
            data = resp.json()
            if data.get('qr'):
                import base64
                b64 = data['qr'].split(',')[1] if ',' in data['qr'] else data['qr']
                img_data = base64.b64decode(b64)
                pixmap = QPixmap()
                pixmap.loadFromData(img_data)
                scaled = pixmap.scaled(280, 280, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.qr_label.setPixmap(scaled)
                self.qr_label.setMinimumHeight(300)
                self.qr_label.setText("")
                self.qr_label.setStyleSheet("padding: 10px; background: white; border: 2px solid #27ae60; border-radius: 8px;")
            else:
                self.qr_label.setText("📱 جاري تحميل QR Code...\n\nالإعدادات ← أجهزة مربوطة ← ربط جهاز")
                self.qr_label.setPixmap(QPixmap())
                self.qr_label.setMinimumHeight(200)
                self.qr_label.setStyleSheet("font-size: 14px; color: #7f8c8d; padding: 20px; background: #f8f9fa; border-radius: 8px;")
        except:
            pass

    def add_auto_reply(self):
        keyword = self.keyword_input.text().strip()
        reply = self.reply_input.text().strip()
        if not keyword or not reply:
            QMessageBox.warning(self, "تنبيه", "اكتب الكلمة والرد")
            return

        row = self.keywords_table.rowCount()
        self.keywords_table.insertRow(row)
        self.keywords_table.setItem(row, 0, QTableWidgetItem(keyword))
        self.keywords_table.setItem(row, 1, QTableWidgetItem(reply))
        self.keyword_input.clear()
        self.reply_input.clear()

    def delete_auto_reply(self):
        rows = self.keywords_table.selectionModel().selectedRows()
        if not rows:
            return
        for row in sorted(rows, reverse=True):
            self.keywords_table.removeRow(row.row())

    def save_and_update_replies(self):
        replies = {}
        for i in range(self.keywords_table.rowCount()):
            keyword = self.keywords_table.item(i, 0).text()
            reply = self.keywords_table.item(i, 1).text()
            replies[keyword] = reply

        welcome = self.welcome_msg.toPlainText()

        self.db.set_setting("auto_welcome", welcome)
        self.db.set_setting("auto_replies", json.dumps(replies, ensure_ascii=False))

        try:
            requests.post(f"{WA_SERVER}/api/replies", json={
                "replies": replies,
                "welcome": welcome
            }, timeout=2)
            QMessageBox.information(self, "نجاح", "تم حفظ وتحديث الردود بنجاح!")
        except:
            QMessageBox.information(self, "نجاح", "تم حفظ الردود!\n(الخادم مش شغال - هيشتغل لما تشغله)")

    def load_auto_replies(self):
        replies_str = self.db.get_setting("auto_replies", "{}")
        try:
            replies = json.loads(replies_str)
        except:
            replies = {}

        self.keywords_table.setRowCount(len(replies))
        for i, (keyword, reply) in enumerate(replies.items()):
            self.keywords_table.setItem(i, 0, QTableWidgetItem(keyword))
            self.keywords_table.setItem(i, 1, QTableWidgetItem(reply))


# ===========================
# Main Window
# ===========================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.setWindowTitle("نظام إدارة مطبعة - Printing Management System")
        self.setMinimumSize(1200, 700)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        logo = QLabel("🖨️ نظام المطبعة")
        logo.setObjectName("sidebarTitle")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(logo)

        self.nav_buttons = []
        nav_items = [
            ("🏠 لوحة التحكم", 0),
            ("📦 المنتجات", 1),
            ("📊 المخزون", 2),
            ("👥 العملاء", 3),
            ("💬 الاستفسارات", 4),
            ("🛒 المبيعات", 5),
            ("🔗 واتساب وفيسبوك", 6),
            ("⚙️ الإعدادات", 7),
        ]

        for text, idx in nav_items:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, i=idx: self.switch_page(i))
            sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sidebar_layout.addStretch()

        self.stack = QStackedWidget()
        self.stack.addWidget(DashboardWidget(self.db))
        self.stack.addWidget(ProductsWidget(self.db))
        self.stack.addWidget(InventoryWidget(self.db))
        self.stack.addWidget(CustomersWidget(self.db))
        self.stack.addWidget(InquiriesWidget(self.db))
        self.stack.addWidget(ReportsWidget(self.db))
        self.stack.addWidget(IntegrationWidget(self.db))
        self.stack.addWidget(SettingsWidget(self.db))

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stack)

        self.switch_page(0)

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

    def closeEvent(self, event):
        self.db.close()
        event.accept()
