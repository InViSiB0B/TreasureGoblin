from datetime import datetime, timedelta
import json
import shutil
import sqlite3
import sys
import tempfile
import uuid
import zipfile
import random
import os
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QTextEdit,
                             QListWidget, QCalendarWidget, QFileDialog,
                             QFormLayout, QGroupBox, QSplitter, QTabWidget,
                             QMessageBox, QComboBox, QScrollArea, QFrame, QLineEdit, 
                             QDateEdit, QDateTimeEdit, QSpinBox, QListWidgetItem, QGridLayout, QInputDialog,
                             QMenu, QFileDialog, QDialog, QCheckBox, QProgressBar)
from PyQt5.QtCore import Qt, QDate, QDateTime, QObject, pyqtSignal, QTimer, QThread
from PyQt5.QtGui import QIcon, QFont, QPixmap
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import webbrowser
import threading

class TreasureGoblin:
    """
    TreasureGoblin is your personal finance companion, helping you track spending and build wealth through smarter money
    habits. Monitor your finances today to create the financial future you deserve, whether that's next month of years
    from now!
    """

    def __init__(self, db_path = "treasuregoblin.db"):
        """
        Initialize the SQLite database for TreasureGoblin with necessary tables.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.app_dir = Path.home() / ".treasuregoblin"
        self.media_dir = self.app_dir / "media"
        # Create application directories if they don't exist
        self.app_dir.mkdir(exist_ok=True)
        self.media_dir.mkdir(exist_ok=True)
        # Initialize database
        self.setup_database()

        # Initialize Google Drive sync
        self.drive_sync = GoogleDriveSync(self)
        
    def setup_database(self):
        """Create the database and tables if they don't exist."""
        conn = self.get_db_connection()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # Create categories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
                UNIQUE(name, type)
            )
        ''')

        # Create transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
            amount DECIMAL(10, 2) NOT NULL,
            date DATE NOT NULL,
            category_id INTEGER NOT NULL,
            tag TEXT,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
        ''')

        # Insert default categories
        default_income_categories = ['Paycheck','Freelance', 'Investment', 'Gift', 'Other Income']
        default_expense_categories = ['Grocery', 'Housing', 'Transportation', 'Utilities', 'Entertainment', 'Dining', 'Healthcare',
                                      'Education', 'Shopping', 'Bills', 'Gas', 'Other Expense']
        
        # Insert income categories
        for category in default_income_categories:
            cursor.execute('INSERT OR IGNORE INTO categories (name, type) VALUES (?, ?)', (category, 'income'))

        # Insert expense categories
        for category in default_expense_categories:
            cursor.execute('INSERT OR IGNORE INTO categories (name, type) VALUES (?, ?)', (category, 'expense'))

        # Commit changes and close connection
        conn.commit()
        conn.close()

    def get_db_connection(self):
        """Establish and return a database connection."""
        return sqlite3.connect(self.db_path)

    def add_transaction(self, transaction_type, amount, date, category, tag = None):
        """
        Add a new transaction to the database.

        Parameters:
            transaction_type (str): Type of transaction ('income' or 'expense')
            amount (float): Transaction amount
            date (str or datetime): Transaction date in ('MM-DD-YYYY' format if string)
            category (str): Transaction category name
            tag (str, optional): Optional tag for the transaction

        Returns:
            int: ID of the newly created transaction, or None if failed
        """
        # Validate transaction type
        if transaction_type not in ['income', 'expense']:
            raise ValueError("Transaction type must be either 'income' or 'expense'")
        
        # Convert string date to datetime if needed
        if isinstance(date, str):
            try:
                date = datetime.strptime(date, '%m-%d-%Y').date()
            except ValueError:
                raise ValueError("Date must be in 'MM-DD-YYYY' format")
            
        # Make sure amount is positive
        amount = abs(float(amount))

        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            # Get category ID
            cursor.execute(
                "SELECT id FROM categories WHERE name = ? AND type = ?",
                (category, transaction_type)
            )
            category_result = cursor.fetchone()

            if not category_result:
                # Category doesn't exist, create it
                cursor.execute(
                    "INSERT INTO categories (name, type) VALUES (?, ?)",
                    (category, transaction_type)
                )
                category_id = cursor.lastrowid
            else:
                category_id = category_result[0]

            # Insert transaction
            cursor.execute('''
                INSERT INTO transactions (type, amount, date, category_id, tag)
                VALUES (?, ?, ?, ?, ?)
            ''', (transaction_type, amount, date.isoformat(), category_id, tag))

            transaction_id = cursor.lastrowid
            conn.commit()
            return transaction_id
        
        except sqlite3.Error as e:
            conn.rollback()
            print(f"Database error: {e}")
            return None
        finally:
            conn.close()

    def get_transactions(self, month = None, year = None, limit = None):
        """
        Retrieve transactions from the database with optional filtering by month and year.

        Parameters:
            month (int, optional): Month to filter by (1-12)
            year (int, optional): Year to filter by
            limit (int, optional): Maximum number of transactions to return

        Returns:
            list: List of transaction dictionaries with all details
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT t.id, t.type, t.amount, t.date, c.name as category, t.tag
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
        """

        params = []

        # Add date filtering if specified
        if month and year:
            query += " WHERE strftime('%m', t.date) = ? AND strftime('%Y', t.date) = ?"
            params.extend([f"{month:02d}", f"{year}"])
        elif month:
            query += " WHERE strftime('%m', t.date) = ?"
            params.append(f"{month:02d}")
        elif year:
            query += " WHERE strftime('%Y', t.date) = ?"
            params.append(f"{year}")

        # Order by date descending (newest first)
        query += " ORDER BY t.date DESC"

        # Add limit if specified
        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, params)

        # Convert to list of dictionaries
        columns = [column[0] for column in cursor.description]
        transactions = []

        for row in cursor.fetchall():
            transaction = dict(zip(columns, row))
            transactions.append(transaction)

        conn.close()
        return transactions
    
class TreasureGoblinApp (QMainWindow):
    """Main application window for TreasureGoblin"""
    def __init__(self, treasuregoblin):
        super().__init__()

        self.treasure_goblin = treasuregoblin
        self.init_nibble_tips()
        self.init_ui()

    def init_nibble_tips(self):
        """Initialize Nibble's financial tips collection."""
        self.nibble_tips_collection = [
            "Save at least 20% of your income for long-term financial goals!",
            "Track every expense to understand your spending habits better.",
            "Use the 50/30/20 rule: 50% for needs, 30% for wants, 20% for savings.",
            "Consider automating your savings to build wealth consistently.",
            "Review your budget regularly to make adjustments as needed.",
            "Check your credit report annually to maintain good financial health!",
            "Pay off high-interest debt first to save money in the long run.",
            "Set up an emergency fund that covers 3-6 months of expenses.",
            "Avoid impulse purchases by waiting 24 hours before buying non-essentials.",
            "Contribute to retirement accounts early to benefit from compound interest!",
            "Look for ways to increase income, not just cut expenses.",
            "Avoid using credit cards for purchases you can't pay off immediately.",
            "Consider low-cost index funds for long-term investing.",
            "Don't forget to budget for irregular expenses like car maintenance!",
            "Shop around annually for better rates on insurance policies.",
            "Eating out less frequently can significantly boost your savings!",
            "Remember that small expenses add up over time - track them all!",
            "Challenge yourself to a no-spend day once a week to build discipline.",
            "Consider bundling services like internet and phone to save money.",
            "Buying quality items that last longer can save money over time."
        ]

        # Initialize current tip index
        self.current_tip_index = 0

        # Default nibble image is the first one to be assigned
        self.current_nibble_image = 0
        

    def init_ui(self):
            """Initialize the user interface."""
            self.setWindowTitle("TreasureGoblin - Your Income & Expense Tracker")
            self.setGeometry(100, 100, 1000, 800)

            # Create the central widget and main layout
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            main_layout = QVBoxLayout(central_widget)

            # Header with application title
            header_label = QLabel("TreasureGoblin")
            header_label.setFont(QFont("Arial", 18, QFont.Bold))
            header_label.setAlignment(Qt.AlignCenter)
            main_layout.addWidget(header_label)

            # Create tab widget
            self.tabs = QTabWidget()

            self.tabs.currentChanged.connect(self.handle_tab_changed)

            main_layout.addWidget(self.tabs)

            # Create individual tabs
            self.dashboard_tab = self.create_dashboard_tab()
            self.create_transactions_tab = self.create_transactions_tab()
            self.categories_tab = self.create_categories_tab()
            self.reports_tab = self.create_reports_tab()

            # Add tabs to the tab widget
            self.tabs.addTab(self.dashboard_tab, "Dashboard")
            self.tabs.addTab(self.create_transactions_tab, "Transactions")
            self.tabs.addTab(self.categories_tab, "Categories")
            self.tabs.addTab(self.reports_tab, "Reports")

            # Footer with status information
            status_bar = self.statusBar()
            status_bar.showMessage("Ready")

    def get_db_connection(self):
        """Relay database connection to the data manager."""
        return self.treasure_goblin.get_db_connection()
    
    def handle_tab_changed(self, index):
        """Handle actions when tabs are changed."""
        # When switching to transactions tab (index 1), update category options
        if index == 1:
            self.update_category_options()

        # When swtiching to dahsboard tab (index 0), update dahsboard
        elif index == 0:
            self.update_dashboard()

    def create_dashboard_tab(self):
        """Create the dashboard tab with summary information."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Welcome section
        welcome_group = QGroupBox("Welcome to TreasureGoblin!")
        welcome_layout = QVBoxLayout(welcome_group)
        welcome_text = QLabel(
            "TreasureGoblin is your personal finance companion, helping you track spending and build wealth through smarter money"
            " habits. Monitor your finances today to create the financial future you deserve, whether that's next month or years"
            " from now!"
        )
        welcome_text.setWordWrap(True)
        welcome_layout.addWidget(welcome_text)
        layout.addWidget(welcome_group)
        
        # Financial Summary section
        summary_group = QGroupBox("Financial Summary:")
        summary_layout = QHBoxLayout(summary_group)
        
        # Total balance box
        balance_box = QFrame()
        balance_box.setFrameStyle(QFrame.StyledPanel)
        balance_layout = QVBoxLayout(balance_box)
        
        balance_title = QLabel("Total balance across all accounts:")
        balance_title.setAlignment(Qt.AlignCenter)
        balance_layout.addWidget(balance_title)
        
        self.balance_amount = QLabel()
        self.balance_amount.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setBold(True)
        font.setPointSize(14)
        self.balance_amount.setFont(font)
        balance_layout.addWidget(self.balance_amount)
        
        summary_layout.addWidget(balance_box)
        
        # Month-to-date income and expenses box
        mtd_box = QFrame()
        mtd_box.setFrameStyle(QFrame.StyledPanel)
        mtd_layout = QVBoxLayout(mtd_box)
        
        mtd_title = QLabel("Month-to-date income & expenses:")
        mtd_title.setAlignment(Qt.AlignCenter)
        mtd_layout.addWidget(mtd_title)
        
        self.month_income = QLabel()
        self.month_income.setStyleSheet("color: green;")
        self.month_income.setAlignment(Qt.AlignRight)
        mtd_layout.addWidget(self.month_income)
        
        self.month_expenses = QLabel()
        self.month_expenses.setStyleSheet("color: red;")
        self.month_expenses.setAlignment(Qt.AlignRight)
        mtd_layout.addWidget(self.month_expenses)
        
        self.month_net = QLabel()
        self.month_net.setAlignment(Qt.AlignRight)
        mtd_layout.addWidget(self.month_net)
        
        summary_layout.addWidget(mtd_box)
        
        # Month comparison box
        comparison_box = QFrame()
        comparison_box.setFrameStyle(QFrame.StyledPanel)
        comparison_layout = QVBoxLayout(comparison_box)
        
        current_month = datetime.now().strftime("%B")
        last_month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%B")
        
        self.comparison_title = QLabel(f"{current_month} compared to {last_month}:")
        self.comparison_title.setAlignment(Qt.AlignCenter)
        comparison_layout.addWidget(self.comparison_title)
        
        self.prev_month_label = QLabel()
        self.prev_month_label.setAlignment(Qt.AlignRight)
        comparison_layout.addWidget(self.prev_month_label)
        
        self.curr_month_label = QLabel()
        self.curr_month_label.setAlignment(Qt.AlignRight)
        comparison_layout.addWidget(self.curr_month_label)
        
        self.difference_label = QLabel()
        self.difference_label.setAlignment(Qt.AlignRight)
        comparison_layout.addWidget(self.difference_label)
        
        summary_layout.addWidget(comparison_box)
        
        layout.addWidget(summary_group)
        
        # Recent Transactions section
        recent_group = QGroupBox("Recent Transactions:")
        recent_layout = QVBoxLayout(recent_group)
        
        self.transactions_list = QListWidget()
        self.transactions_list.setMaximumHeight(200)
        recent_layout.addWidget(self.transactions_list)
        layout.addWidget(recent_group)
        
        # Nibble the goblin section
        nibble_container = QHBoxLayout()
        
        # Left side - Nibble's tips
        tips_frame = QFrame()
        tips_frame.setFrameStyle(QFrame.StyledPanel)
        tips_layout = QVBoxLayout(tips_frame)
        
        # Initialize Nibble's tip with a random tip from the collection
        self.current_tip_index = random.randint(0, len(self.nibble_tips_collection) -1)
        self.nibble_tips = QLabel(self.nibble_tips_collection[self.current_tip_index])
        self.nibble_tips.setWordWrap(True)
        self.nibble_tips.setMinimumWidth(300)
        self.nibble_tips.setStyleSheet("font-size: 11pt;")
        tips_layout.addWidget(self.nibble_tips)
        
        # Right side - Nibble's image
        self.nibble_image_label = QLabel()
        self.nibble_image_label.setFixedSize(120, 120)
        self.nibble_image_label.setCursor(Qt.PointingHandCursor)
        self.nibble_image_label.mousePressEvent = self.nibble_clicked

        # Load Nibble's image
        self.load_nibble_image()
        
        nibble_container.addWidget(tips_frame)
        nibble_container.addWidget(self.nibble_image_label)
        
        layout.addLayout(nibble_container)
        
        # Update dashboard with data
        self.update_dashboard()
        
        return tab
    
    def load_nibble_images(self):
        """Load all available Nibble png images from the media directory."""
        self.nibble_images = []
        script_dir = os.path.dirname(os.path.abspath(__file__))
        nibble_dir = os.path.join(script_dir, "nibble_images")

        # Check if the directory exists
        if os.path.exists(nibble_dir) and os.path.isdir(nibble_dir):
            # Look for Nibble images in the directory
            for file in os.listdir(nibble_dir):
                if file.lower().endswith('.png'):
                    self.nibble_images.append(os.path.join(nibble_dir, file))

    def load_nibble_image(self):
        """This is different than load_nibble_images, loads and displays an image (singular) from the images loaded"""
        # Load images if not already loaded
        if not hasattr(self, 'nibble_images'):
            self.load_nibble_images()

        # If we have actual images, use them
        if self.nibble_images:
            try:
                image_path = self.nibble_images[self.current_nibble_image]
                pixmap = QPixmap(image_path)

                if not pixmap.isNull():
                    # Scale the pixmap to fit our lavel while maintaining aspect ratio
                    pixmap = pixmap.scaled(
                        self.nibble_image_label.width(),
                        self.nibble_image_label.height(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    self.nibble_image_label.setPixmap(pixmap)
                    return
            except Exception as e:
                print(f"Error loading Nibble image: {e}")

        # Fallback to colored background if image loading fails
        self.nibble_image_label.setPixmap(QPixmap()) # Clear any existing pixmap
        self.nibble_image_label.setStyleSheet("background-color: lightgreen; border-radius: 60px;")

    def update_nibble(self):
        """Update Nibble with a random image and tip"""
        # Select a random tip
        new_tip_index = random.randint(0, len(self.nibble_tips_collection) - 1)

        # Ensure the same tip can't be selected twice in a row
        while new_tip_index == self.current_tip_index and len(self.nibble_tips_collection) > 1:
            new_tip_index = random.randint(0, len(self.nibble_tips_collection) - 1)
        
        self.current_tip_index = new_tip_index
        self.nibble_tips.setText(self.nibble_tips_collection[self.current_tip_index])

        # Select a random image
        if hasattr(self, 'nibble_images') and len(self.nibble_images) > 1:
            new_image_index = random.randint(0, len(self.nibble_images) - 1)

            # Ensure the same image isn't selected twice in a row
            while new_image_index == self.current_nibble_image:
                new_image_index = random.randint(0, len(self.nibble_images) - 1)

            self.current_nibble_image = new_image_index

        # Load the new image
        self.load_nibble_image()

    def nibble_clicked(self, event):
        """Handle click events on Nibble's image."""
        self.update_nibble()
    
    def update_dashboard(self):
        """Update dashboard with the latest data from the database."""
        try:
            # Get current and previous month info
            now = datetime.now()
            current_month = now.month
            current_year = now.year

            # Calculate previous month
            if current_month == 1: # January
                previous_month = 12
                previous_year = current_year - 1
            else:
                previous_month = current_month - 1
                previous_year = current_year

            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Calculate total balance
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) -
                    SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END)
                FROM transactions
            """)

            total_balance = cursor.fetchone()[0] or 0
            self.balance_amount.setText(f"$ {total_balance:.2f}")

            # Calculate current month income and expenses
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
                    SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expenses
                FROM transactions
                WHERE strftime('%m', date) = ? AND strftime('%Y', date) = ?
            """, (f"{current_month:02d}", str(current_year)))

            current_income, current_expenses = cursor.fetchone()
            current_income = current_income or 0
            current_expenses = current_expenses or 0
            current_net = current_income - current_expenses

            self.month_income.setText(f"$ {current_income:.2f}")
            self.month_expenses.setText(f"$ {current_expenses:.2f}")
            self.month_net.setText(f"$ {current_net:.2f}")

            # Calculate the previous months income and expenses
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) -
                    SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as net
                FROM transactions
                WHERE strftime('%m', date) = ? AND strftime('%Y', date) = ?
            """, (f"{previous_month:02d}", str(previous_year)))

            previous_net = cursor.fetchone()[0] or 0

            # Update month comparison section
            current_month_name = now.strftime("%B")
            previous_month_name = datetime(previous_year, previous_month, 1).strftime("%B")

            self.comparison_title.setText(f"{current_month_name} compared to {previous_month_name}:")
            self.prev_month_label.setText(f"{previous_month_name}: $ {previous_net:.2f}")
            self.curr_month_label.setText(f"{current_month_name}: $ {current_net:.2f}")

            # Calculate difference and percentage
            difference = current_net - previous_net
            percentage = 0
            if previous_net != 0:
                percentage = (difference / abs(previous_net)) * 100

            # Set color based on whether the difference is positive or negative
            color = "green" if difference >= 0 else "red"
            self.difference_label.setText(f"$ {difference:.2f} ({percentage:.2f}%)")
            self.difference_label.setStyleSheet(f"color: {color};")

            # Get recent transactions
            cursor.execute("""
                SELECT t.date, t.amount, t.type, c.name, t.tag
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                ORDER BY t.date DESC
                LIMIT 5
            """)

            recent_transactions = cursor.fetchall()

            # Clear and repopulate transactions list
            self.transactions_list.clear()

            for transaction in recent_transactions:
                date, amount, type, category, tag = transaction
                date_obj = datetime.fromisoformat(date).strftime("%m/%d/%y")

                description = category
                if tag:
                    description += f" ({tag})"
                
                 # Create item
                item = QListWidgetItem()
                self.transactions_list.addItem(item)
                
                # Create a label with rich text 
                amount_color = "green" if type == 'income' else "red"
                label = QLabel(f"{date_obj} {description} $ <span style='color:{amount_color}'>{amount:.2f}</span>")
                label.setTextFormat(Qt.RichText)
                
                # Set the custom widget for the item
                self.transactions_list.setItemWidget(item, label)
                
                # Set appropriate item size
                item.setSizeHint(label.sizeHint())

            conn.close()

            # Update Nibble with a new tip and image
            self.update_nibble()

        except Exception as e:
            print(f"Error updating dashboard: {e}")

    def create_transactions_tab(self):
        """Create the transactions tab with transaction entry form and history."""
        tab = QWidget()
        layout = QHBoxLayout(tab)
        
        # Left side - Transactions list
        transactions_list_container = QFrame()
        transactions_list_container.setFrameStyle(QFrame.StyledPanel)
        transactions_list_layout = QVBoxLayout(transactions_list_container)
        
        # Month selector
        month_selector_layout = QHBoxLayout()
        month_selector_layout.addWidget(QLabel("Transactions for:"))
        
        self.month_combo = QComboBox()
        
        # Add months (last 12 months)
        current_date = QDate.currentDate()
        for i in range(12):
            # Calculate month and year
            date = current_date.addMonths(-i)
            month_year = date.toString("MMMM yyyy")
            self.month_combo.addItem(month_year, (date.month(), date.year()))
        
        self.month_combo.currentIndexChanged.connect(self.load_transactions_for_month)
        month_selector_layout.addWidget(self.month_combo)
        
        transactions_list_layout.addLayout(month_selector_layout)
        
        # Transactions list
        self.transactions_list_widget = QListWidget()
        self.transactions_list_widget.setMinimumWidth(300)
        transactions_list_layout.addWidget(self.transactions_list_widget)
        
        # Right side - container for form and buttons
        right_container = QVBoxLayout()
        
        # Transaction form
        transaction_form = QFrame()
        transaction_form.setFrameStyle(QFrame.StyledPanel)
        form_layout = QVBoxLayout(transaction_form)
        
        form_title = QLabel("Enter a Transaction:")
        form_title.setFont(QFont("Arial", 10, QFont.Bold))
        form_layout.addWidget(form_title)
        
        # Form fields
        transaction_form_fields = QFormLayout()
        
        # Transaction type
        self.transaction_type_combo = QComboBox()
        self.transaction_type_combo.addItems(["Expense", "Income"])
        self.transaction_type_combo.currentTextChanged.connect(self.update_category_options)
        transaction_form_fields.addRow("Transaction Type:", self.transaction_type_combo)
        
        # Transaction amount
        amount_layout = QHBoxLayout()
        amount_layout.addWidget(QLabel("$"))
        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("0.00")
        amount_layout.addWidget(self.amount_input)
        transaction_form_fields.addRow("Transaction Amount:", amount_layout)
        
        # Transaction date
        self.date_input = QDateEdit()
        self.date_input.setDisplayFormat("MM/dd/yy")
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        transaction_form_fields.addRow("Transaction Date:", self.date_input)
        
        # Transaction category
        self.category_combo = QComboBox()
        transaction_form_fields.addRow("Transaction Category:", self.category_combo)
        
        # Transaction tag
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Tag")
        transaction_form_fields.addRow("Transaction Tag (Optional):", self.tag_input)
        
        form_layout.addLayout(transaction_form_fields)
        
        # Submit button
        self.submit_button = QPushButton("Submit Transaction")
        self.submit_button.setStyleSheet("background-color: #CD5C5C; color: white;")
        self.submit_button.clicked.connect(self.submit_transaction)
        form_layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)
        
        right_container.addWidget(transaction_form)
        
        # Spacer
        right_container.addStretch()
        
        # Import/Export buttons container
        import_export_frame = QFrame()
        import_export_frame.setFrameStyle(QFrame.StyledPanel)
        import_export_layout = QHBoxLayout(import_export_frame)

        # Add title for import/export section
        import_export_title = QLabel("Backup & Restore:")
        import_export_title.setFont(QFont("Arial", 10, QFont.Bold))
        import_export_layout.addWidget(import_export_title)

        # Regular Import/Export buttons
        local_backup_layout = QHBoxLayout()
        
        # Import button
        import_button = QPushButton("Import Transactions")
        import_button.setStyleSheet("background-color: #CD5C5C; color: white;")
        import_button.clicked.connect(self.import_transactions)
        local_backup_layout.addWidget(import_button)
        
        # Export button
        export_button = QPushButton("Export Transactions")
        export_button.setStyleSheet("background-color: #CD5C5C; color: white;")
        export_button.clicked.connect(self.export_transactions)
        local_backup_layout.addWidget(export_button)

        import_export_layout.addLayout(local_backup_layout)
        
        # Google Drive Sync section
        drive_sync_layout = QHBoxLayout()

        # Google Drive Sync button
        self.drive_sync_button = QPushButton("Google Drive Sync")
        self.drive_sync_button.setStyleSheet("background-color: #4285F4; color: white;")
        self.drive_sync_button.clicked.connect(self.open_drive_sync_dialog)
        drive_sync_layout.addWidget(self.drive_sync_button)

        # Sync Now button
        self.sync_now_button = QPushButton("Sync Now")
        self.sync_now_button.setStyleSheet("background-color: #4285F4; color: white;")
        self.sync_now_button.clicked.connect(self.sync_to_drive_now)
        
        # Enable/disable based on whether sync is configured
        self.sync_now_button.setEnabled(self.treasure_goblin.drive_sync.config.get('token') is not None)
        drive_sync_layout.addWidget(self.sync_now_button)

        import_export_layout.addLayout(drive_sync_layout)

        # Add sync status indicator
        self.sync_status_label = QLabel()
        self.update_sync_status_label()
        import_export_layout.addWidget(self.sync_status_label)

        right_container.addWidget(import_export_frame)
        
        # Add left and right sides to main layout
        layout.addWidget(transactions_list_container, 1)
        layout.addLayout(right_container, 1)
        
        # Initialize the category options based on the default transaction type
        self.update_category_options()
        
        # Load transactions for the current month
        self.load_transactions_for_month()
        
        return tab
    
    def update_category_options(self):
        """Update category dropdown based on selected transaction type."""
        self.category_combo.clear()

        # Get transaction type (conver to lowercase for database query)
        transaction_type = self.transaction_type_combo.currentText().lower()

        # Get categories from database
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM categories WHERE type = ? ORDER BY name",
                (transaction_type,)
            )

            categories = [row[0] for row in cursor.fetchall()]
            self.category_combo.addItems(categories)

            conn.close()
        except Exception as e:
            print(f"Error loading categories: {e}")
    
    def load_transactions_for_month(self):
        """Load transactions for the selected month and year."""
        self.transactions_list_widget.clear()

        # Get selected month and year
        current_index = self.month_combo.currentIndex()
        if current_index >= 0:
            month, year = self.month_combo.itemData(current_index)
        else:
            # Default to current month/year
            today = QDate.currentDate()
            month, year = today.month(), today.year()

        try:
            # Get transactions for the selected month
            conn = self.get_db_connection()
            cursor = conn.cursor()

            query = """
                SELECT t.id, t.date, t.amount, t.type, c.name as category, t.tag
                FROM transactions t 
                JOIN categories c ON t.category_id = c.id 
                WHERE strftime('%m', t.date) = ? AND strftime('%Y', t.date) = ?
                ORDER BY t.date DESC
            """

            cursor.execute(query, (f"{month:02d}", str(year)))

            transactions = []
            for row in cursor.fetchall():
                id, date, amount, type, category, tag = row
                transactions.append({
                    'id': id,
                    'date': date,
                    'amount': amount,
                    'type': type,
                    'category': category,
                    'tag': tag
                })

            conn.close()

            # Add transactions to list widget
            for transaction in transactions:
                # Format date
                date_obj = datetime.fromisoformat(transaction['date']).strftime("%m/%d/%y")

                # Format category and tag
                description = transaction['category']
                if transaction['tag']:
                    description += f" ({transaction['tag']})"

                # Format amount with color based on type
                amount_color = "green" if transaction['type'] == 'income' else "red"
                amount_str = f"${transaction['amount']:.2f}"
                
                # Create a custom widget item
                item = QListWidgetItem()
                item.setData(Qt.UserRole, transaction['id'])  # Store transaction ID

                # Create a label with rich text
                label = QLabel(f"{date_obj} {description} <span style='color:{amount_color}'>{amount_str}</span>")
                label.setTextFormat(Qt.RichText)
                
                # Add item to list and set custom widget
                self.transactions_list_widget.addItem(item)
                self.transactions_list_widget.setItemWidget(item, label)
                
                # Set appropriate item size
                item.setSizeHint(label.sizeHint())
            
        except Exception as e:
            print(f"Error loading transactions: {e}")

    def submit_transaction(self):
        """Handle the submission of a new transaction."""
        try:
            # Get form values
            transaction_type = self.transaction_type_combo.currentText().lower()

            # Validate amount
            amount_text = self.amount_input.text().strip()
            if not amount_text:
                QMessageBox.warning(self, "Invalid Amount", "Please enter a transaction amount.")
                return
            
            try:
                amount = float(amount_text)
                if amount <= 0:
                    QMessageBox.warning(self, "Invalid Amount", "Amount must be greater than zero.")
                    return
            except ValueError:
                QMessageBox.warning(self, "Invalid Amount", "Please enter a valid number for the amount.")
                return
            
            # Get date in ISO format 
            date = self.date_input.date().toString("MM-dd-yyyy")

            # Get category
            category = self.category_combo.currentText()
            if not category:
                QMessageBox.warning(self, "Missing Category", "Please select a transaction category.")
                return
            
            # Get tag (optional)
            tag_text = self.tag_input.text().strip()
            tag = tag_text if tag_text else None

            # Add transaction to database
            transaction_id = self.treasure_goblin.add_transaction(
                transaction_type, amount, date, category, tag
            )

            if transaction_id:
                # Clear form
                self.amount_input.clear()
                self.tag_input.clear()
                self.date_input.setDate(QDate.currentDate())

                # Refresh the transactions list
                self.load_transactions_for_month()

                # Update the dashboard if needed
                self.update_dashboard()

                QMessageBox.information(self, "Success", "Transaction added successfully!")
            else:
                QMessageBox.warning(self, "Error", "Failed to add transaction. Please try again.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {str(e)}")

    def import_transactions(self):
        """Import transactions from zip."""
        # Initialize the import/export helper if it doesn't exist
        if not hasattr(self, 'import_export'):
            self.import_export = TreasureGoblinImportExport(self.treasure_goblin)
        
        # Ask user if they want to merge or replace
        choice_msg = QMessageBox()
        choice_msg.setIcon(QMessageBox.Question)
        choice_msg.setWindowTitle("Import Options")
        choice_msg.setText("How would you like to import transactions?")
        choice_msg.setInformativeText("You can either merge the imported transactions with your existing data, or replace your current financial data entirely.")
        
        merge_button = choice_msg.addButton("Merge", QMessageBox.ActionRole)
        replace_button = choice_msg.addButton("Replace", QMessageBox.ActionRole)
        cancel_button = choice_msg.addButton("Cancel", QMessageBox.RejectRole)
        
        choice_msg.exec_()
        
        # Handle user choice
        if choice_msg.clickedButton() == cancel_button:
            return
        
        merge_mode = (choice_msg.clickedButton() == merge_button)
        
        # Call the import function with the selected mode
        success, message = self.import_export.import_database(merge=merge_mode)
        
        # Show result message
        if success:
            QMessageBox.information(self, "Import Complete", message)
            
            # Refresh UI
            self.update_dashboard()
            self.load_transactions_for_month()
        else:
            QMessageBox.warning(self, "Import Failed", message)

    def export_transactions(self):
        """Export transactions to zip."""
        # Initialize the import/export helper if it doesn't exist
        if not hasattr(self, 'import_export'):
            self.import_export = TreasureGoblinImportExport(self.treasure_goblin)
        
        # Call the export function
        success, message = self.import_export.export_database()
        
        # Show result message
        if success:
            QMessageBox.information(self, "Export Complete", message)
        else:
            QMessageBox.warning(self, "Export Failed", message)

    def update_sync_status_label(self):
        """Update the sync status label based on current sync configuration."""
        drive_sync = self.treasure_goblin.drive_sync

        if not drive_sync.config.get('token'):
            self.sync_status_label.setText("Google Drive Sync: Not configured")
            self.sync_status_label.setStyleSheet("color: gray;")
            return
        last_sync = drive_sync.config.get('last_sync')
        if last_sync:
            try:
                sync_time = datetime.fromisoformat(last_sync)
                last_sync_text = sync_time.strftime("%m/%d/%Y %H:%M")
                self.sync_status_label.setText(f"Last synced: {last_sync_text}")
                self.sync_status_label.setStyleSheet("color: green;")
            except:
                self.sync_status_label.setText("Last sync: Unknown")
                self.sync_status_label.setStyleSheet("color: gray;")
        else:
            self.sync_status_label.setText("Google Drive Sync: Not yet synced")
            self.sync_status_label.setStyleSheet("color: orange;")

    def open_drive_sync_dialog(self):
        """Open the Google Drive sync settings dialog."""
        dialog = GoogleDriveSyncDialog(self, self.treasure_goblin.drive_sync)
        result = dialog.exec_()

        # Update UI elements after the dialog closes
        self.sync_now_button.setEnabled(self.treasure_goblin.drive_sync.config.get('token') is not None)
        self.update_sync_status_label()

    def sync_to_drive_now(self):
        """Perform an immediate sync to Google Drive."""
        # Show progress dialog
        progress_dialog = QDialog(self)
        progress_dialog.setWindowTitle("Syncing to Google Drive")
        progress_dialog.setFixedSize(300, 100)
        
        dialog_layout = QVBoxLayout(progress_dialog)
        
        status_label = QLabel("Syncing data to Google Drive...")
        dialog_layout.addWidget(status_label)
        
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        dialog_layout.addWidget(progress_bar)
        
        # Connect signals
        self._sync_progress_connection = self.treasure_goblin.drive_sync.sync_progress.connect(
        lambda val: self._update_progress_safely(progress_bar, val)
        )
        self._sync_completed_connection = self.treasure_goblin.drive_sync.sync_completed.connect(
            lambda success, message: self._handle_sync_completion_safely(success, message, progress_dialog)
        )
        
        # Start sync in a separate thread
        progress_dialog.show()
        QApplication.processEvents()  # Ensure the dialog shows immediately
        
        # Create and start the thread
        self.sync_thread = threading.Thread(
            target=self.treasure_goblin.drive_sync.sync_now,
            daemon=True
        )
        self.sync_thread.start()

    def handle_sync_completed(self, success, message, dialog):
        """Handle completion of Google Drive sync."""
        dialog.close()
        
        if success:
            QMessageBox.information(self, "Sync Complete", message)
        else:
            QMessageBox.warning(self, "Sync Failed", message)
        
        # Update the status label
        self.update_sync_status_label()

    def closeEvent(self, event):
        """Handle application close event."""
        # Check if we need to sync with Google Drive
        if hasattr(self.treasure_goblin, 'drive_sync'):
            if self.treasure_goblin.drive_sync.should_sync_on_close():
                reply = QMessageBox.question(
                    self, 
                    "Sync to Google Drive", 
                    "Sync your data to Google Drive before closing?",
                    QMessageBox.Yes | QMessageBox.No, 
                    QMessageBox.Yes
                )
                
                if reply == QMessageBox.Yes:
                    # Show a progress dialog
                    progress_dialog = QDialog(self)
                    progress_dialog.setWindowTitle("Syncing to Google Drive")
                    progress_dialog.setFixedSize(300, 100)
                    
                    dialog_layout = QVBoxLayout(progress_dialog)
                    
                    status_label = QLabel("Syncing data to Google Drive before closing...")
                    dialog_layout.addWidget(status_label)
                    
                    progress_bar = QProgressBar()
                    progress_bar.setRange(0, 100)
                    progress_bar.setValue(0)
                    dialog_layout.addWidget(progress_bar)
                    
                    # Connect signals
                    self.treasure_goblin.drive_sync.sync_progress.connect(progress_bar.setValue)
                    self.treasure_goblin.drive_sync.sync_completed.connect(
                        lambda success, message: progress_dialog.close()
                    )
                    
                    # Start sync
                    progress_dialog.show()
                    QApplication.processEvents()
                    
                    # Direct sync (wait for it to complete)
                    success, message = self.treasure_goblin.drive_sync.sync_now()
                    progress_dialog.close()
                    
                    if not success:
                        QMessageBox.warning(self, "Sync Failed", message)
        
        # Accept the close event
        event.accept()

    def create_categories_tab(self):
        """Create the categories tab for managing transaction categories."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Categories title
        title_label = QLabel("Transaction Categories:")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_label = QLabel("Transaction Categories:")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title_label)

        # Main content area
        content_frame = QFrame()
        content_frame.setFrameStyle(QFrame.StyledPanel)
        content_layout = QVBoxLayout(content_frame)

        # Category type selector (Income/Expenses)
        type_selector_layout = QHBoxLayout()
        type_selector_layout.addStretch()

        self.expenses_button = QPushButton("Expenses")
        self.expenses_button.setStyleSheet("background-color: #CD5C5C; color: white;")
        self.expenses_button.setCheckable(True)
        self.expenses_button.setChecked(True)
        self.expenses_button.clicked.connect(lambda: self.switch_category_type('expense'))

        self.income_button = QPushButton("Income")
        self.income_button.setStyleSheet("background-color: #CD5C5C; color: white;")
        self.income_button.setCheckable(True)
        self.income_button.clicked.connect(lambda: self.switch_category_type('income'))

        type_selector_layout.addWidget(self.expenses_button)
        type_selector_layout.addWidget(self.income_button)
        content_layout.addLayout(type_selector_layout)

        # Categories grid
        self.categories_grid = QGridLayout()
        self.categories_grid.setSpacing(10)
        content_layout.addLayout(self.categories_grid)

        # Add button for new categories
        add_button = QPushButton("+")
        add_button.setFont(QFont("Arial", 16))
        add_button.setMinimumSize(60, 60)
        add_button.setStyleSheet("background-color: #CD5C5C; color: white;")
        add_button.setStyleSheet("background-color: #CD5C5C; color: white;")
        add_button.clicked.connect(self.add_new_category)

        # Add stretch to push everything to the top
        content_layout.addStretch()

        layout.addWidget(content_frame)

        # Load initial categories (expenses by default)
        self.current_category_type = 'expense'
        self.current_category_type = 'expense'
        self.load_categories()

        return tab
    
    def switch_category_type(self, category_type):
        """Switch between income and expense categories."""
        if category_type == 'expense':
            self.expenses_button.setChecked(True)
            self.income_button.setChecked(False)
            self.current_category_type = 'expense'
        else:
            self.expenses_button.setChecked(False)
            self.income_button.setChecked(True)
            self.current_category_type = 'income'

        self.load_categories()

    def load_categories(self):
        """Load categories of the current type from the database."""
        # Clear existing categories
        while self.categories_grid.count():
            item = self.categories_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            # Get categories from database
            conn = self.get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                    "SELECT id, name FROM categories WHERE type = ?",
                    (self.current_category_type,)
            )

            categories = cursor.fetchall()
            conn.close()

            # Add categories to grid
            row, col = 0,0
            max_cols = 4 # Number of columns in the grid

            for category_id, category_name in categories:
                category_button = QPushButton(category_name)
                category_button.setMinimumSize(80, 60)

                # Set different colors based on category type
                if self.current_category_type == 'expense':
                    category_button.setStyleSheet("background-color: #CC0000; color: white;")
                else:
                    category_button.setStyleSheet("background-color: #008800; color: white;")

                # Set up context menu for edit/delete
                category_button.setContextMenuPolicy(Qt.CustomContextMenu)
                category_button.customContextMenuRequested.connect(
                    lambda pos, cid=category_id, cname=category_name: self.show_category_context_menu(pos, cid, cname)
                )

                self.categories_grid.addWidget(category_button, row, col)

                # Update grid positive
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

            # Add the "+" button at the end
            add_button = QPushButton("+")
            add_button.setFont(QFont("Arial", 16))
            add_button.setMinimumSize(80, 60)
            add_button.setStyleSheet("background-color: #CD5C5C; color: white;")
            add_button.clicked.connect(self.add_new_category)

            self.categories_grid.addWidget(add_button, row if col == 0 else row, col)

        except Exception as e:
            print(f"Error loading categories: {e}")

    def show_category_context_menu(self, pos, category_id, category_name):
        """Show context menu for a category button."""
        menu = QMenu()
        edit_action = menu.addAction("Edit")
        delete_action = menu.addAction("Delete")

        # Get global position for the menu
        global_pos = self.sender().mapToGlobal(pos)
        action = menu.exec_(global_pos)

        if action == edit_action:
            self.edit_category(category_id, category_name)
        elif action == delete_action:
            self.delete_category(category_id, category_name)

    def add_new_category(self):
        """Add a new category."""
        category_name, ok = QInputDialog.getText(
            self, "Add Category", "Enter category name:"
        )
    
        if ok and category_name:
            try:
                conn = self.get_db_connection()
                cursor = conn.cursor()
            
                # Check if category already exists
                cursor.execute(
                    "SELECT id FROM categories WHERE name = ? AND type = ?",
                    (category_name, self.current_category_type)
                )
            
                if cursor.fetchone():
                    QMessageBox.warning(
                        self, "Duplicate Category", 
                        f"A {self.current_category_type} category named '{category_name}' already exists."
                )
                else:
                    # Add new category
                    cursor.execute(
                        "INSERT INTO categories (name, type) VALUES (?, ?)",
                        (category_name, self.current_category_type)
                    )
                    conn.commit()
                    QMessageBox.information(
                        self, "Success", f"Category '{category_name}' added successfully!"
                    )
                    # Reload categories
                    self.load_categories()
            
                conn.close()
            
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add category: {str(e)}")

    def edit_category(self, category_id, current_name):
        """Edit an existing category."""
        new_name, ok = QInputDialog.getText(
            self, "Edit Category", "Enter new category name:",
            text=current_name
        )

        if ok and new_name and new_name != current_name:
            try:
                conn = self.get_db_connection()
                cursor = conn.cursor()

                # Check if the new name already exists
                cursor.execute(
                    "SELECT id FROM categories WHERE name =? AND type = ? AND id != ?",
                        (new_name, self.current_category_type, category_id)
                )

                if cursor.fetchone():
                    QMessageBox.warning(
                        self, "Duplicate Category",
                        f"A {self.current_category_type} category named '{new_name}' already exists"
                    )
                else:
                    # Update category name
                    cursor.execute(
                        "UPDATE categories SET name = ? WHERE id = ?",
                            (new_name, category_id)
                    )
                    conn.commit()
                    QMessageBox.information(
                        self, "Success", f"Category renamed to '{new_name}' successfully!"
                    )
                    # Reload categories
                    self.load_categories()

                conn.close()

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update category: {str(e)}")

    def delete_category(self, category_id, category_name):
        """Delete a category after confirmation."""
        # Check if category is in use
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT COUNT(*) FROM transactions WHERE category_id = ?",
                    (category_id,)
            )
            
            usage_count = cursor.fetchone()[0]

            if usage_count > 0:
                reply = QMessageBox.question(
                    self, "Category In Use",
                    f"The category '{category_name}' is used in {usage_count} transactions. "
                    "Deleting it will affect those transactions. Proceed?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )

                if reply != QMessageBox.Yes:
                    conn.close()
                    return
            else:
                reply = QMessageBox.question(
                    self, "Confirm Deletion",
                    f"Are you sure you want to delete the category '{category_name}'?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )

                if reply != QMessageBox.Yes:
                    conn.close()
                    return

            # Delete the category
            cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
            conn.commit()

            QMessageBox.information(
                self, "Success", f"Category '{category_name}' deleted successfully!"
            )

            # Reload categories
            self.load_categories()

            conn.close()
    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete category: {str(e)}")


    def get_db_connection(self):
        """Get a connection to the SQLite database."""
        try:
            conn = sqlite3.connect(self.treasure_goblin.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to connect to database: {str(e)}")
            return None
        

    def create_reports_tab(self):
        """Create the reports tab with visualizations of financial data."""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        # Main content area
        content_frame = QFrame()
        content_frame.setFrameStyle(QFrame.StyledPanel)
        content_layout = QVBoxLayout(content_frame)

        # Controls section
        top_controls_layout = QHBoxLayout()

        # Left side - Transaction type toggle (Expenses/Income)
        type_toggle_layout = QHBoxLayout()
        self.report_expenses_button = QPushButton("Expenses")
        self.report_expenses_button.setCheckable(True)
        self.report_expenses_button.setChecked(True)
        self.report_expenses_button.setStyleSheet("background-color: #CD5C5C; color: white;")
        self.report_expenses_button.clicked.connect(lambda: self.switch_report_type('expense'))

        self.report_income_button = QPushButton("Income")
        self.report_income_button.setCheckable(True)
        self.report_income_button.setStyleSheet("background-color: #CD5C5C; color: white;")
        self.report_income_button.clicked.connect(lambda: self.switch_report_type('income'))

        type_toggle_layout.addWidget(self.report_expenses_button)
        type_toggle_layout.addWidget(self.report_income_button)
        top_controls_layout.addLayout(type_toggle_layout)

        # Center - Current period display with nav buttons
        period_navigation_layout = QHBoxLayout()

        # Previous period button
        self.prev_period_button = QPushButton("<")
        self.prev_period_button.setFixedWidth(30)
        self.prev_period_button.clicked.connect(self.go_to_prev_period)
        period_navigation_layout.addWidget(self.prev_period_button)

        # Current period label
        self.report_period_label = QLabel()
        self.report_period_label.setAlignment(Qt.AlignCenter)
        self.report_period_label.setFont(QFont("Arial", 14, QFont.Bold))
        period_navigation_layout.addWidget(self.report_period_label, 1)

        # Next period button
        self.next_period_button = QPushButton(">")
        self.next_period_button.setFixedWidth(30)
        self.next_period_button.clicked.connect(self.go_to_next_period)
        period_navigation_layout.addWidget(self.next_period_button)

        top_controls_layout.addLayout(period_navigation_layout)

        # Right side - Time period toggle (Monthly/Yearly)
        period_toggle_layout = QHBoxLayout()
        self.report_monthly_button = QPushButton("Monthly")
        self.report_monthly_button.setCheckable(True)
        self.report_monthly_button.setChecked(True)
        self.report_monthly_button.setStyleSheet("background-color: #CD5C5C; color: white;")
        self.report_monthly_button.clicked.connect(lambda: self.switch_report_period('monthly'))

        self.report_yearly_button = QPushButton("Yearly")
        self.report_yearly_button.setCheckable(True)
        self.report_yearly_button.setStyleSheet("background-color: #CD5C5C; color: white;")
        self.report_yearly_button.clicked.connect(lambda: self.switch_report_period('yearly'))

        period_toggle_layout.addWidget(self.report_monthly_button)
        period_toggle_layout.addWidget(self.report_yearly_button)
        top_controls_layout.addLayout(period_toggle_layout)

        content_layout.addLayout(top_controls_layout)

        # Chart area
        self.chart_area = QLabel()
        self.chart_area.setMinimumHeight(400)
        self.chart_area.setStyleSheet("background-color: #E0E0E0;")
        self.chart_layout = QVBoxLayout(self.chart_area)
        content_layout.addWidget(self.chart_area)

        # Bottom controls - Chart type toggle (Pie/Bar)
        bottom_controls_layout = QHBoxLayout()
        bottom_controls_layout.addStretch()

        self.pie_chart_button = QPushButton("Pie")
        self.pie_chart_button.setCheckable(True)
        self.pie_chart_button.setChecked(True)
        self.pie_chart_button.setStyleSheet("background-color: #CD5C5C; color: white;")
        self.pie_chart_button.clicked.connect(lambda: self.switch_chart_type('pie'))

        self.bar_chart_button = QPushButton("Bar")
        self.bar_chart_button.setCheckable(True)
        self.bar_chart_button.setStyleSheet("background-color: #CD5C5C; color: white;")
        self.bar_chart_button.clicked.connect(lambda: self.switch_chart_type('bar'))

        bottom_controls_layout.addWidget(self.pie_chart_button)
        bottom_controls_layout.addWidget(self.bar_chart_button)

        content_layout.addLayout(bottom_controls_layout)

        main_layout.addWidget(content_frame)

        # Initialize state
        self.current_report_type = 'expense'
        self.current_report_period = 'monthly'
        self.current_chart_type = 'pie'

        # Initialize current date for reports (use current date)
        self.current_report_date = QDate.currentDate()
        self.update_report_period_label()

        # Load intial report
        self.generate_report()

        return tab
    
    def update_report_period_label(self):
        """Update the period label based on current settings."""
        if self.current_report_period == 'monthly':
            self.report_period_label.setText(self.current_report_date.toString("MMMM yyyy"))
        else: # yearly
            self.report_period_label.setText(str(self.current_report_date.year()))

    def go_to_prev_period(self):
        """Go to the previous month or year."""
        if self.current_report_period == 'monthly':
            # Go to previous month
            self.current_report_date = self.current_report_date.addMonths(-1)
        else:
            # Go to previous year
            self.current_report_date = self.current_report_date.addYears(-1)

        self.update_report_period_label()
        self.generate_report()

    def go_to_next_period(self):
        """Go to the next month or year."""
        if self.current_report_period == 'monthly':
            # Go to next month
            self.current_report_date = self.current_report_date.addMonths(1)
        else:
            # Go to next year
            self.current_report_date = self.current_report_date.addYears(1)

        self.update_report_period_label()
        self.generate_report()

    def switch_report_type(self, report_type):
        """Switch between expense and income reports."""
        if report_type == 'expense':
            self.report_expenses_button.setChecked(True)
            self.report_income_button.setChecked(False)
        else:
            self.report_expenses_button.setChecked(False)
            self.report_income_button.setChecked(True)
        
        self.current_report_type = report_type
        self.update_report_period_label()
        self.generate_report()

    def switch_report_period(self, period):
        """Switch between monthly and yearly reports."""
        if period == 'monthly':
            self.report_monthly_button.setChecked(True)
            self.report_yearly_button.setChecked(False)
        else: # period == 'yearly'
            self.report_monthly_button.setChecked(False)
            self.report_yearly_button.setChecked(True)

        self.current_report_period = period
        self.update_report_period_label()
        self.generate_report()

    def switch_chart_type(self, chart_type):
        """Switch between pie and bar charts."""
        if chart_type == 'pie':
            self.pie_chart_button.setChecked(True)
            self.bar_chart_button.setChecked(False)
        else:
            self.pie_chart_button.setChecked(False)
            self.bar_chart_button.setChecked(True)

        self.current_chart_type = chart_type
        self.generate_report()

    def generate_report(self):
        """Generate and display the report based on current settings."""
        try:
            # Get date range for query
            start_date, end_date = self.get_report_date_range()

            # Get data based on report type
            data = self.get_report_data(start_date, end_date)

            if not data:
                print("No data found for this period")
                self.display_no_data_message()
                return

            # Display chart based on chart type
            if self.current_chart_type == 'pie':
                self.display_pie_chart(data)
            else:
                self.display_bar_chart(data)
        
        except Exception as e:
            print(f"Error generating report: {str(e)}")
            self.display_error_message(str(e))

    def get_report_date_range(self):
        """Calculate the date range for the current report settings."""
        if self.current_report_period == 'monthly':
            # Start of month
            start_date = QDate(self.current_report_date.year(),
                               self.current_report_date.month(), 1)
            
            # End of month - calculate last day
            if self.current_report_date.month() == 12:
                end_date = QDate(self.current_report_date.year(), 12, 31)
            else:
                next_month = QDate(self.current_report_date.year(),
                                   self.current_report_date.month() + 1, 1)
                end_date = next_month.addDays(-1)
        else:
            # Start of year
            start_date = QDate(self.current_report_date.year(), 1, 1)

            # End of year
            end_date = QDate(self.current_report_date.year(), 12, 31)

        # Convert to strings for SQL query
        start_date_str = start_date.toString("yyyy-MM-dd")
        end_date_str = end_date.toString("yyyy-MM-dd")

        return start_date_str, end_date_str
    
    def get_report_data(self, start_date, end_date):
        """Get data for the current report from the database."""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        check_query = """
            SELECT COUNT(*) as count,
                    MIN(date) as earliest_date,
                    MAX(date) as latest_date
            FROM transactions t
            WHERE t.type = ? AND t.date BETWEEN ? AND ?
        """

        cursor.execute(check_query, (self.current_report_type, start_date, end_date))
        check_result = cursor.fetchone()

        query = """
            SELECT
                c.name as category,
                SUM(t.amount) as total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.type = ? AND t.date BETWEEN ? AND ?
            GROUP BY c.name
            ORDER BY total DESC
        """

        cursor.execute(query, (self.current_report_type, start_date, end_date))
        data = cursor.fetchall()

        conn.close()

        return data
    
    def display_no_data_message(self):
        """Display a message when no data is available."""
        # Clear existing layout
        self.clear_chart_area()

        # Add no data message
        message = QLabel("No transactions found for this period.")
        message.setAlignment(Qt.AlignCenter)
        message.setStyleSheet("font-size: 16px;")
        self.chart_area.layout().addWidget(message)

    def clear_chart_area(self):
        """Clear all widgets from the chart area layout."""
        if self.chart_layout is not None:
            while self.chart_layout.count():
                item = self.chart_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

    def display_error_message(self, error_message):
        """Display an errror message in the chart area."""
       # Clear existing layout
        self.clear_chart_area()
        
        # Add error message
        message = QLabel(f"Error loading report: {error_message}")
        message.setAlignment(Qt.AlignCenter)
        message.setStyleSheet("color: red; font-size: 14px;")
        self.chart_layout.addWidget(message)

    def display_pie_chart(self, data):
        """Display a pie chart visualization"""
        # Clear the existing chart area
        self.clear_chart_area()
        
        if not data:
            self.display_no_data_message()
            return

        # Extract categories and amounts
        categories = [item[0] for item in data]
        amounts = [item[1] for item in data]

        # Create a figure and a set of subplots
        figure = Figure(figsize=(6, 6), dpi=100)
        canvas = FigureCanvas(figure)
        ax = figure.add_subplot(111)

        # Create the pie chart
        wedges, texts, autotexts = ax.pie(
            amounts, 
            labels=categories,
            autopct='%1.1f%%',
            startangle=90,
            shadow=False,
            wedgeprops={'edgecolor': 'w', 'linewidth': 1},
            textprops={'fontsize': 10, 'fontweight': 'bold'}
        )

        # Equal aspect ratio ensures that the pie is drawn as a circle
        ax.axis('equal')

        # Add title based on current report settings
        period_text = self.report_period_label.text()
        type_text = "Income" if self.current_report_type == 'income' else "Expenses"
        ax.set_title(f"{type_text} Breakdown - {period_text}", fontsize=14, fontweight='bold')

        # Set the background color of the figure to match the application
        figure.patch.set_facecolor('#E0E0E0')

        # Add the pie chart to the chart area
        self.chart_layout.addWidget(canvas)

    def display_bar_chart(self, data):
        """Display a bar chart visualization"""
        # Clear the existing chart area
        self.clear_chart_area()

        if not data:
            self.display_no_data_message()
            return
        
        # Extract categories and amounts
        categories = [item[0] for item in data]
        amounts = [item[1] for item in data]

        # Create a figure and a set of subplots
        figure = Figure(figsize=(8, 6), dpi=100)
        canvas = FigureCanvas(figure)
        ax = figure.add_subplot(111)

        # Create a horizontal bar chart
        bars = ax.barh(categories, amounts, color='#CD5C5C')

        # Add data labels to the right of each bar
        for bar in bars:
            width = bar.get_width()
            ax.text(width + 0.3, bar.get_y() + bar.get_height()/2,
                    f'${width:.2f}', ha='left', va='center', fontweight='bold')
            
        # Remove the top and right spines
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Add gridlines
        ax.grid(axis='x', linestyle='--', alpha=0.7)

        # Add title based on current report settings
        period_text = self.report_period_label.text()
        type_text = "Income" if self.current_report_type == 'income' else "Expenses"
        ax.set_title(f"{type_text} Breakdown - {period_text}", fontsize=14, fontweight='bold')

        # Set the background color of the figure to match the application
        figure.patch.set_facecolor('#E0E0E0')

        # Set x-axis label
        ax.set_xlabel('Amount ($)', fontweight='bold')

        # Set up the chart layout
        figure.tight_layout()

        # Add the bar chart to the chart area
        self.chart_layout.addWidget(canvas)
       
class TreasureGoblinImportExport:
    """Helper class for handling import/export operations in TreasureGoblin."""
 
 
    def __init__(self, treasure_goblin):
        """
        Initialize with a reference to the TreasureGoblin instance.

        Args: 
        Args: 
            treasure_goblin: Reference to the TreasureGoblin instance
        """
        self.treasure_goblin = treasure_goblin

    def export_database(self):
        """
        Export the entire database to a zip archive.
        
        Returns:
            Tuple (success: bool, message: str) indicating operation result
        """
        try:
            # Ask user for export location
            export_file, _ = QFileDialog.getSaveFileName(
                None, 
                "Export Financial Data", 
                str(Path.home() / "TreasureGoblin_Export.zip"),
                "Zip Files (*.zip)"
            )
            
            if not export_file:
                return False, "Export cancelled"
            
            # Get database path
            db_path = self.treasure_goblin.db_path

            # Create a timestamp for the backup file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"treasuregoblin_backup_{timestamp}.zip"
            
            # Create a temporary directory for the export
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Copy database file
                db_dest = temp_path / "treasuregoblin.db"
                shutil.copy2(db_path, db_dest)
                
                # Create metadata file
                metadata = {
                    "export_date": datetime.now().isoformat(),
                    "app_version": "1.0",
                    "transaction_count": self._get_transaction_count()
                }
                
                with open(temp_path / "metadata.json", "w") as f:
                    json.dump(metadata, f, indent=2)
                
                # Create the zip file
                with zipfile.ZipFile(export_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    # Add database and metadata files
                    zipf.write(db_dest, "treasuregoblin.db")
                    zipf.write(temp_path / "metadata.json", "metadata.json")

            # Store the path for later reference
            self.last_export_path = export_file
            
            return True, f"Successfully exported to {export_file}"
        
        except Exception as e:
            return False, f"Export failed: {str(e)}"
    
    def _get_transaction_count(self):
        """
        Get count of transactions in the database.
        
        Returns:
            Dict containing transaction counts by type and total
        """
        try:
            conn = self.treasure_goblin.get_db_connection()
            cursor = conn.cursor()
            
            # Get total count
            cursor.execute("SELECT COUNT(*) FROM transactions")
            total = cursor.fetchone()[0]
            
            # Get income count
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE type = 'income'")
            income = cursor.fetchone()[0]
            
            # Get expense count
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE type = 'expense'")
            expense = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "total": total,
                "income": income,
                "expense": expense
            }
        except:
            return {"total": 0, "income": 0, "expense": 0}
        
    def import_database(self, merge=True):
        """
        Import a database from a previously exported zip archive.
        
        Args:
            merge: If True, merge imported transactions with existing ones. 
                  If False, replace the existing database.
        
        Returns:
            Tuple (success: bool, message: str) indicating operation result
        """
        try:
            # Ask user for import file
            import_file, _ = QFileDialog.getOpenFileName(
                None, 
                "Import Financial Data", 
                str(Path.home()),
                "Zip Files (*.zip)"
            )
            
            if not import_file:
                return False, "Import cancelled"
            
            # Confirm import
            confirm_msg = QMessageBox()
            confirm_msg.setIcon(QMessageBox.Warning)
            confirm_msg.setWindowTitle("Confirm Import")
            
            if merge:
                confirm_msg.setText("Merge imported transactions with your current data?")
                confirm_msg.setInformativeText("This will add the imported transactions to your existing financial history.")
            else:
                confirm_msg.setText("Importing will replace your current financial data.")
                confirm_msg.setInformativeText("Are you sure you want to proceed? This cannot be undone.")
            
            confirm_msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            confirm_msg.setDefaultButton(QMessageBox.No)
            
            if confirm_msg.exec_() != QMessageBox.Yes:
                return False, "Import cancelled"
            
            # Get database path
            db_path = self.treasure_goblin.db_path
            
            # Create a temporary directory for the import
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Close all existing database connections first
                try:
                    conn = self.treasure_goblin.get_db_connection()
                    conn.close()
                except:
                    pass
                
                # Extract the zip file
                with zipfile.ZipFile(import_file, 'r') as zipf:
                    zipf.extractall(temp_path)
                
                # Verify this is a valid export
                if not (temp_path / "treasuregoblin.db").exists():
                    return False, "Invalid export file: Missing database"
                
                if not (temp_path / "metadata.json").exists():
                    return False, "Invalid export file: Missing metadata"
                
                # Read metadata
                with open(temp_path / "metadata.json", "r") as f:
                    metadata = json.load(f)
                
                import_db_path = temp_path / "treasuregoblin.db"
                
                if merge:
                    # Merge databases
                    imported_count, skipped_count = self._merge_databases(db_path, import_db_path)
                    return True, f"Successfully imported and merged {imported_count} transactions. {skipped_count} duplicate transactions were skipped."
                else:
                    
                    # Create a backup of the current database
                    backup_path = str(db_path) + ".backup"
                    shutil.copy2(db_path, backup_path)
                    
                   # Make sure SQLite isn't using the file
                    import time
                    
                    # Close connections and wait a moment for OS to release file locks
                    time.sleep(0.5)  
                    
                    # Copy the file
                    try:
                        shutil.copy2(import_db_path, db_path)
                    except PermissionError:
                        # If we still have permission issues, try an alternative approach
                        with open(import_db_path, 'rb') as src, open(db_path, 'wb') as dst:
                            dst.write(src.read())
                    
                    transaction_count = metadata.get("transaction_count", {})
                    total_count = transaction_count.get("total", "unknown")
                    
                    return True, f"Successfully imported {total_count} transactions"
            
        except Exception as e:
            # Restore from backup if available and not merging
            if not merge and 'backup_path' in locals():
                try:
                    shutil.copy2(backup_path, db_path)
                except Exception as backup_error:
                    return False, f"Import failed: {str(e)}\nAlso failed to restore backup: {str(backup_error)}"
            
            return False, f"Import failed: {str(e)}"
        
    def _merge_databases(self, current_db_path, import_db_path):
        """
        Merge two SQLite databases, importing transactions from import_db to current_db.
        
        Args:
            current_db_path: Path to the current database
            import_db_path: Path to the database being imported
        
        Returns:
            Number of transactions imported
        """
        # Connect to current database
        current_conn = None
        import_conn = None
        
        try:
            # Track how many transactions we import and skip
            imported_count = 0
            skipped_count = 0
            
            # Open connections with retry logic
            for attempt in range(3):
                try:
                    # Connect to current database
                    current_conn = sqlite3.connect(current_db_path)
                    current_cursor = current_conn.cursor()
                    
                    # Connect to imported database
                    import_conn = sqlite3.connect(f"file:{import_db_path}?mode=ro", uri=True)  # Read-only mode
                    import_conn.row_factory = sqlite3.Row
                    import_cursor = import_conn.cursor()
                    break
                except sqlite3.OperationalError as e:
                    if attempt == 2:  # Last attempt failed
                        raise e
                    import time
                    time.sleep(1)  # Wait before retrying
            
            # Enable foreign keys
            current_cursor.execute("PRAGMA foreign_keys = ON")
            
            # Begin transaction
            current_conn.execute("BEGIN TRANSACTION")
            
            # Get all categories from the import database
            import_cursor.execute("SELECT id, name, type FROM categories")
            categories = import_cursor.fetchall()
            
            # Get existing categories to avoid duplicates
            current_cursor.execute("SELECT id, name, type FROM categories")
            existing_categories = {(row[1], row[2]): row[0] for row in current_cursor.fetchall()}
            
            # Import categories
            category_mapping = {}  # Maps imported category IDs to existing/new category IDs
            
            for category in categories:
                cat_id, cat_name, cat_type = category
                
                # If category name already exists, map to existing ID
                if (cat_name, cat_type) in existing_categories:
                    category_mapping[cat_id] = existing_categories[(cat_name, cat_type)]
                else:
                    # Otherwise, insert the category
                    current_cursor.execute(
                        "INSERT INTO categories (name, type) VALUES (?, ?)",
                        (cat_name, cat_type)
                    )
                    new_id = current_cursor.lastrowid
                    category_mapping[cat_id] = new_id
            
            # Get existing transactions to check for duplicates
            current_cursor.execute("""
                SELECT t.date, t.amount, t.type, c.name
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
            """)
            existing_transactions = set()
            for row in current_cursor.fetchall():
                date, amount, type_val, category = row
                # Ensure consistent formatting for comparison
                date_str = date.strip() if isinstance(date, str) else date
                amount_float = float(amount)
                existing_transactions.add((date_str, amount_float, type_val, category))
            
            # Import transactions from source database
            import_cursor.execute("""
                SELECT t.id, t.type, t.amount, t.date, t.category_id, t.tag, c.name as category_name
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
            """)
            
            transactions = import_cursor.fetchall()
            
            # Process each transaction
            for transaction in transactions:
                transaction_dict = dict(transaction)
                transaction_dict = dict(transaction)
                transaction_dict = dict(transaction)
                
                # Create tuple for duplicate checking
                transaction_tuple = (
                    transaction_dict['date'].strip() if isinstance(transaction_dict['date'], str) else transaction_dict['date'],
                    float(transaction_dict['amount']), 
                    transaction_dict['type'],
                    transaction_dict['category_name']
                )
                
                # Skip if this transaction already exists
                if transaction_tuple in existing_transactions:
                    skipped_count += 1
                    continue
                
                # Update category ID mapping
                mapped_category_id = category_mapping.get(transaction_dict['category_id'])
                if mapped_category_id is None:
                    # If no mapping exists (unusual case), use a default category
                    default_query = "SELECT id FROM categories WHERE type = ? LIMIT 1"
                    current_cursor.execute(default_query, (transaction_dict['type'],))
                    result = current_cursor.fetchone()
                    if result:
                        mapped_category_id = result[0]
                    else:
                        # Create a default category if none exists
                        default_name = "Other Income" if transaction_dict['type'] == 'income' else "Other Expense"
                        current_cursor.execute(
                            "INSERT INTO categories (name, type) VALUES (?, ?)",
                            (default_name, transaction_dict['type'])
                        )
                        mapped_category_id = current_cursor.lastrowid
                
                # Insert transaction with a new ID (don't preserve old IDs)
                current_cursor.execute("""
                    INSERT INTO transactions 
                    (type, amount, date, category_id, tag)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    transaction_dict['type'], 
                    transaction_dict['amount'],
                    transaction_dict['date'], 
                    mapped_category_id, 
                    transaction_dict['tag']
                ))
                
                # Add to existing set to avoid duplicates in the import file
                existing_transactions.add(transaction_tuple)
                imported_count += 1
            
            # Commit all changes
            current_conn.commit()
            
            return imported_count, skipped_count
            
        except Exception as e:
            # Roll back on error
            if current_conn:
                current_conn.rollback()
            raise e
            
        finally:
            # Close connections
            if current_conn:
                current_conn.close()
            if import_conn:
                import_conn.close()
    
class GoogleDriveSync(QObject):
    """Class for handling Google Drive synchronization of TreasureGoblin data."""

    # Define signals, for UI updates
    sync_started = pyqtSignal()
    sync_completed = pyqtSignal(bool, str) # Success flag and message
    sync_progress = pyqtSignal(int) # Progress percentage

    # Scopes required for Google Drive API
    SCOPES = ['https://www.googleapis.com/auth/drive.file']

    def __init__(self, treasure_goblin):
        super().__init__()
        self.treasure_goblin = treasure_goblin
        self.app_dir = treasure_goblin.app_dir
        self.config_file = self.app_dir / "drive_sync.json"

        # Default configuration
        self.config = {
            'sync_enabled': False,
            'sync_frequency': 'manual', # 'manual, 'app_close', 'daily', 'weekly', 'monthly'
            'last_sync': None,
            'sync_folder_id': None, # Google Drive folder ID wher backups are stored
            'sync_file_id': None, # Latest file ID on Google Drive
            'token': None # OAuth token info
        }

        # Load existing configuration if available
        self.load_config()

    def load_config(self):
        """Load Google Drive sync configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    saved_config = json.load(f)
                    
                    # Update config with saved values
                    self.config.update(saved_config)
            except Exception as e:
                print(f"Error loading Drive sync config: {e}")

    def save_config(self):
        """Save Google Drive sync configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent = 2)
        except Exception as e:
            print(f"Error saving Drive sync config: {e}")

    def get_credentials(self):
        """Get and refresh Google Drive API credentials."""
        creds = None

        # Load token from config if available
        if self.config['token']:
            creds = Credentials.from_authorized_user_info(self.config['token'], self.SCOPES)

        # If credentials are invalid or expired, refresh or authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing credentials: {e}")
                    return None
            else:
                # Look for client secret file with the full filename
                try:
                    # Define the path to the client secret file
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    client_config_file = os.path.join(
                        script_dir, 
                        "client_secret_201372032136-ev7nhopm297avo3lotgufftvlb6kgao2.apps.googleusercontent.com.json"
                    )
                    
                    # Check if the file exists
                    if not os.path.exists(client_config_file):
                        # Try in app_dir as fallback
                        client_config_file = self.app_dir / "client_secret_201372032136-ev7nhopm297avo3lotgufftvlb6kgao2.apps.googleusercontent.com.json"
                        
                        # If still not found, try with a simpler name
                        if not os.path.exists(client_config_file):
                            client_config_file = self.app_dir / "client_secret.json"
                            
                            # If even simpler name not found, use embedded credentials
                            if not os.path.exists(client_config_file):
                                raise FileNotFoundError("Client secret file not found")
                    
                    # Use the file for authentication
                    flow = InstalledAppFlow.from_client_secrets_file(
                        client_config_file, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                    
                except FileNotFoundError:
                    # Fallback to embedded credentials
                    print("Using embedded credentials as fallback...")
                    client_config = {
                        "installed": {
                            "client_id": self.CLIENT_ID,
                            "client_secret": self.CLIENT_SECRET,
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
                        }
                    }
                    
                    flow = InstalledAppFlow.from_client_config(
                        client_config, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                
            # Save the updated token
            self.config['token'] = json.loads(creds.to_json())
            self.save_config()

        return creds
    
    def get_drive_service(self):
        """Create and return a Google Drive API service instance."""
        creds = self.get_credentials()
        if not creds:
            return None
        
        return build ('drive', 'v3', credentials=creds)
    
    def ensure_backup_folder(self, service):
        """Ensure the TreasureGoblin backup folder exists in Google Drive."""
        folder_id = self.config['sync_folder_id']

        # Check if there is already a folder ID and it exists
        if folder_id:
            try:
                folder = service.files().get(fileId=folder_id).execute()
                return folder_id
            except Exception:
                # Folder doesn't exist, need to create a new one
                folder_id = None

        # Create a new folder
        folder_metadata = {
            'name': 'TreasureGoblin Backups',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        folder = service.files().create(body=folder_metadata, fields='id').execute()
        folder_id = folder.get('id')

        # Save the folder ID
        self.config['sync_folder_id'] = folder_id
        self.save_config()

        return folder_id
    
    def create_backup_file(self):
        """Create a backup zip file of the database."""
        try:
            # Initialize the import/export helper if it doesn't exist already
            if not hasattr(self, 'import_export'):
                self.import_export = TreasureGoblinImportExport(self.treasure_goblin)

            # Use the existing export_database method
            success, message = self.import_export.export_database()

            if success:
                # export_database method shoul return the path to the exported file
                # If it doesn't, parse it from the success message
                if hasattr(self.import_export, 'last_export_path') and self.import_export.last_export_path:
                    return self.import_export.last_export_path
                
                # If export_database doesn't store the path, extract it from the message
                import re
                match = re.search(r"Successfully exported to (.+)", message)
                if match:
                    return match.group(1)
                
                # If we can't get the path from either source, raise a detailed error
                raise Exception(f"Backup was created but couldn't determine file path. Message: {message}")
            else:
                raise Exception(f"Failed to create backup: {message}")
        
        except Exception as e:
            print (f"Error creating backup file: {e}")
            return None # Return None instead of raising to handle it in upload_backup

    def upload_backup(self, backup_file_path):
        """Upload the backup file to Google Drive."""
        try:
            # Check if backup_file is None or empty
            if not backup_file_path:
                return False, "No valid backup file was created. Check previous errors."
            
            service = self.get_drive_service()
            if not service:
                return False, "Failed to connect to Google Drive."
            
            # Ensure backup folder exists
            folder_id = self.ensure_backup_folder(service)

            # Prepare file metadata
            file_metadata = {
                'name': os.path.basename(backup_file_path),
                'parents': [folder_id]
            }

            # Prepare the media upload
            media = MediaFileUpload(
                backup_file_path,
                mimetype='application/zip',
                resumable=True
            )

            # Upload file with progress tracking
            request = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            )

            response = None
            progress = 0

            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    self.sync_progress.emit(progress)

            # Save the file ID
            self.config['sync_file_id'] = response.get('id')
            self.config['last_sync'] = datetime.now().isoformat()
            self.save_config()

            # Ensure 100% progress is shown
            self.sync_progress.emit(100)

            return True, "Backup successfully uploaded to Google Drive"
        
        except Exception as e:
            print(f"Error uploading backup: {e}")
            return False, f"Error uploading backup: {str(e)}"
        
    def sync_now(self):
        """Perform an immediate sync to Google Drive."""
        self.sync_started.emit()

        try:
            # Create backup file
            backup_file_path = self.create_backup_file()

            # Upload to Google Drive
            success, message = self.upload_backup(backup_file_path)

            # Emit completion signal
            self.sync_completed.emit(success, message)

            return success, message
        
        except Exception as e:
            error_message = f"Sync failed: {str(e)}"
            self.sync_completed.emit(False, error_message)
            return False, error_message
        
    def should_sync_on_close(self):
        """Check if backup should be synced on application close."""
        if not self.config['sync_enabled']:
            return False
        
        frequency = self.config['sync_frequency']

        if frequency == 'app_close':
            return True
        
        if frequency == 'daily':
            # Check if last sync was more than a day ago
            if not self.config['last_sync']:
                return True
            
            last_sync = datetime.fromisoformat(self.config)['last_sync']
            now = datetime.now()
            return (now - last_sync).days >= 1
        
        if frequency == 'weekly':
            # Check if last sync was more than a week ago
            if not self.config['last_sync']:
                return True
            
            last_sync = datetime.fromisoformat(self.config['last_sync'])
            now = datetime.now()
            return (now - last_sync).days >= 7
        
        if frequency == 'monthly':
            # Check if last sync was more than a month ago
            if not self.config['last_sync']:
                return True
            
            last_sync = datetime.fromisoformat(self.config['last_sync'])
            now = datetime.now()
            return (now - last_sync).days >= 30
        
        return False
    
    def sync_on_close(self):
        """Perform sync on application close if needed."""
        if self.should_sync_on_close():
            return self.sync_now()
        return False, "Sync not needed based on current settings."
    
class GoogleDriveSyncDialog(QDialog):
    """Dialog for configuring Google Drive synchronization settings."""

    def __init__(self, parent, drive_sync):
        super().__init__(parent)
        self.drive_sync = drive_sync
        self.init_ui()

    def init_ui(self):
        """Initialize the dialog UI."""
        self.setWindowTitle("Google Drive Sync Settings")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Google Drive status section
        status_group = QGroupBox("Google Drive Status")
        status_layout = QVBoxLayout(status_group)

        if self.drive_sync.config.get('token'):
            status_label = QLabel("Connected to Google Drive")
            status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            status_label = QLabel("Not connected to Google Drive")
            status_label.setStyleSheet("color: gray;")

        status_layout.addWidget(status_label)

        # Google account info if available
        if self.drive_sync.config.get('token'):
            try:
                # Try to extract email from token if available
                token_info = self.drive_sync.config.get('token', {})
                if isinstance(token_info, dict) and 'email' in token_info:
                    email = token_info['email']
                    account_label = QLabel(f"Connected Account: {email}")
            except:
                pass
        
        # Authentication button
        auth_button_text = "Re-Connect" if self.drive_sync.config.get('token') else "Connect to Google Drive"
        self.auth_button = QPushButton(auth_button_text)
        self.auth_button.setStyleSheet("background-color: #4285F4; color: white;")
        self.auth_button.clicked.connect(self.authenticate)
        status_layout.addWidget(self.auth_button)

        # Add info about Google Drive access
        info_label = QLabel(
            "Connecting to Google Drive allows TreasureGoblin to automatically back up " 
            "your financial data. The app will only have access to the files it creates "
            "in a folder named 'TreasureGoblin Backups'."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 9pt;")
        status_layout.addWidget(self.auth_button)

        layout.addWidget(status_group)

        # Enable sync checkbox
        self.enable_sync_checkbox = QCheckBox("Enable automatic Google Drive synchronization")
        self.enable_sync_checkbox.setChecked(self.drive_sync.config.get('sync_enabled', False))
        self.enable_sync_checkbox.setEnabled(self.drive_sync.config.get('token') is not None)
        layout.addWidget(self.enable_sync_checkbox)

        # Sync frequency options
        sync_group = QGroupBox("Sync Frequency")
        sync_layout = QFormLayout(sync_group)

        self.frequency_combo = QComboBox()
        self.frequency_combo.addItem("Manual Only", "manual")
        self.frequency_combo.addItem("Every Time App Closes", "app_close")
        self.frequency_combo.addItem("Once Daily", "daily")
        self.frequency_combo.addItem("Once Weekly", "weekly")
        self.frequency_combo.addItem("Once Monthly", "monthly")
        self.frequency_combo.setEnabled(self.drive_sync.config.get('token') is not None)

        # Set current value
        current_frequency = self.drive_sync.config.get('sync_frequency', 'manual')
        index = self.frequency_combo.findData(current_frequency)
        if index >= 0:
            self.frequency_combo.setCurrentIndex(index)

        sync_layout.addRow("Backup Frequency:", self.frequency_combo)

        # Last sync information
        last_sync = self.drive_sync.config.get('last_sync')
        last_sync_text = "Never" if not last_sync else datetime.fromisoformat(last_sync).strftime("%Y-%m-%d %H:%M:%S")
        self.last_sync_label = QLabel(f"Last Sync: {last_sync_text}")
        sync_layout.addRow("", self.last_sync_label)

        layout.addWidget(sync_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.sync_now_button = QPushButton("Sync Now")
        self.sync_now_button.setStyleSheet("background-color: #4285F4; color: white;")
        self.sync_now_button.clicked.connect(self.sync_now)
        self.sync_now_button.setEnabled(self.drive_sync.config.get('token') is not None)

        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self.save_settings)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.sync_now_button)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        # Progress bar (hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Connect signals
        self.drive_sync.sync_started.connect(self.on_sync_started)
        self.drive_sync.sync_completed.connect(self.on_sync_completed)
        self.drive_sync.sync_progress.connect(self.on_sync_progress)

    def authenticate(self):
        """Handle Google Drive authentication."""
        try:
            # Clear existing token to force new authentication
            self.drive_sync.config['token'] = None
            self.drive_sync.save_config()

            # Get new credentials (will launch browser auth)
            creds = self.drive_sync.get_credentials()

            if creds:
                # Update the UI
                self.setWindowTitle("Google Drive Sync Settings - Connecting...")
                QApplication.processEvents() # Update the UI

                # Test the credentials with a simple API call
                service = self.drive_sync.get_drive_service()
                if service:
                    about = service.about().get(fields="user").execute()
                    if "user" in about and "emailAddress" in about["user"]:
                        email = about["user"]["emailAddress"]
                        self.drive_sync.config['user_email'] = email
                        self.drive_sync.save_config()

                # Refresh the dialog
                self.close()
                new_dialog = GoogleDriveSyncDialog(self.parent(), self.drive_sync)
                new_dialog.exec_()
            else:
                QMessageBox.warning(self, "Authentication Failed", "Failed to connect to Google Drive.")

        except Exception as e:
            QMessageBox.critical(self, "Authentication Error", f"Error during authentication: {str(e)}")

    def sync_now(self):
        """Handle manual sync."""
        # Disable buttons during sync
        self.sync_now_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.cancel_button.setEnabled(False)

        # Show progress bar
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        # Run sync in a separate thread
        threading.Thread(target=self.drive_sync.sync_now, daemon=True).start()

    def on_sync_started(self):
        """Handle sync started signal."""
        # Already being handled from sync_now
        pass

    def on_sync_progress(self, progress):
        """Handle sync progress signal."""
        self.progress_bar.setValue(progress)

    def on_sync_completed(self, success, message):
        """Handle sync completed signal."""
        # Re-enable buttons
        self.sync_now_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.cancel_button.setEnabled(True)

        # Hide the progress bar after a short delay
        QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))

        # Update last sync time if successful
        if success:
            last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.last_sync_label.setText(f"Last Sync: {last_sync}")

        # Show result message
        if success:
            QMessageBox.information(self, "Sync Complete", message)
        else:
            QMessageBox.warning(self, "Sync Failed", message)

    def save_settings(self):
        """Save settings and close dialog."""
        # Update config
        self.drive_sync.config['sync_enabled'] = self.enable_sync_checkbox.isChecked()
        self.drive_sync.config['sync_frequency'] = self.frequency_combo.currentData()

        # Save to file
        self.drive_sync.save_config()

        # Close dialog
        self.accept()


def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)

    app.setStyle("Fusion")
    
    # Create the TreasureGoblin data manager
    treasure_goblin = TreasureGoblin()

    # Create and show the main application window
    main_window = TreasureGoblinApp(treasure_goblin)
    main_window.show()

    # Run the application event loop
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()