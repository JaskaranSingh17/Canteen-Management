import os
import json
import random
import sqlite3
import datetime as dt
import subprocess
import platform

import tkinter as tk
from tkinter import ttk, messagebox

# Matplotlib imports for Tkinter embedding
from matplotlib.figure import Figure
try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except Exception:
    FigureCanvasTkAgg = None

# QR code generation
try:
    import qrcode
except Exception:
    qrcode = None

# PDF generation for receipts
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    reportlab_available = True
except Exception:
    reportlab_available = False

# Excel/CSV export
try:
    import pandas as pd
    pandas_available = True
except Exception:
    pandas_available = False

import csv


ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
DB_PATH = os.path.join(os.path.dirname(__file__), "canteen.db")
UPI_ID = "jaskaran.singh.170506@okaxis"  # demo UPI id

# UI Palette - Bright Warm Light (White + Orange/Red)
PALETTE = {
    "bg": "#ffffff",  # pure white background
    "panel": "#ffffff",  # panels blend into white
    "panel_alt": "#fff7ed",  # light warm panel
    "panel_hover": "#ffedd5",  # hover: soft orange tint
    "text": "#111827",  # near-black text
    "text_secondary": "#4b5563",  # slate
    "muted": "#6b7280",  # muted slate
    "border": "#e5e7eb",  # light gray border
    "border_focus": "#fb923c",  # bright orange focus
    "primary": "#fb6a00",  # vivid orange
    "primary_hover": "#f97316",  # hot orange
    "primary_alt": "#ff8a4a",  # tangerine
    "accent": "#ef4444",  # strong red
    "accent_hover": "#dc2626",  # deeper red
    "accent_alt": "#ff4d4d",  # bright red
    "danger": "#ef4444",  # red
    "danger_hover": "#dc2626",
    "success": "#16a34a",  # emerald
    "success_hover": "#15803d",
    "warning": "#f59e0b",  # amber
    "warning_hover": "#d97706",
    "info": "#fb7185",  # warm info
    "info_hover": "#f43f5e",
    "input_bg": "#ffffff",  # light inputs
    "input_focus": "#fff1e6",  # focused input warm tint
    "row_alt": "#fff7ed",  # zebra warm
    "row_alt2": "#fffaf5",  # zebra alt
    "table_header": "#ffedd5",  # warm header
    "selection_bg": "#fb6a00",  # bright selection
    "selection_fg": "#ffffff",  # white on orange
    "highlight": "#ffedd5",  # highlight
    "shadow": "#000000",
    "link": "#fb6a00",
    "link_hover": "#f97316",
    "badge_bg": "#fff1e6",
    "badge_fg": "#7c2d12",
    "chip_bg": "#ffedd5",
    "chip_fg": "#7c2d12",
    "gradient_start": "#fb6a00",
    "gradient_end": "#ef4444",
    # Chart series (bright warm ramp)
    "chart_1": "#fb6a00",
    "chart_2": "#f97316",
    "chart_3": "#ef4444",
    "chart_4": "#ff8a4a",
    "chart_5": "#f43f5e",
    "chart_6": "#f59e0b",
    "chart_7": "#dc2626",
    "chart_8": "#ffa94d",
}


def ensure_assets_dir_exists() -> None:
    if not os.path.isdir(ASSETS_DIR):
        os.makedirs(ASSETS_DIR, exist_ok=True)


def format_datetime(timestamp_str: str) -> str:
    """Format ISO timestamp to user-friendly format."""
    try:
        dt_obj = dt.datetime.fromisoformat(timestamp_str)
        # Format: "Nov 4, 2025 12:18 AM"
        return dt_obj.strftime("%b %d, %Y %I:%M %p")
    except Exception:
        # Fallback: try to parse common formats
        try:
            # Handle format like "2025-11-04T00:18:55"
            if "T" in timestamp_str:
                date_part, time_part = timestamp_str.split("T")
                year, month, day = date_part.split("-")
                hour, minute, second = time_part.split(":")[:3]
                dt_obj = dt.datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
                return dt_obj.strftime("%b %d, %Y %I:%M %p")
        except Exception:
            pass
        # If all else fails, return as-is
        return timestamp_str


def calculate_discounted_price(original_price: float, offers: list) -> tuple[float, str | None]:
    """Calculate discounted price based on active offers.
    
    Args:
        original_price: Original item price
        offers: List of active offers for the item
        
    Returns:
        Tuple of (final_price, offer_description) where offer_description is None if no discount
    """
    if not offers:
        return original_price, None
    
    # Apply the best offer (highest discount)
    best_offer = None
    best_discount = 0.0
    
    for offer in offers:
        if offer["discount_type"] == "PERCENTAGE":
            discount = original_price * (offer["discount_value"] / 100)
        else:  # FIXED
            discount = offer["discount_value"]
        
        if discount > best_discount:
            best_discount = discount
            best_offer = offer
    
    if best_offer:
        final_price = max(0.0, original_price - best_discount)
        offer_desc = f"{best_offer['offer_name']}: "
        if best_offer["discount_type"] == "PERCENTAGE":
            offer_desc += f"{best_offer['discount_value']:.0f}% off"
        else:
            offer_desc += f"Rs {best_offer['discount_value']:.2f} off"
        return final_price, offer_desc
    
    return original_price, None


def generate_receipt_pdf(order_data: dict, user_data: dict, qr_path: str = None) -> str:
    """Generate a professional PDF receipt for a completed order.
    
    Args:
        order_data: Dictionary containing order information
        user_data: Dictionary containing user information
        qr_path: Optional path to QR code image
        
    Returns:
        Path to the generated PDF file
    """
    if not reportlab_available:
        raise ImportError("reportlab library is not installed. Install it with: pip install reportlab")
    
    ensure_assets_dir_exists()
    
    # Create PDF filename
    order_id = order_data["order_id"]
    pdf_filename = f"receipt_order_{order_id}.pdf"
    pdf_path = os.path.join(ASSETS_DIR, pdf_filename)
    
    # Create PDF document
    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    story = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1f2e'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 10
    normal_style.leading = 14
    
    # Header
    story.append(Paragraph("🍽️ CANTEEN PAYMENT SYSTEM", title_style))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("OFFICIAL RECEIPT", heading_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Order Information
    order_info_data = [
        ['Order ID:', str(order_data["order_id"])],
        ['Token Number:', order_data["token_number"]],
        ['Date & Time:', format_datetime(order_data["timestamp"])],
        ['Status:', order_data["status"]],
    ]
    
    order_info_table = Table(order_info_data, colWidths=[2*inch, 4*inch])
    order_info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(order_info_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Customer Information
    customer_info_data = [
        ['Customer Name:', user_data.get("name", "N/A")],
        ['Customer ID:', user_data.get("user_id", "N/A")],
    ]
    
    customer_info_table = Table(customer_info_data, colWidths=[2*inch, 4*inch])
    customer_info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(Paragraph("Customer Details", heading_style))
    story.append(customer_info_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Items Table
    story.append(Paragraph("Ordered Items", heading_style))
    items_data = [['Item Name', 'Quantity', 'Unit Price (Rs)', 'Total (Rs)']]
    
    for item in order_data["items"]:
        item_name = item["item_name"]
        quantity = item.get("qty", 1)
        unit_price = float(item["price"])
        total_price = unit_price * quantity
        items_data.append([
            item_name,
            str(quantity),
            f"{unit_price:.2f}",
            f"{total_price:.2f}"
        ])
    
    items_table = Table(items_data, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Total Amount
    total_data = [
        ['', '', 'Total Amount:', f"Rs {order_data['total_amount']:.2f}"]
    ]
    total_table = Table(total_data, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
    total_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (2, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (2, 0), (-1, -1), 12),
        ('TEXTCOLOR', (2, 0), (-1, -1), colors.HexColor('#2c3e50')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(total_table)
    story.append(Spacer(1, 0.3*inch))
    
    # QR Code (if available)
    if qr_path and os.path.exists(qr_path):
        try:
            story.append(Paragraph("Transaction QR Code", heading_style))
            qr_img = Image(qr_path, width=2*inch, height=2*inch)
            story.append(qr_img)
            story.append(Spacer(1, 0.2*inch))
        except Exception:
            pass
    
    # Footer
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("Thank you for your order!", normal_style))
    story.append(Paragraph("This is a computer-generated receipt.", 
                          ParagraphStyle('Footer', parent=normal_style, fontSize=8, 
                                       textColor=colors.grey, alignment=TA_CENTER)))
    
    # Build PDF
    doc.build(story)
    return pdf_path


class DatabaseHandler:
    """Encapsulates all SQLite operations and reporting queries."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._ensure_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _ensure_db(self) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS menu (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT UNIQUE NOT NULL,
                    price REAL NOT NULL,
                    available INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    items TEXT NOT NULL, -- JSON
                    total_amount REAL NOT NULL,
                    token_number TEXT NOT NULL,
                    status TEXT NOT NULL, -- PLACED | READY | COMPLETED
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS offers (
                    offer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    offer_name TEXT NOT NULL,
                    item_id INTEGER,
                    discount_type TEXT NOT NULL, -- PERCENTAGE | FIXED
                    discount_value REAL NOT NULL,
                    start_date TEXT,
                    end_date TEXT,
                    day_of_week TEXT, -- MON, TUE, WED, etc. or NULL for all days
                    active INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (item_id) REFERENCES menu(item_id)
                )
                """
            )
            conn.commit()

        # Seed menu if empty
        if not self.list_menu():
            self._seed_menu()

    def _seed_menu(self) -> None:
        default_items = [
            ("Masala Dosa", 50.0, 1),
            ("Idli Sambar", 35.0, 1),
            ("Veg Sandwich", 45.0, 1),
            ("Pav Bhaji", 70.0, 1),
            ("Chole Bhature", 80.0, 1),
            ("Tea", 10.0, 1),
            ("Coffee", 15.0, 1),
        ]
        with self._connect() as conn:
            cur = conn.cursor()
            cur.executemany(
                "INSERT OR IGNORE INTO menu(item_name, price, available) VALUES (?, ?, ?)",
                default_items,
            )
            conn.commit()

    # Users
    def get_user(self, user_id: str):
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT user_id, name, role FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            return {"user_id": row[0], "name": row[1], "role": row[2]} if row else None

    def get_user_by_name_and_id(self, name: str, user_id: str):
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT user_id, name, role FROM users WHERE user_id = ? AND name = ?",
                (user_id, name),
            )
            row = cur.fetchone()
            return {"user_id": row[0], "name": row[1], "role": row[2]} if row else None

    def create_user(self, user_id: str, name: str, role: str) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users(user_id, name, role) VALUES (?, ?, ?)",
                (user_id, name, role),
            )
            conn.commit()

    # Menu
    def list_menu(self):
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT item_id, item_name, price, available FROM menu ORDER BY item_name ASC"
            )
            rows = cur.fetchall()
            return [
                {"item_id": r[0], "item_name": r[1], "price": r[2], "available": bool(r[3])}
                for r in rows
            ]

    def add_menu_item(self, item_name: str, price: float, available: bool = True) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO menu(item_name, price, available) VALUES (?, ?, ?)",
                (item_name, price, 1 if available else 0),
            )
            conn.commit()

    def update_menu_item(self, item_id: int, item_name: str, price: float, available: bool) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE menu SET item_name = ?, price = ?, available = ? WHERE item_id = ?",
                (item_name, price, 1 if available else 0, item_id),
            )
            conn.commit()

    def delete_menu_item(self, item_id: int) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM menu WHERE item_id = ?", (item_id,))
            conn.commit()

    # Orders
    def _generate_unique_token(self) -> str:
        with self._connect() as conn:
            cur = conn.cursor()
            while True:
                token = str(random.randint(1000, 9999))
                cur.execute("SELECT 1 FROM orders WHERE token_number = ?", (token,))
                if cur.fetchone() is None:
                    return token

    def create_order(self, user_id: str, items: list, total_amount: float) -> int:
        token = self._generate_unique_token()
        timestamp = dt.datetime.now().isoformat(timespec="seconds")
        items_json = json.dumps(items)
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO orders(user_id, items, total_amount, token_number, status, timestamp)
                VALUES (?, ?, ?, ?, 'PLACED', ?)
                """,
                (user_id, items_json, total_amount, token, timestamp),
            )
            conn.commit()
            return cur.lastrowid

    def update_order_status(self, order_id: int, status: str) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id))
            conn.commit()

    def list_orders(self, status: str | None = None):
        query = "SELECT order_id, user_id, items, total_amount, token_number, status, timestamp FROM orders"
        params: tuple = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY order_id DESC"
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            return [
                {
                    "order_id": r[0],
                    "user_id": r[1],
                    "items": json.loads(r[2]),
                    "total_amount": r[3],
                    "token_number": r[4],
                    "status": r[5],
                    "timestamp": r[6],
                }
                for r in rows
            ]

    def list_orders_for_user(self, user_id: str):
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT order_id, user_id, items, total_amount, token_number, status, timestamp
                FROM orders WHERE user_id = ? ORDER BY order_id DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
            return [
                {
                    "order_id": r[0],
                    "user_id": r[1],
                    "items": json.loads(r[2]),
                    "total_amount": r[3],
                    "token_number": r[4],
                    "status": r[5],
                    "timestamp": r[6],
                }
                for r in rows
            ]

    # Reporting
    def sales_by_item(self):
        counts: dict[str, int] = {}
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT items FROM orders")
            for (items_json,) in cur.fetchall():
                for it in json.loads(items_json):
                    name = it["item_name"]
                    qty = int(it.get("qty", 1))
                    counts[name] = counts.get(name, 0) + qty
        return counts

    def orders_per_hour(self):
        buckets = {h: 0 for h in range(24)}
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT timestamp FROM orders")
            for (ts,) in cur.fetchall():
                try:
                    dt_obj = dt.datetime.fromisoformat(ts)
                    buckets[dt_obj.hour] += 1
                except Exception:
                    pass
        return buckets

    def revenue_per_day(self):
        totals: dict[str, float] = {}
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT total_amount, timestamp FROM orders")
            for amount, ts in cur.fetchall():
                try:
                    d = dt.datetime.fromisoformat(ts).date().isoformat()
                except Exception:
                    d = ts.split("T")[0]
                totals[d] = round(totals.get(d, 0.0) + float(amount), 2)
        return totals

    # Offers Management
    def create_offer(self, offer_name: str, item_id: int | None, discount_type: str, 
                     discount_value: float, start_date: str | None = None, 
                     end_date: str | None = None, day_of_week: str | None = None, 
                     active: bool = True) -> int:
        """Create a new offer."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO offers(offer_name, item_id, discount_type, discount_value, 
                                 start_date, end_date, day_of_week, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (offer_name, item_id, discount_type, discount_value, start_date, 
                 end_date, day_of_week, 1 if active else 0),
            )
            conn.commit()
            return cur.lastrowid

    def list_offers(self):
        """List all offers with menu item names."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT o.offer_id, o.offer_name, o.item_id, m.item_name, o.discount_type,
                       o.discount_value, o.start_date, o.end_date, o.day_of_week, o.active
                FROM offers o
                LEFT JOIN menu m ON o.item_id = m.item_id
                ORDER BY o.offer_id DESC
                """
            )
            rows = cur.fetchall()
            return [
                {
                    "offer_id": r[0],
                    "offer_name": r[1],
                    "item_id": r[2],
                    "item_name": r[3] if r[3] else "All Items",
                    "discount_type": r[4],
                    "discount_value": r[5],
                    "start_date": r[6],
                    "end_date": r[7],
                    "day_of_week": r[8],
                    "active": bool(r[9]),
                }
                for r in rows
            ]

    def update_offer(self, offer_id: int, offer_name: str, item_id: int | None,
                     discount_type: str, discount_value: float, 
                     start_date: str | None = None, end_date: str | None = None,
                     day_of_week: str | None = None, active: bool = True) -> None:
        """Update an existing offer."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE offers 
                SET offer_name = ?, item_id = ?, discount_type = ?, discount_value = ?,
                    start_date = ?, end_date = ?, day_of_week = ?, active = ?
                WHERE offer_id = ?
                """,
                (offer_name, item_id, discount_type, discount_value, start_date, 
                 end_date, day_of_week, 1 if active else 0, offer_id),
            )
            conn.commit()

    def delete_offer(self, offer_id: int) -> None:
        """Delete an offer."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM offers WHERE offer_id = ?", (offer_id,))
            conn.commit()

    def get_active_offers_for_item(self, item_id: int) -> list:
        """Get all active offers applicable to a specific item at current date/time."""
        now = dt.datetime.now()
        current_date = now.date().isoformat()
        current_day = now.strftime("%a").upper()  # MON, TUE, WED, etc.
        
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT offer_id, offer_name, item_id, discount_type, discount_value,
                       start_date, end_date, day_of_week
                FROM offers
                WHERE active = 1
                AND (item_id = ? OR item_id IS NULL)
                AND (start_date IS NULL OR start_date <= ?)
                AND (end_date IS NULL OR end_date >= ?)
                AND (day_of_week IS NULL OR day_of_week = ?)
                """,
                (item_id, current_date, current_date, current_day),
            )
            rows = cur.fetchall()
            return [
                {
                    "offer_id": r[0],
                    "offer_name": r[1],
                    "item_id": r[2],
                    "discount_type": r[3],
                    "discount_value": r[4],
                    "start_date": r[5],
                    "end_date": r[6],
                    "day_of_week": r[7],
                }
                for r in rows
            ]


def export_orders_to_csv(db: DatabaseHandler, filepath: str = None) -> str:
    """Export all orders to CSV format.
    
    Args:
        db: DatabaseHandler instance
        filepath: Optional file path, if None will generate timestamped filename
        
    Returns:
        Path to the generated CSV file
    """
    ensure_assets_dir_exists()
    
    if filepath is None:
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(ASSETS_DIR, f"orders_export_{timestamp}.csv")
    
    orders = db.list_orders()
    
    # Prepare data for CSV
    csv_data = []
    for order in orders:
        # Expand items into separate rows
        items = order["items"]
        for idx, item in enumerate(items):
            row = {
                'Order ID': order["order_id"],
                'User ID': order["user_id"],
                'Token Number': order["token_number"],
                'Status': order["status"],
                'Date & Time': format_datetime(order["timestamp"]),
                'Item Name': item["item_name"],
                'Quantity': item.get("qty", 1),
                'Unit Price': f"{float(item['price']):.2f}",
                'Item Total': f"{float(item['price']) * item.get('qty', 1):.2f}",
                'Order Total': f"{order['total_amount']:.2f}",
            }
            csv_data.append(row)
    
    # Write CSV file
    if csv_data:
        fieldnames = ['Order ID', 'User ID', 'Token Number', 'Status', 'Date & Time', 
                     'Item Name', 'Quantity', 'Unit Price', 'Item Total', 'Order Total']
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_data)
    else:
        # Create empty CSV with headers
        fieldnames = ['Order ID', 'User ID', 'Token Number', 'Status', 'Date & Time', 
                     'Item Name', 'Quantity', 'Unit Price', 'Item Total', 'Order Total']
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
    
    return filepath


def export_orders_to_excel(db: DatabaseHandler, filepath: str = None) -> str:
    """Export all orders to Excel format using pandas.
    
    Args:
        db: DatabaseHandler instance
        filepath: Optional file path, if None will generate timestamped filename
        
    Returns:
        Path to the generated Excel file
    """
    if not pandas_available:
        raise ImportError("pandas library is not installed. Install it with: pip install pandas openpyxl")
    
    ensure_assets_dir_exists()
    
    if filepath is None:
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(ASSETS_DIR, f"orders_export_{timestamp}.xlsx")
    
    orders = db.list_orders()
    
    # Prepare data for Excel
    excel_data = []
    for order in orders:
        # Expand items into separate rows
        items = order["items"]
        for item in items:
            row = {
                'Order ID': order["order_id"],
                'User ID': order["user_id"],
                'Token Number': order["token_number"],
                'Status': order["status"],
                'Date & Time': format_datetime(order["timestamp"]),
                'Item Name': item["item_name"],
                'Quantity': item.get("qty", 1),
                'Unit Price': float(item['price']),
                'Item Total': float(item['price']) * item.get('qty', 1),
                'Order Total': float(order['total_amount']),
            }
            excel_data.append(row)
    
    # Create DataFrame and export to Excel
    if excel_data:
        df = pd.DataFrame(excel_data)
    else:
        # Create empty DataFrame with headers
        df = pd.DataFrame(columns=['Order ID', 'User ID', 'Token Number', 'Status', 'Date & Time', 
                                   'Item Name', 'Quantity', 'Unit Price', 'Item Total', 'Order Total'])
    
    # Write to Excel with formatting
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Orders', index=False)
        
        # Get the workbook and worksheet for formatting
        workbook = writer.book
        worksheet = writer.sheets['Orders']
        
        # Auto-adjust column widths
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # Format header row
        from openpyxl.styles import Font, PatternFill, Alignment
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        
        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
    
    return filepath


class Order:
    """Simple helper to create orders and expose fields."""

    def __init__(self, db: DatabaseHandler) -> None:
        self.db = db

    def create(self, user_id: str, cart_items: list[dict]) -> int:
        total = sum(float(i["price"]) * int(i["qty"]) for i in cart_items)
        return self.db.create_order(user_id=user_id, items=cart_items, total_amount=round(total, 2))


class LoginWindow(ttk.Frame):
    def __init__(self, parent, app, db: DatabaseHandler):
        super().__init__(parent)
        self.app = app
        self.db = db
        # Ensure dark background on this root frame
        try:
            self.configure(style="Panel.TFrame")
        except Exception:
            pass
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        
        # Title
        title_frame = ttk.Frame(self, style="Panel.TFrame")
        title_frame.grid(row=0, column=0, sticky="ew", pady=(50, 30))
        title_frame.columnconfigure(0, weight=1)
        title = ttk.Label(title_frame, text="🍽️  Canteen Payment System", style="Title.TLabel")
        title.grid(row=0, column=0, pady=10)
        subtitle = ttk.Label(title_frame, text="Sign in to continue", style="Subtle.TLabel")
        subtitle.grid(row=1, column=0, pady=(0, 10))

        # Card container for form
        card = ttk.Frame(self, style="Card.TFrame")
        card.grid(row=1, column=0, padx=40, pady=20, sticky="nsew")
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)
        
        # Form content
        form = ttk.Frame(card, style="Card.TFrame")
        form.grid(row=0, column=0, padx=40, pady=30, sticky="")
        form.columnconfigure(1, weight=1, minsize=280)

        # Name field
        name_label = ttk.Label(form, text="Name", style="FormLabel.TLabel")
        name_label.grid(row=0, column=0, sticky="w", padx=(0, 15), pady=(0, 8))
        self.name_var = tk.StringVar()
        name_entry = ttk.Entry(form, textvariable=self.name_var, width=30)
        name_entry.grid(row=0, column=1, sticky="ew", pady=(0, 20), ipady=6)

        # ID field
        id_label = ttk.Label(form, text="ID", style="FormLabel.TLabel")
        id_label.grid(row=1, column=0, sticky="w", padx=(0, 15), pady=(0, 8))
        self.id_var = tk.StringVar()
        id_entry = ttk.Entry(form, textvariable=self.id_var, width=30)
        id_entry.grid(row=1, column=1, sticky="ew", pady=(0, 20), ipady=6)

        # Role dropdown
        role_label = ttk.Label(form, text="Role", style="FormLabel.TLabel")
        role_label.grid(row=2, column=0, sticky="w", padx=(0, 15), pady=(0, 8))
        self.role_var = tk.StringVar(value="Student")
        role_cb = ttk.Combobox(form, textvariable=self.role_var, 
                               values=["Student", "Attendant", "Manager"], 
                               state="readonly", width=27)
        role_cb.grid(row=2, column=1, sticky="ew", pady=(0, 30), ipady=6)

        # Buttons
        btns = ttk.Frame(form, style="Card.TFrame")
        btns.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        btns.columnconfigure(0, weight=1, uniform="btn")
        btns.columnconfigure(1, weight=1, uniform="btn")
        
        login_btn = ttk.Button(btns, text="→ Login", style="Primary.TButton", command=self._login)
        login_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        
        register_btn = ttk.Button(btns, text="＋ Register", style="Accent.TButton", command=self._register)
        register_btn.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        
        # Bind Enter key to login
        name_entry.bind("<Return>", lambda e: self._login())
        id_entry.bind("<Return>", lambda e: self._login())
        role_cb.bind("<Return>", lambda e: self._login())

    def _login(self):
        name = self.name_var.get().strip()
        uid = self.id_var.get().strip()
        role = self.role_var.get().strip()
        if not name or not uid:
            messagebox.showwarning("Missing", "Enter name and ID")
            return
        user = self.db.get_user_by_name_and_id(name, uid)
        if not user:
            messagebox.showerror("Not found", "User not found. Please register.")
            return
        if user["role"].lower() != role.lower():
            messagebox.showerror("Role mismatch", f"Account exists with role {user['role']}.")
            return
        self.app.set_user(user)

    def _register(self):
        name = self.name_var.get().strip()
        uid = self.id_var.get().strip()
        role = self.role_var.get().strip()
        if not name or not uid:
            messagebox.showwarning("Missing", "Enter name and ID")
            return
        existing = self.db.get_user(uid)
        if existing:
            messagebox.showerror("Exists", "User ID already exists. Use another ID.")
            return
        self.db.create_user(uid, name, role)
        messagebox.showinfo("Registered", "Registration successful. You can now login.")


class StudentDashboard(ttk.Frame):
    def __init__(self, parent, app, db: DatabaseHandler):
        super().__init__(parent)
        self.app = app
        self.db = db
        self.cart: dict[int, dict] = {}
        self.notebook = ttk.Notebook(self)
        self.menu_tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.orders_tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(self.menu_tab, text="Menu")
        self.notebook.add(self.orders_tab, text="My Orders")
        self.notebook.pack(fill="both", expand=True)

        self._build_menu_tab()
        self._build_orders_tab()

    def _build_menu_tab(self):
        left = ttk.Frame(self.menu_tab, style="Panel.TFrame")
        right = ttk.Frame(self.menu_tab, style="Panel.TFrame")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Menu Tree with scrollbar
        menu_frame = ttk.Frame(left)
        menu_frame.pack(fill=tk.BOTH, expand=True)
        
        menu_scroll_y = ttk.Scrollbar(menu_frame, orient="vertical")
        menu_scroll_x = ttk.Scrollbar(menu_frame, orient="horizontal")
        
        columns = ("item", "price", "available")
        self.menu_tree = ttk.Treeview(menu_frame, columns=columns, show="headings", height=12,
                                      yscrollcommand=menu_scroll_y.set, xscrollcommand=menu_scroll_x.set)
        self.menu_tree.heading("item", text="Item")
        self.menu_tree.heading("price", text="Price")
        self.menu_tree.heading("available", text="Available")
        self.menu_tree.column("item", width=180)
        self.menu_tree.column("price", width=80, anchor="e")
        self.menu_tree.column("available", width=80, anchor="center")
        
        menu_scroll_y.config(command=self.menu_tree.yview)
        menu_scroll_x.config(command=self.menu_tree.xview)
        
        self.menu_tree.grid(row=0, column=0, sticky="nsew")
        menu_scroll_y.grid(row=0, column=1, sticky="ns")
        menu_scroll_x.grid(row=1, column=0, sticky="ew")
        menu_frame.columnconfigure(0, weight=1)
        menu_frame.rowconfigure(0, weight=1)

        ctrl = ttk.Frame(left)
        ctrl.pack(fill=tk.X, pady=6)
        ttk.Label(ctrl, text="Qty").pack(side=tk.LEFT)
        self.qty_var = tk.IntVar(value=1)
        qty = ttk.Spinbox(ctrl, from_=1, to=20, textvariable=self.qty_var, width=5)
        qty.pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl, text="Add to Cart", command=self._add_to_cart).pack(side=tk.LEFT, padx=6)
        ttk.Button(ctrl, text="Refresh Menu", command=self._load_menu).pack(side=tk.LEFT, padx=6)

        # Cart with scrollbar
        ttk.Label(right, text="Cart", style="Title.TLabel").pack(anchor="w")
        cart_frame = ttk.Frame(right)
        cart_frame.pack(fill=tk.BOTH, expand=True)
        
        cart_scroll_y = ttk.Scrollbar(cart_frame, orient="vertical")
        cart_scroll_x = ttk.Scrollbar(cart_frame, orient="horizontal")
        
        self.cart_tree = ttk.Treeview(cart_frame, columns=("item", "qty", "price", "discount", "total"), show="headings", height=10,
                                      yscrollcommand=cart_scroll_y.set, xscrollcommand=cart_scroll_x.set)
        for col, text, anchor, width in [
            ("item", "Item", "w", 150),
            ("qty", "Qty", "center", 50),
            ("price", "Price", "e", 80),
            ("discount", "Discount", "w", 120),
            ("total", "Total", "e", 90),
        ]:
            self.cart_tree.heading(col, text=text)
            self.cart_tree.column(col, anchor=anchor, width=width)
        
        cart_scroll_y.config(command=self.cart_tree.yview)
        cart_scroll_x.config(command=self.cart_tree.xview)
        
        self.cart_tree.grid(row=0, column=0, sticky="nsew")
        cart_scroll_y.grid(row=0, column=1, sticky="ns")
        cart_scroll_x.grid(row=1, column=0, sticky="ew")
        cart_frame.columnconfigure(0, weight=1)
        cart_frame.rowconfigure(0, weight=1)

        total_bar = ttk.Frame(right)
        total_bar.pack(fill=tk.X, pady=6)
        self.total_var = tk.StringVar(value="0.00")
        ttk.Label(total_bar, text="Total: ").pack(side=tk.LEFT)
        ttk.Label(total_bar, textvariable=self.total_var, font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        ttk.Button(total_bar, text="₹ Pay", style="Primary.TButton", command=self._checkout).pack(side=tk.RIGHT)
        ttk.Button(total_bar, text="⟲ Clear", style="Ghost.TButton", command=self._clear_cart).pack(side=tk.RIGHT, padx=6)

        self._load_menu()

    def _build_orders_tab(self):
        top = ttk.Frame(self.orders_tab, style="Panel.TFrame")
        top.pack(fill=tk.X, pady=6)
        ttk.Button(top, text="⟳ Refresh", style="Ghost.TButton", command=self._load_orders).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="📄 Download Receipt", style="Accent.TButton", command=self._download_receipt).pack(side=tk.LEFT, padx=6)
        # Add logout button for easy visibility
        ttk.Button(top, text="🚪 Logout", style="Danger.TButton", command=self.app._logout).pack(side=tk.RIGHT, padx=6)
        
        # Orders tree with scrollbar
        orders_frame = ttk.Frame(self.orders_tab, style="Panel.TFrame")
        orders_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        orders_scroll_y = ttk.Scrollbar(orders_frame, orient="vertical")
        orders_scroll_x = ttk.Scrollbar(orders_frame, orient="horizontal")
        
        self.orders_tree = ttk.Treeview(
            orders_frame,
            columns=("order", "token", "status", "total", "time"),
            show="headings",
            height=14,
            yscrollcommand=orders_scroll_y.set,
            xscrollcommand=orders_scroll_x.set
        )
        for col, text, anchor, width in [
            ("order", "Order ID", "center", 80),
            ("token", "Token", "center", 70),
            ("status", "Status", "center", 90),
            ("total", "Total", "center", 90),
            ("time", "Date & Time", "center", 200),
        ]:
            self.orders_tree.heading(col, text=text)
            self.orders_tree.column(col, anchor=anchor, width=width)
        
        orders_scroll_y.config(command=self.orders_tree.yview)
        orders_scroll_x.config(command=self.orders_tree.xview)
        
        self.orders_tree.grid(row=0, column=0, sticky="nsew")
        orders_scroll_y.grid(row=0, column=1, sticky="ns")
        orders_scroll_x.grid(row=1, column=0, sticky="ew")
        orders_frame.columnconfigure(0, weight=1)
        orders_frame.rowconfigure(0, weight=1)
        
        # Bind double-click to download receipt for completed orders
        self.orders_tree.bind("<Double-1>", lambda e: self._download_receipt())

    def on_show(self):
        self._load_orders()

    def _load_menu(self):
        for i in self.menu_tree.get_children():
            self.menu_tree.delete(i)
        for m in self.db.list_menu():
            avail = "Yes" if m["available"] else "No"
            self.menu_tree.insert("", tk.END, iid=str(m["item_id"]), values=(m["item_name"], f"{m['price']:.2f}", avail))
        # zebra
        self._zebra_tree(self.menu_tree)

    def _add_to_cart(self):
        selected = self.menu_tree.focus()
        if not selected:
            messagebox.showwarning("Select", "Select a menu item")
            return
        qty = int(self.qty_var.get())
        vals = self.menu_tree.item(selected, "values")
        item_id = int(selected)
        item_name = vals[0]
        original_price = float(vals[1])
        
        # Check for active offers
        offers = self.db.get_active_offers_for_item(item_id)
        discounted_price, offer_desc = calculate_discounted_price(original_price, offers)
        
        existing = self.cart.get(item_id)
        if existing:
            existing["qty"] += qty
            # Recalculate discount in case offers changed
            offers = self.db.get_active_offers_for_item(item_id)
            discounted_price, offer_desc = calculate_discounted_price(original_price, offers)
            existing["price"] = discounted_price
            existing["original_price"] = original_price
            existing["offer_desc"] = offer_desc
        else:
            self.cart[item_id] = {
                "item_id": item_id, 
                "item_name": item_name, 
                "price": discounted_price,
                "original_price": original_price,
                "offer_desc": offer_desc,
                "qty": qty
            }
        self._refresh_cart()

    def _refresh_cart(self):
        for i in self.cart_tree.get_children():
            self.cart_tree.delete(i)
        total = 0.0
        for it in self.cart.values():
            # Recalculate discount in case offers changed
            offers = self.db.get_active_offers_for_item(it["item_id"])
            original_price = it.get("original_price", it["price"])
            discounted_price, offer_desc = calculate_discounted_price(original_price, offers)
            it["price"] = discounted_price
            it["original_price"] = original_price
            it["offer_desc"] = offer_desc
            
            line_total = float(it["price"]) * int(it["qty"])
            total += line_total
            
            # Format discount display
            discount_display = offer_desc if offer_desc else "-"
            
            self.cart_tree.insert(
                "", tk.END, iid=str(it["item_id"]), 
                values=(
                    it["item_name"], 
                    it["qty"], 
                    f"{it['price']:.2f}", 
                    discount_display,
                    f"{line_total:.2f}"
                )
            )
        self.total_var.set(f"{total:.2f}")
        self._zebra_tree(self.cart_tree)

    def _clear_cart(self):
        self.cart.clear()
        self._refresh_cart()

    def _checkout(self):
        if not self.cart:
            messagebox.showwarning("Empty", "Your cart is empty")
            return
        user = self.app.current_user
        if not user:
            messagebox.showerror("Not logged in", "Please login again")
            return
        items = list(self.cart.values())
        order_id = Order(self.db).create(user_id=user["user_id"], cart_items=items)
        total = float(self.total_var.get())
        self._show_qr_modal(order_id, total)
        self._clear_cart()
        self.notebook.select(self.orders_tab)
        self._load_orders()

    def _show_qr_modal(self, order_id: int, amount: float):
        if qrcode is None:
            messagebox.showinfo("QR", "Install 'qrcode' to generate QR codes: pip install qrcode[pil]")
            return
        ensure_assets_dir_exists()
        upi_payload = f"upi://pay?pa={UPI_ID}&am={amount:.2f}&tn=Canteen%20Order%20{order_id}"
        img = qrcode.make(upi_payload)
        qr_path = os.path.join(ASSETS_DIR, f"qr_order_{order_id}.png")
        img.save(qr_path)

        top = tk.Toplevel(self)
        top.title("Scan to Pay")
        top.geometry("360x420")
        ttk.Label(top, text=f"Order #{order_id} | Amount: Rs {amount:.2f}", font=("Segoe UI", 10, "bold")).pack(pady=8)

        try:
            from PIL import Image, ImageTk  # optional for better sizing
            im = Image.open(qr_path).resize((300, 300))
            photo = ImageTk.PhotoImage(im)
        except Exception:
            photo = tk.PhotoImage(file=qr_path)

        lbl = ttk.Label(top, image=photo)
        lbl.image = photo
        lbl.pack(pady=6)

        ttk.Button(top, text="I have paid", command=top.destroy).pack(pady=10)

    def _load_orders(self):
        user = self.app.current_user
        if not user:
            return
        for i in self.orders_tree.get_children():
            self.orders_tree.delete(i)
        data = self.db.list_orders_for_user(user["user_id"]) or []
        current_first = sorted(data, key=lambda d: (d["status"] != "PLACED", -d["order_id"]))
        for o in current_first:
            # Format the timestamp to a user-friendly format
            formatted_time = format_datetime(o["timestamp"])
            self.orders_tree.insert(
                "",
                tk.END,
                iid=str(o["order_id"]),
                values=(o["order_id"], o["token_number"], o["status"], f"{o['total_amount']:.2f}", formatted_time),
            )
        self._zebra_tree(self.orders_tree)

    def _download_receipt(self):
        """Download PDF receipt for the selected completed order."""
        sel = self.orders_tree.focus()
        if not sel:
            messagebox.showwarning("Select Order", "Please select an order to download receipt")
            return
        
        order_id = int(sel)
        user = self.app.current_user
        if not user:
            messagebox.showerror("Error", "User session expired. Please login again.")
            return
        
        # Get order data
        orders = self.db.list_orders_for_user(user["user_id"])
        order_data = None
        for o in orders:
            if o["order_id"] == order_id:
                order_data = o
                break
        
        if not order_data:
            messagebox.showerror("Error", "Order not found")
            return
        
        # Check if order is completed
        if order_data["status"] != "COMPLETED":
            messagebox.showwarning("Order Not Completed", 
                                 f"Receipt can only be downloaded for completed orders.\n"
                                 f"Current status: {order_data['status']}")
            return
        
        # Check if reportlab is available
        if not reportlab_available:
            messagebox.showerror("Library Missing", 
                               "PDF generation requires 'reportlab' library.\n"
                               "Install it with: pip install reportlab")
            return
        
        try:
            # Check for QR code
            qr_path = os.path.join(ASSETS_DIR, f"qr_order_{order_id}.png")
            if not os.path.exists(qr_path):
                qr_path = None
            
            # Generate PDF receipt
            pdf_path = generate_receipt_pdf(order_data, user, qr_path)
            
            # Open the PDF file
            try:
                if platform.system() == 'Windows':
                    os.startfile(pdf_path)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.call(['open', pdf_path])
                else:  # Linux
                    subprocess.call(['xdg-open', pdf_path])
            except Exception:
                # If auto-open fails, just show success message
                pass
            
            messagebox.showinfo("Receipt Generated", 
                              f"Receipt downloaded successfully!\n\n"
                              f"File: {os.path.basename(pdf_path)}\n"
                              f"Location: {ASSETS_DIR}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate receipt:\n{str(e)}")

    def _zebra_tree(self, tree: ttk.Treeview) -> None:
        tree.tag_configure("odd", background=PALETTE["row_alt"]) 
        for idx, iid in enumerate(tree.get_children("")):
            tree.item(iid, tags=("odd",) if idx % 2 else ())


class AttendantDashboard(ttk.Frame):
    def __init__(self, parent, app, db: DatabaseHandler):
        super().__init__(parent)
        self.app = app
        self.db = db
        self._build()

    def _build(self):
        top = ttk.Frame(self, style="Panel.TFrame")
        top.pack(fill=tk.X, pady=6)
        ttk.Button(top, text="⟳ Refresh", style="Ghost.TButton", command=self._refresh).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="✓ Ready", style="Accent.TButton", command=lambda: self._update_status("READY")).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="✔ Completed", style="Primary.TButton", command=lambda: self._update_status("COMPLETED")).pack(side=tk.LEFT, padx=6)
        # Add logout button for easy visibility
        ttk.Button(top, text="🚪 Logout", style="Danger.TButton", command=self.app._logout).pack(side=tk.RIGHT, padx=6)

        # Orders tree with scrollbar
        orders_frame = ttk.Frame(self, style="Panel.TFrame")
        orders_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        orders_scroll_y = ttk.Scrollbar(orders_frame, orient="vertical")
        orders_scroll_x = ttk.Scrollbar(orders_frame, orient="horizontal")
        
        columns = ("order", "token", "items", "total", "status", "time")
        self.orders_tree = ttk.Treeview(orders_frame, columns=columns, show="headings", height=16,
                                        yscrollcommand=orders_scroll_y.set, xscrollcommand=orders_scroll_x.set)
        for col, text, anchor, width in [
            ("order", "Order ID", "center", 70),
            ("token", "Token", "center", 70),
            ("items", "Items", "w", 260),
            ("total", "Total", "center", 90),
            ("status", "Status", "center", 90),
            ("time", "Date & Time", "center", 200),
        ]:
            self.orders_tree.heading(col, text=text)
            self.orders_tree.column(col, anchor=anchor, width=width)
        
        orders_scroll_y.config(command=self.orders_tree.yview)
        orders_scroll_x.config(command=self.orders_tree.xview)
        
        self.orders_tree.grid(row=0, column=0, sticky="nsew")
        orders_scroll_y.grid(row=0, column=1, sticky="ns")
        orders_scroll_x.grid(row=1, column=0, sticky="ew")
        orders_frame.columnconfigure(0, weight=1)
        orders_frame.rowconfigure(0, weight=1)

        menuf = ttk.Labelframe(self, text="Menu Management")
        menuf.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        # Treeview with scrollbar
        tree_frame = ttk.Frame(menuf)
        tree_frame.grid(row=0, column=0, columnspan=10, sticky="nsew", padx=6, pady=6)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        scrollbar_y = ttk.Scrollbar(tree_frame, orient="vertical")
        scrollbar_x = ttk.Scrollbar(tree_frame, orient="horizontal")
        
        self.menu_tree = ttk.Treeview(tree_frame, columns=("name", "price", "avail"), show="headings", height=8,
                                      yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        self.menu_tree.heading("name", text="Name")
        self.menu_tree.heading("price", text="Price")
        self.menu_tree.heading("avail", text="Available")
        self.menu_tree.column("name", width=180)
        self.menu_tree.column("price", width=80, anchor="center")
        self.menu_tree.column("avail", width=90, anchor="center")
        
        scrollbar_y.config(command=self.menu_tree.yview)
        scrollbar_x.config(command=self.menu_tree.xview)
        
        self.menu_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        
        # Bind selection to populate form fields
        self.menu_tree.bind("<<TreeviewSelect>>", self._on_menu_select)

        # Input row with buttons beside
        ttk.Label(menuf, text="Name").grid(row=1, column=0, padx=4, pady=4, sticky="e")
        self.m_name = tk.StringVar()
        ttk.Entry(menuf, textvariable=self.m_name, width=18).grid(row=1, column=1, padx=4, pady=4)
        ttk.Label(menuf, text="Price").grid(row=1, column=2, padx=4, pady=4, sticky="e")
        self.m_price = tk.StringVar()
        ttk.Entry(menuf, textvariable=self.m_price, width=10).grid(row=1, column=3, padx=4, pady=4)
        self.m_avail = tk.BooleanVar(value=True)
        ttk.Checkbutton(menuf, text="Available", variable=self.m_avail).grid(row=1, column=4, padx=4, pady=4)
        
        # Buttons beside input fields
        ttk.Button(menuf, text="＋ Add", style="Accent.TButton", command=self._add_menu).grid(row=1, column=5, padx=2, pady=4)
        ttk.Button(menuf, text="✏️ Update", style="Primary.TButton", command=self._update_item).grid(row=1, column=6, padx=2, pady=4)
        ttk.Button(menuf, text="Update Price", style="Primary.TButton", command=self._update_price).grid(row=1, column=7, padx=2, pady=4)
        ttk.Button(menuf, text="Toggle", style="Accent.TButton", command=self._toggle_availability).grid(row=1, column=8, padx=2, pady=4)
        ttk.Button(menuf, text="Delete", style="Danger.TButton", command=self._delete_menu).grid(row=1, column=9, padx=2, pady=4)
        
        # Second row for additional buttons
        ttk.Button(menuf, text="⟲ Clear", style="Ghost.TButton", command=self._clear_form).grid(row=2, column=1, padx=2, pady=4)
        ttk.Button(menuf, text="⟳ Refresh", style="Ghost.TButton", command=self._load_menu).grid(row=2, column=2, padx=2, pady=4)
        
        # Configure grid weights
        menuf.columnconfigure(0, weight=0)
        menuf.columnconfigure(1, weight=1)
        menuf.rowconfigure(0, weight=1)
        
        # Load menu immediately when dashboard is built
        self._load_menu()

    def on_show(self):
        self._refresh()
        self._load_menu()

    def _refresh(self):
        for i in self.orders_tree.get_children():
            self.orders_tree.delete(i)
        orders = self.db.list_orders()  # all orders, latest first
        for o in orders:
            items_str = ", ".join(f"{it['item_name']} x{it['qty']}" for it in o["items"])[:80]
            # Format the timestamp to a user-friendly format
            formatted_time = format_datetime(o["timestamp"])
            self.orders_tree.insert(
                "",
                tk.END,
                iid=str(o["order_id"]),
                values=(o["order_id"], o["token_number"], items_str, f"{o['total_amount']:.2f}", o["status"], formatted_time),
            )
        self._zebra_tree(self.orders_tree)

    def _update_status(self, status: str):
        sel = self.orders_tree.focus()
        if not sel:
            messagebox.showwarning("Select", "Select an order")
            return
        self.db.update_order_status(int(sel), status)
        self._refresh()

    def _load_menu(self):
        for i in self.menu_tree.get_children():
            self.menu_tree.delete(i)
        menu_items = self.db.list_menu()
        # If menu is empty, seed default items
        if not menu_items:
            # Re-seed menu if empty
            default_items = [
                ("Masala Dosa", 50.0, 1),
                ("Idli Sambar", 35.0, 1),
                ("Veg Sandwich", 45.0, 1),
                ("Pav Bhaji", 70.0, 1),
                ("Chole Bhature", 80.0, 1),
                ("Tea", 10.0, 1),
                ("Coffee", 15.0, 1),
            ]
            for name, price, avail in default_items:
                try:
                    self.db.add_menu_item(name, price, bool(avail))
                except sqlite3.IntegrityError:
                    pass  # Item already exists
            menu_items = self.db.list_menu()
        for m in menu_items:
            self.menu_tree.insert("", tk.END, iid=str(m["item_id"]), values=(m["item_name"], f"{m['price']:.2f}", "Yes" if m["available"] else "No"))
        self._zebra_tree(self.menu_tree)
    
    def _on_menu_select(self, event):
        """Populate form fields when a menu item is selected."""
        sel = self.menu_tree.focus()
        if sel:
            values = self.menu_tree.item(sel, "values")
            self.m_name.set(values[0])  # Name
            self.m_price.set(values[1])  # Price
            # Set availability checkbox based on "Yes"/"No"
            self.m_avail.set(values[2] == "Yes")
    
    def _clear_form(self):
        """Clear all form fields."""
        self.m_name.set("")
        self.m_price.set("")
        self.m_avail.set(True)
        # Clear selection in tree
        for item in self.menu_tree.selection():
            self.menu_tree.selection_remove(item)

    def _add_menu(self):
        try:
            name = self.m_name.get().strip()
            price = float(self.m_price.get())
            avail = bool(self.m_avail.get())
            if not name:
                raise ValueError("Name required")
        except Exception as e:
            messagebox.showerror("Invalid", f"{e}")
            return
        try:
            self.db.add_menu_item(name, price, avail)
            self._load_menu()
            self.m_name.set("")
            self.m_price.set("")
            self.m_avail.set(True)
        except sqlite3.IntegrityError:
            messagebox.showerror("Exists", "Item with this name already exists")

    def _update_item(self):
        """Update both price and availability of the selected menu item."""
        sel = self.menu_tree.focus()
        if not sel:
            messagebox.showwarning("Select", "Select a menu item to update")
            return
        
        # Get current values
        current_values = self.menu_tree.item(sel, "values")
        current_name = current_values[0]
        
        # Get new price from input field
        new_price_str = self.m_price.get().strip()
        if not new_price_str:
            messagebox.showwarning("Missing", "Enter a price in the Price field")
            return
        
        try:
            new_price = float(new_price_str)
            if new_price < 0:
                raise ValueError("Price cannot be negative")
        except ValueError as e:
            messagebox.showerror("Invalid Price", f"Please enter a valid price.\n{str(e)}")
            return
        
        # Get new availability from checkbox
        new_avail = bool(self.m_avail.get())
        status_text = "available" if new_avail else "unavailable"
        
        # Update the item
        self.db.update_menu_item(int(sel), current_name, new_price, new_avail)
        messagebox.showinfo("Updated", f"'{current_name}' updated:\nPrice: Rs {new_price:.2f}\nStatus: {status_text}")
        self._load_menu()
        # Clear form fields
        self.m_name.set("")
        self.m_price.set("")
        self.m_avail.set(True)

    def _update_price(self):
        """Update the price of the selected menu item."""
        sel = self.menu_tree.focus()
        if not sel:
            messagebox.showwarning("Select", "Select a menu item to update")
            return
        
        # Get current values
        current_values = self.menu_tree.item(sel, "values")
        current_name = current_values[0]
        current_price = current_values[1]
        current_avail = current_values[2] == "Yes"
        
        # Get new price from input field
        new_price_str = self.m_price.get().strip()
        if not new_price_str:
            messagebox.showwarning("Missing", "Enter a new price in the Price field")
            return
        
        try:
            new_price = float(new_price_str)
            if new_price < 0:
                raise ValueError("Price cannot be negative")
        except ValueError as e:
            messagebox.showerror("Invalid Price", f"Please enter a valid price.\n{str(e)}")
            return
        
        # Update the item
        self.db.update_menu_item(int(sel), current_name, new_price, current_avail)
        messagebox.showinfo("Updated", f"Price updated to Rs {new_price:.2f}")
        self._load_menu()
        # Clear form fields
        self.m_name.set("")
        self.m_price.set("")
        self.m_avail.set(True)
    
    def _toggle_availability(self):
        """Toggle the availability status of the selected menu item."""
        sel = self.menu_tree.focus()
        if not sel:
            messagebox.showwarning("Select", "Select a menu item to toggle availability")
            return
        
        # Get current values
        current_values = self.menu_tree.item(sel, "values")
        current_name = current_values[0]
        current_price = float(current_values[1])
        current_avail = current_values[2] == "Yes"
        
        # Toggle availability
        new_avail = not current_avail
        status_text = "available" if new_avail else "unavailable"
        
        # Update the item
        self.db.update_menu_item(int(sel), current_name, current_price, new_avail)
        messagebox.showinfo("Updated", f"'{current_name}' is now {status_text}")
        self._load_menu()
        # Clear form fields
        self.m_name.set("")
        self.m_price.set("")
        self.m_avail.set(True)

    def _delete_menu(self):
        sel = self.menu_tree.focus()
        if not sel:
            messagebox.showwarning("Select", "Select a menu item")
            return
        if messagebox.askyesno("Confirm", "Delete selected item?"):
            self.db.delete_menu_item(int(sel))
            self._load_menu()
    
    def _zebra_tree(self, tree: ttk.Treeview) -> None:
        """Apply zebra striping to treeview rows."""
        tree.tag_configure("odd", background=PALETTE["row_alt"]) 
        tree.tag_configure("even", background=PALETTE.get("row_alt2", PALETTE["panel"])) 
        for idx, iid in enumerate(tree.get_children("")):
            tree.item(iid, tags=("odd",) if idx % 2 else ("even",))


class GraphGenerator:
    def __init__(self, db: DatabaseHandler):
        self.db = db

    def most_selling_items_figure(self) -> Figure:
        counts = self.db.sales_by_item()
        items = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
        labels = [i[0] for i in items]
        values = [i[1] for i in items]
        fig = Figure(figsize=(5.5, 3.0), dpi=100)
        ax = fig.add_subplot(111)
        palette_keys = ["chart_1","chart_2","chart_3","chart_4","chart_5","chart_6","chart_7","chart_8"]
        colors = [PALETTE.get(palette_keys[i % len(palette_keys)], PALETTE["primary"]) for i in range(len(labels))]
        ax.bar(labels, values, color=colors)
        ax.set_title("Top Selling Items", color=PALETTE["text"], fontsize=12, fontweight="bold", pad=10)
        ax.set_ylabel("Qty", color=PALETTE["text"])
        ax.tick_params(axis='x', rotation=30, colors=PALETTE["text"])
        ax.tick_params(axis='y', colors=PALETTE["text"])
        fig.tight_layout()
        return fig

    def orders_per_time_figure(self) -> Figure:
        buckets = self.db.orders_per_hour()
        hours = list(range(24))
        values = [buckets.get(h, 0) for h in hours]
        fig = Figure(figsize=(5.5, 2.5), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(hours, values, marker="o", color=PALETTE.get("chart_3", PALETTE["accent"]), linewidth=2, markersize=6)
        ax.set_title("Orders by Hour", color=PALETTE["text"], fontsize=12, fontweight="bold", pad=10)
        ax.set_xlabel("Hour", color=PALETTE["text"])
        ax.set_ylabel("Orders", color=PALETTE["text"])
        ax.set_xticks(list(range(0, 24, 2)))
        ax.tick_params(colors=PALETTE["text"])
        fig.tight_layout()
        return fig

    def revenue_per_day_figure(self) -> Figure:
        totals = self.db.revenue_per_day()
        labels = sorted(totals.keys())[-10:]
        values = [totals[d] for d in labels]
        fig = Figure(figsize=(5.5, 2.5), dpi=100)
        ax = fig.add_subplot(111)
        ax.bar(labels, values, color=PALETTE.get("chart_4", PALETTE["primary_alt"]))
        ax.set_title("Revenue per Day (Last 10)", color=PALETTE["text"], fontsize=12, fontweight="bold", pad=10)
        ax.set_ylabel("Rs", color=PALETTE["text"])
        ax.tick_params(axis='x', rotation=30, colors=PALETTE["text"])
        ax.tick_params(axis='y', colors=PALETTE["text"])
        fig.tight_layout()
        return fig


class ManagerDashboard(ttk.Frame):
    def __init__(self, parent, app, db: DatabaseHandler):
        super().__init__(parent)
        self.app = app
        self.db = db
        self.graphs = GraphGenerator(db)
        self._build()

    def _build(self):
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Dashboard tab
        self.dashboard_tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(self.dashboard_tab, text="📊 Dashboard")
        self._build_dashboard_tab()
        
        # Offers Management tab
        self.offers_tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(self.offers_tab, text="🎁 Offers & Discounts")
        self._build_offers_tab()
    
    def _build_dashboard_tab(self):
        stats = ttk.Frame(self.dashboard_tab, style="Panel.TFrame")
        stats.pack(fill=tk.X, padx=8, pady=8)
        self.pending_var = tk.StringVar(value="0")
        self.completed_var = tk.StringVar(value="0")
        self.revenue_var = tk.StringVar(value="0.00")
        for i in range(3):
            stats.columnconfigure(i, weight=1)
        self._badge(stats, 0, "Pending", self.pending_var)
        self._badge(stats, 1, "Completed", self.completed_var)
        self._badge(stats, 2, "Revenue (sum)", self.revenue_var)

        btns = ttk.Frame(self.dashboard_tab, style="Panel.TFrame")
        btns.pack(fill=tk.X, padx=8)
        ttk.Button(btns, text="⟳ Refresh", style="Ghost.TButton", command=self._refresh_all).pack(side=tk.LEFT)
        ttk.Button(btns, text="📊 Export to CSV", style="Accent.TButton", command=self._export_csv).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="📈 Export to Excel", style="Primary.TButton", command=self._export_excel).pack(side=tk.LEFT, padx=6)
        # Add logout button for easy visibility
        ttk.Button(btns, text="🚪 Logout", style="Danger.TButton", command=self.app._logout).pack(side=tk.RIGHT, padx=6)

        self.fig_frame = ttk.Frame(self.dashboard_tab, style="Panel.TFrame")
        self.fig_frame.pack(fill=tk.BOTH, expand=True)
        self._render_figures()

    def _badge(self, parent, col, title, var):
        box = ttk.Labelframe(parent, text=title)
        box.grid(row=0, column=col, sticky="ew", padx=6)
        ttk.Label(box, textvariable=var, font=("Segoe UI", 14, "bold")).pack(padx=10, pady=10)

    def _render_figures(self):
        for w in self.fig_frame.winfo_children():
            w.destroy()
        if FigureCanvasTkAgg is None:
            ttk.Label(self.fig_frame, text="Matplotlib backend not available.").pack(pady=12)
            return
        figs = []
        # Harmonize chart background with app theme
        for f in [
            self.graphs.most_selling_items_figure(),
            self.graphs.orders_per_time_figure(),
            self.graphs.revenue_per_day_figure(),
        ]:
            f.patch.set_facecolor(PALETTE["panel"]) 
            for ax in f.axes:
                ax.set_facecolor(PALETTE["panel_alt"]) 
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                ax.tick_params(colors=PALETTE["text"]) 
                ax.yaxis.label.set_color(PALETTE["text"]) 
                if ax.xaxis.label:
                    ax.xaxis.label.set_color(PALETTE["text"]) 
                ax.title.set_color(PALETTE["text"]) 
            figs.append(f)
        for fig in figs:
            canvas = FigureCanvasTkAgg(fig, master=self.fig_frame)
            canvas.draw()
            widget = canvas.get_tk_widget()
            widget.pack(fill=tk.X, padx=8, pady=6)

    def on_show(self):
        self._refresh_all()

    def _refresh_all(self):
        pending = len([o for o in self.db.list_orders() if o["status"] != "COMPLETED"])
        completed = len([o for o in self.db.list_orders("COMPLETED")])
        revenue = sum(float(o["total_amount"]) for o in self.db.list_orders())
        self.pending_var.set(str(pending))
        self.completed_var.set(str(completed))
        self.revenue_var.set(f"{revenue:.2f}")
        self._render_figures()
    
    def _export_csv(self):
        """Export all orders to CSV format."""
        try:
            filepath = export_orders_to_csv(self.db)
            
            # Open the file location
            try:
                if platform.system() == 'Windows':
                    subprocess.Popen(f'explorer /select,"{filepath}"')
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.call(['open', '-R', filepath])
                else:  # Linux
                    subprocess.call(['xdg-open', os.path.dirname(filepath)])
            except Exception:
                pass
            
            messagebox.showinfo("Export Successful", 
                              f"Orders exported to CSV successfully!\n\n"
                              f"File: {os.path.basename(filepath)}\n"
                              f"Location: {ASSETS_DIR}\n\n"
                              f"Total orders exported: {len(self.db.list_orders())}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Failed to export to CSV:\n{str(e)}")
    
    def _export_excel(self):
        """Export all orders to Excel format."""
        if not pandas_available:
            messagebox.showerror("Library Missing", 
                               "Excel export requires 'pandas' and 'openpyxl' libraries.\n"
                               "Install them with: pip install pandas openpyxl")
            return
        
        try:
            filepath = export_orders_to_excel(self.db)
            
            # Open the file
            try:
                if platform.system() == 'Windows':
                    os.startfile(filepath)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.call(['open', filepath])
                else:  # Linux
                    subprocess.call(['xdg-open', filepath])
            except Exception:
                pass
            
            messagebox.showinfo("Export Successful", 
                              f"Orders exported to Excel successfully!\n\n"
                              f"File: {os.path.basename(filepath)}\n"
                              f"Location: {ASSETS_DIR}\n\n"
                              f"Total orders exported: {len(self.db.list_orders())}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Failed to export to Excel:\n{str(e)}")
    
    def _build_offers_tab(self):
        """Build the offers management tab."""
        # Top buttons
        top_btns = ttk.Frame(self.offers_tab, style="Panel.TFrame")
        top_btns.pack(fill=tk.X, padx=8, pady=8)
        ttk.Button(top_btns, text="➕ Add Offer", style="Primary.TButton", command=self._add_offer).pack(side=tk.LEFT, padx=6)
        ttk.Button(top_btns, text="✏️ Update Offer", style="Accent.TButton", command=self._update_offer_ui).pack(side=tk.LEFT, padx=6)
        ttk.Button(top_btns, text="🗑️ Delete Offer", style="Danger.TButton", command=self._delete_offer_ui).pack(side=tk.LEFT, padx=6)
        ttk.Button(top_btns, text="⟳ Refresh", style="Ghost.TButton", command=self._load_offers).pack(side=tk.LEFT, padx=6)
        ttk.Button(top_btns, text="🚪 Logout", style="Danger.TButton", command=self.app._logout).pack(side=tk.RIGHT, padx=6)
        
        # Form frame
        form_frame = ttk.Labelframe(self.offers_tab, text="Offer Details", style="Panel.TLabelframe")
        form_frame.pack(fill=tk.X, padx=8, pady=8)
        
        # Form fields
        ttk.Label(form_frame, text="Offer Name:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.offer_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.offer_name_var, width=30).grid(row=0, column=1, padx=6, pady=4)
        
        ttk.Label(form_frame, text="Menu Item:").grid(row=0, column=2, sticky="w", padx=6, pady=4)
        self.offer_item_var = tk.StringVar()
        self.offer_item_combo = ttk.Combobox(form_frame, textvariable=self.offer_item_var, width=25, state="readonly")
        self.offer_item_combo.grid(row=0, column=3, padx=6, pady=4)
        
        ttk.Label(form_frame, text="Discount Type:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.offer_type_var = tk.StringVar(value="PERCENTAGE")
        ttk.Combobox(form_frame, textvariable=self.offer_type_var, values=["PERCENTAGE", "FIXED"], 
                     width=27, state="readonly").grid(row=1, column=1, padx=6, pady=4)
        
        ttk.Label(form_frame, text="Discount Value:").grid(row=1, column=2, sticky="w", padx=6, pady=4)
        self.offer_value_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.offer_value_var, width=25).grid(row=1, column=3, padx=6, pady=4)
        
        ttk.Label(form_frame, text="Start Date (YYYY-MM-DD):").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        self.offer_start_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.offer_start_var, width=30).grid(row=2, column=1, padx=6, pady=4)
        
        ttk.Label(form_frame, text="End Date (YYYY-MM-DD):").grid(row=2, column=2, sticky="w", padx=6, pady=4)
        self.offer_end_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.offer_end_var, width=25).grid(row=2, column=3, padx=6, pady=4)
        
        ttk.Label(form_frame, text="Day of Week:").grid(row=3, column=0, sticky="w", padx=6, pady=4)
        self.offer_day_var = tk.StringVar()
        ttk.Combobox(form_frame, textvariable=self.offer_day_var, 
                     values=["", "MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"], 
                     width=27, state="readonly").grid(row=3, column=1, padx=6, pady=4)
        
        ttk.Label(form_frame, text="Active:").grid(row=3, column=2, sticky="w", padx=6, pady=4)
        self.offer_active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, variable=self.offer_active_var).grid(row=3, column=3, sticky="w", padx=6, pady=4)
        
        ttk.Button(form_frame, text="⟲ Clear", style="Ghost.TButton", command=self._clear_offer_form).grid(row=4, column=0, padx=6, pady=8)
        
        # Offers list
        list_frame = ttk.Frame(self.offers_tab, style="Panel.TFrame")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        offers_scroll_y = ttk.Scrollbar(list_frame, orient="vertical")
        offers_scroll_x = ttk.Scrollbar(list_frame, orient="horizontal")
        
        self.offers_tree = ttk.Treeview(
            list_frame,
            columns=("name", "item", "type", "value", "start", "end", "day", "active"),
            show="headings",
            height=12,
            yscrollcommand=offers_scroll_y.set,
            xscrollcommand=offers_scroll_x.set
        )
        
        for col, text, width in [
            ("name", "Offer Name", 150),
            ("item", "Item", 120),
            ("type", "Type", 100),
            ("value", "Value", 80),
            ("start", "Start Date", 100),
            ("end", "End Date", 100),
            ("day", "Day", 80),
            ("active", "Active", 60),
        ]:
            self.offers_tree.heading(col, text=text)
            self.offers_tree.column(col, width=width, anchor="center")
        
        offers_scroll_y.config(command=self.offers_tree.yview)
        offers_scroll_x.config(command=self.offers_tree.xview)
        
        self.offers_tree.grid(row=0, column=0, sticky="nsew")
        offers_scroll_y.grid(row=0, column=1, sticky="ns")
        offers_scroll_x.grid(row=1, column=0, sticky="ew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Bind selection
        self.offers_tree.bind("<Button-1>", self._on_offer_select)
        
        # Load data
        self._load_menu_items()
        self._load_offers()
    
    def _load_menu_items(self):
        """Load menu items into the combobox."""
        menu_items = [("", "All Items")]
        for item in self.db.list_menu():
            menu_items.append((item["item_id"], item["item_name"]))
        self.offer_item_combo['values'] = [f"{name} (ID: {id})" if id else name for id, name in menu_items]
    
    def _load_offers(self):
        """Load offers into the treeview."""
        for i in self.offers_tree.get_children():
            self.offers_tree.delete(i)
        offers = self.db.list_offers()
        for offer in offers:
            self.offers_tree.insert(
                "",
                tk.END,
                iid=str(offer["offer_id"]),
                values=(
                    offer["offer_name"],
                    offer["item_name"],
                    offer["discount_type"],
                    f"{offer['discount_value']:.2f}",
                    offer["start_date"] or "-",
                    offer["end_date"] or "-",
                    offer["day_of_week"] or "-",
                    "Yes" if offer["active"] else "No",
                ),
            )
        self._zebra_tree_offers()
    
    def _zebra_tree_offers(self):
        """Apply zebra striping to offers treeview."""
        self.offers_tree.tag_configure("odd", background=PALETTE["row_alt"])
        for idx, iid in enumerate(self.offers_tree.get_children("")):
            self.offers_tree.item(iid, tags=("odd",) if idx % 2 else ())
    
    def _on_offer_select(self, event):
        """Populate form when offer is selected."""
        sel = self.offers_tree.focus()
        if not sel:
            return
        offer_id = int(sel)
        offers = self.db.list_offers()
        offer = next((o for o in offers if o["offer_id"] == offer_id), None)
        if offer:
            self.offer_name_var.set(offer["offer_name"])
            if offer["item_id"]:
                self.offer_item_var.set(f"{offer['item_name']} (ID: {offer['item_id']})")
            else:
                self.offer_item_var.set("All Items")
            self.offer_type_var.set(offer["discount_type"])
            self.offer_value_var.set(str(offer["discount_value"]))
            self.offer_start_var.set(offer["start_date"] or "")
            self.offer_end_var.set(offer["end_date"] or "")
            self.offer_day_var.set(offer["day_of_week"] or "")
            self.offer_active_var.set(offer["active"])
    
    def _clear_offer_form(self):
        """Clear the offer form."""
        self.offer_name_var.set("")
        self.offer_item_var.set("")
        self.offer_type_var.set("PERCENTAGE")
        self.offer_value_var.set("")
        self.offer_start_var.set("")
        self.offer_end_var.set("")
        self.offer_day_var.set("")
        self.offer_active_var.set(True)
        self.offers_tree.selection_remove(self.offers_tree.selection())
    
    def _add_offer(self):
        """Add a new offer."""
        name = self.offer_name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Enter offer name")
            return
        
        item_str = self.offer_item_var.get()
        item_id = None
        if item_str and item_str != "All Items":
            try:
                # Extract ID from "Item Name (ID: 123)"
                if "(ID:" in item_str:
                    item_id = int(item_str.split("(ID:")[1].split(")")[0].strip())
            except:
                messagebox.showerror("Error", "Invalid item selection")
                return
        
        discount_type = self.offer_type_var.get()
        try:
            discount_value = float(self.offer_value_var.get())
            if discount_value < 0:
                raise ValueError("Discount value cannot be negative")
            if discount_type == "PERCENTAGE" and discount_value > 100:
                raise ValueError("Percentage cannot exceed 100%")
        except ValueError as e:
            messagebox.showerror("Invalid Value", f"Please enter a valid discount value.\n{str(e)}")
            return
        
        start_date = self.offer_start_var.get().strip() or None
        end_date = self.offer_end_var.get().strip() or None
        day_of_week = self.offer_day_var.get().strip() or None
        active = self.offer_active_var.get()
        
        try:
            self.db.create_offer(name, item_id, discount_type, discount_value, 
                                start_date, end_date, day_of_week, active)
            messagebox.showinfo("Success", "Offer created successfully!")
            self._clear_offer_form()
            self._load_offers()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create offer:\n{str(e)}")
    
    def _update_offer_ui(self):
        """Update selected offer."""
        sel = self.offers_tree.focus()
        if not sel:
            messagebox.showwarning("Select", "Select an offer to update")
            return
        
        offer_id = int(sel)
        name = self.offer_name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Enter offer name")
            return
        
        item_str = self.offer_item_var.get()
        item_id = None
        if item_str and item_str != "All Items":
            try:
                if "(ID:" in item_str:
                    item_id = int(item_str.split("(ID:")[1].split(")")[0].strip())
            except:
                messagebox.showerror("Error", "Invalid item selection")
                return
        
        discount_type = self.offer_type_var.get()
        try:
            discount_value = float(self.offer_value_var.get())
            if discount_value < 0:
                raise ValueError("Discount value cannot be negative")
            if discount_type == "PERCENTAGE" and discount_value > 100:
                raise ValueError("Percentage cannot exceed 100%")
        except ValueError as e:
            messagebox.showerror("Invalid Value", f"Please enter a valid discount value.\n{str(e)}")
            return
        
        start_date = self.offer_start_var.get().strip() or None
        end_date = self.offer_end_var.get().strip() or None
        day_of_week = self.offer_day_var.get().strip() or None
        active = self.offer_active_var.get()
        
        try:
            self.db.update_offer(offer_id, name, item_id, discount_type, discount_value,
                               start_date, end_date, day_of_week, active)
            messagebox.showinfo("Success", "Offer updated successfully!")
            self._clear_offer_form()
            self._load_offers()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update offer:\n{str(e)}")
    
    def _delete_offer_ui(self):
        """Delete selected offer."""
        sel = self.offers_tree.focus()
        if not sel:
            messagebox.showwarning("Select", "Select an offer to delete")
            return
        
        if messagebox.askyesno("Confirm", "Delete selected offer?"):
            try:
                self.db.delete_offer(int(sel))
                messagebox.showinfo("Success", "Offer deleted successfully!")
                self._clear_offer_form()
                self._load_offers()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete offer:\n{str(e)}")


class CanteenApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Canteen Payment System")
        self.geometry("1000x750")
        self.minsize(900, 650)
        ensure_assets_dir_exists()
        self.db = DatabaseHandler(DB_PATH)
        self.current_user: dict | None = None

        # Root background
        self.configure(bg=PALETTE["bg"])
        
        # Center window on screen
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}") 

        # Styles
        self._setup_styles()

        container = ttk.Frame(self, style="Panel.TFrame")
        container.pack(fill=tk.BOTH, expand=True)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self.frames: dict[str, ttk.Frame] = {}
        self.frames["LoginWindow"] = LoginWindow(container, self, self.db)
        self.frames["StudentDashboard"] = StudentDashboard(container, self, self.db)
        self.frames["AttendantDashboard"] = AttendantDashboard(container, self, self.db)
        self.frames["ManagerDashboard"] = ManagerDashboard(container, self, self.db)

        for f in self.frames.values():
            f.grid(row=0, column=0, sticky="nsew")

        self._build_topbar()
        self.show_frame("LoginWindow")

    def _build_topbar(self):
        self.topbar = ttk.Frame(self, style="Topbar.TFrame")
        self.topbar.pack(fill=tk.X, side=tk.TOP)
        title = ttk.Label(self.topbar, text="🍽  Canteen", style="Title.TLabel")
        title.pack(side=tk.LEFT, padx=12, pady=8)
        self.user_label = ttk.Label(self.topbar, text="Not logged in", style="Subtle.TLabel")
        self.user_label.pack(side=tk.LEFT, padx=8)
        self.role_label = ttk.Label(self.topbar, text="", style="Subtle.TLabel")
        self.role_label.pack(side=tk.LEFT)
        # Make logout button more visible with danger style
        self.nav_button = ttk.Button(self.topbar, text="🚪 Logout", style="Danger.TButton", command=self._logout)
        self.nav_button.pack(side=tk.RIGHT, padx=12, pady=6)

    def _setup_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Frames
        style.configure("Topbar.TFrame", background=PALETTE["panel"], relief="flat") 
        style.configure("Panel.TFrame", background=PALETTE["panel"], relief="flat") 
        style.configure("PanelAlt.TFrame", background=PALETTE["panel_alt"], relief="flat") 
        style.configure("Card.TFrame", background=PALETTE["panel_alt"], relief="flat")

        # Labels
        style.configure("TLabel", background=PALETTE["panel"], foreground=PALETTE["text"], font=("Segoe UI", 11))
        style.configure("Subtle.TLabel", background=PALETTE["panel"], foreground=PALETTE["text_secondary"], font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=PALETTE["panel"], foreground=PALETTE["text"], font=("Segoe UI", 16, "bold"))
        style.configure("FormLabel.TLabel", background=PALETTE["panel_alt"], foreground=PALETTE["text"], font=("Segoe UI", 10))

        # Buttons
        style.configure("TButton", padding=(12, 8), font=("Segoe UI", 10, "bold"), foreground="#ffffff", borderwidth=0) 
        style.map("TButton",
                  background=[("active", PALETTE["primary_hover"]), ("!active", PALETTE["primary"])],
                  relief=[("pressed", "sunken"), ("!pressed", "flat")])
        style.configure("Primary.TButton", background=PALETTE["primary"], foreground="#ffffff", padding=(16, 10))
        style.map("Primary.TButton", background=[("active", PALETTE["primary_hover"])])
        style.configure("Accent.TButton", background=PALETTE["accent"], foreground="#ffffff", padding=(16, 10))
        style.map("Accent.TButton", background=[("active", PALETTE["accent_hover"])])
        style.configure("Danger.TButton", background=PALETTE["danger"], foreground="#ffffff", padding=(12, 8))
        style.map("Danger.TButton", background=[("active", PALETTE["danger_hover"])])
        style.configure("Ghost.TButton", background=PALETTE["panel"], foreground=PALETTE["text"], relief="flat", padding=(10, 6))
        style.map("Ghost.TButton",
                  background=[("active", PALETTE["panel_hover"])],
                  foreground=[("!active", PALETTE["link"]), ("active", PALETTE["link_hover"])])
        # Extra button variants
        style.configure("Success.TButton", background=PALETTE["success"], foreground="#001b10", padding=(14, 9))
        style.map("Success.TButton", background=[("active", PALETTE["success_hover"])])
        style.configure("Warning.TButton", background=PALETTE["warning"], foreground="#1a0f00", padding=(14, 9))
        style.map("Warning.TButton", background=[("active", PALETTE["warning_hover"])])
        style.configure("Info.TButton", background=PALETTE["info"], foreground="#00121a", padding=(14, 9))
        style.map("Info.TButton", background=[("active", PALETTE["info_hover"])])

        # Entry Fields - Custom styled with dark background
        style.configure("TEntry",
                       fieldbackground=PALETTE["input_bg"],
                       foreground=PALETTE["text"],
                       borderwidth=1,
                       relief="solid",
                       padding=8,
                       insertcolor=PALETTE["text"],
                       font=("Segoe UI", 10))
        style.map("TEntry",
                 fieldbackground=[("focus", PALETTE["input_focus"]), ("!focus", PALETTE["input_bg"])],
                 bordercolor=[("focus", PALETTE["border_focus"]), ("!focus", PALETTE["border"])])

        # Combobox - Properly styled dropdown
        style.configure("TCombobox",
                       fieldbackground=PALETTE["input_bg"],
                       foreground=PALETTE["text"],
                       background=PALETTE["panel_alt"],
                       borderwidth=1,
                       relief="solid",
                       padding=8,
                       arrowcolor=PALETTE["text"],
                       font=("Segoe UI", 10))
        style.map("TCombobox",
                 fieldbackground=[("focus", PALETTE["input_focus"]), ("readonly", PALETTE["input_bg"]), ("!focus", PALETTE["input_bg"])],
                 bordercolor=[("focus", PALETTE["border_focus"]), ("!focus", PALETTE["border"])],
                 arrowcolor=[("active", PALETTE["text"])],
                 background=[("readonly", PALETTE["input_bg"])])
        
        # Combobox dropdown styling (popup window)
        try:
            style.configure("TCombobox.Listbox",
                           background=PALETTE["input_bg"],
                           foreground=PALETTE["text"],
                           selectbackground=PALETTE["primary"],
                           selectforeground="#ffffff",
                           borderwidth=1,
                           relief="solid",
                           font=("Segoe UI", 10))
        except Exception:
            pass

        # Spinbox
        try:
            style.configure("TSpinbox",
                           fieldbackground=PALETTE["input_bg"],
                           foreground=PALETTE["text"],
                           borderwidth=1,
                           relief="solid",
                           padding=6,
                           insertcolor=PALETTE["text"],
                           arrowcolor=PALETTE["text"],
                           font=("Segoe UI", 10))
            style.map("TSpinbox",
                     fieldbackground=[("focus", PALETTE["input_focus"]), ("!focus", PALETTE["input_bg"])],
                     bordercolor=[("focus", PALETTE["border_focus"]), ("!focus", PALETTE["border"])])
        except Exception:
            pass

        # Checkbutton
        style.configure("TCheckbutton",
                       background=PALETTE["panel_alt"],
                       foreground=PALETTE["text"],
                       font=("Segoe UI", 10))
        style.map("TCheckbutton",
                 background=[("active", PALETTE["panel_alt"]), ("selected", PALETTE["panel_alt"])])

        # Notebook
        style.configure("TNotebook", background=PALETTE["panel"], borderwidth=0, relief="flat") 
        style.configure("TNotebook.Tab",
                       padding=(18, 10),
                       font=("Segoe UI", 11, "bold"),
                       background=PALETTE["panel"],
                       foreground=PALETTE["text_secondary"],
                       borderwidth=0) 
        style.map("TNotebook.Tab",
                 background=[("selected", PALETTE["accent_alt"]), ("!selected", PALETTE["panel"])],
                 foreground=[("selected", "#ffffff"), ("!selected", PALETTE["text_secondary"])],
                 expand=[("selected", [1, 1, 1, 0])])

        # Treeview
        style.configure("Treeview",
                       background=PALETTE["panel"],
                       fieldbackground=PALETTE["panel"],
                       foreground=PALETTE["text"],
                       rowheight=32,
                       font=("Segoe UI", 10),
                       borderwidth=0,
                       relief="flat")
        style.map("Treeview",
                 background=[("selected", PALETTE["selection_bg"])],
                 foreground=[("selected", PALETTE["selection_fg"])])
        style.configure("Treeview.Heading",
                       font=("Segoe UI", 11, "bold"),
                       background=PALETTE["table_header"],
                       foreground=PALETTE["text"],
                       relief="flat",
                       borderwidth=0,
                       padding=(8, 8))

        # Labelframe
        style.configure("TLabelframe",
                       background=PALETTE["panel"],
                       relief="flat",
                       borderwidth=1,
                       bordercolor=PALETTE["border"]) 
        style.configure("TLabelframe.Label",
                       background=PALETTE["panel"],
                       foreground=PALETTE["text"],
                       font=("Segoe UI", 11, "bold"))

    def show_frame(self, name: str) -> None:
        frame = self.frames[name]
        frame.tkraise()
        if hasattr(frame, "on_show"):
            try:
                frame.on_show()
            except Exception:
                pass

    def set_user(self, user: dict) -> None:
        self.current_user = user
        self.user_label.config(text=f"{user['name']} ({user['user_id']})")
        self.role_label.config(text=f" | Role: {user['role']}")
        role = user["role"].lower()
        if role == "student":
            self.show_frame("StudentDashboard")
        elif role == "attendant":
            self.show_frame("AttendantDashboard")
        else:
            self.show_frame("ManagerDashboard")

    def _logout(self):
        self.current_user = None
        self.user_label.config(text="Not logged in")
        self.role_label.config(text="")
        self.show_frame("LoginWindow")


def main():
    app = CanteenApp()
    app.mainloop()


if __name__ == "__main__":
    main()


