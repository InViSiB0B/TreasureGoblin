from datetime import datetime, timedelta
import json
import shutil
import sqlite3
import sys
import tempfile
import uuid
import zipfile
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
                             QMessageBox, QComboBox,QScrollArea, QFrame, QLineEdit, 
                             QDateEdit, QDateTimeEdit, QSpinBox, QListWidgetItem, QGridLayout, QInputDialog,
                             QMenu)
                             QDateEdit, QDateTimeEdit, QSpinBox, QListWidgetItem, QGridLayout, QInputDialog,
                             QMenu)
from PyQt5.QtCore import Qt, QDate, QDateTime
from PyQt5.QtGui import QIcon, QFont
from pathlib import Path

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
        self.init_ui()

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

            # Connect tab changed signal to categories when switching to Transactions tab
            self.tabs.currentChanged.connect(lambda index: self.update_category_options() if index == 1 else None)


            # Connect tab changed signal to categories when switching to Transactions tab
            self.tabs.currentChanged.connect(lambda index: self.update_category_options() if index == 1 else None)

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
        
        self.nibble_tips = QLabel(
            "I'm Nibble, and I give helpful tips to users\n"
            "about the app and finance facts! My tips\n"
            "change along with my pose whenever the\n"
            "Dashboard page is refreshed or I am clicked!\n"
            "(not implemented here)"
        )
        tips_layout.addWidget(self.nibble_tips)
        
        # Right side - Nibble's image (placeholder)
        nibble_image = QLabel()
        nibble_image.setFixedSize(100, 100)
        nibble_image.setStyleSheet("background-color: lightgreen; border-radius: 50px;")
        
        nibble_container.addWidget(tips_frame)
        nibble_container.addWidget(nibble_image)
        
        layout.addLayout(nibble_container)
        
        # Update dashboard with data
        self.update_dashboard()
        
        return tab
    
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
        
        # Import button
        import_button = QPushButton("Import Transactions")
        import_button.setStyleSheet("background-color: #CD5C5C; color: white;")
        import_button.clicked.connect(self.import_transactions)
        import_export_layout.addWidget(import_button)
        
        # Export button
        export_button = QPushButton("Export Transactions")
        export_button.setStyleSheet("background-color: #CD5C5C; color: white;")
        export_button.clicked.connect(self.export_transactions)
        import_export_layout.addWidget(export_button)
        
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
        end_date_str = end_date.toString("yyy-MM-dd")

        return start_date_str, end_date_str
    
    def get_report_data(self, start_date, end_date):
        """Get data for the current report from the database."""
        conn = self.get_db_connection()
        cursor = conn.cursor()

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
            
            # Create a temporary directory for the export
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Copy database file
                db_dest = temp_path / "treasuregoblin.db"
                shutil.copy2(db_path, db_dest)
                
                # Create metadata file
                metadata = {
                    "export_date": datetime.now().isoformat(),
                    "app_version": "1.0",  # You can update this with actual version
                    "transaction_count": self._get_transaction_count()
                }
                
                with open(temp_path / "metadata.json", "w") as f:
                    json.dump(metadata, f, indent=2)
                
                # Create the zip file
                with zipfile.ZipFile(export_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    # Add database and metadata files
                    zipf.write(db_dest, "treasuregoblin.db")
                    zipf.write(temp_path / "metadata.json", "metadata.json")
            
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