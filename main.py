from datetime import datetime, timedelta
import json
import shutil
import sqlite3
import sys
import tempfile
import uuid
import zipfile
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QTextEdit,
                             QListWidget, QCalendarWidget, QFileDialog,
                             QFormLayout, QGroupBox, QSplitter, QTabWidget,
                             QMessageBox, QComboBox,QScrollArea, QFrame, QLineEdit, 
                             QDateEdit, QDateTimeEdit, QSpinBox, QListWidgetItem)
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
            main_layout.addWidget(self.tabs)

            # Create individual tabs
            self.dashboard_tab = self.create_dashboard_tab()
            self.create_transactions_tab = self.create_transactions_tab()
            # self.categories_tab = self.create_categories_tab()
            # self.reports_tab = self.create_reports_tab()

            # Add tabs to the tab widget
            self.tabs.addTab(self.dashboard_tab, "Dashboard")
            self.tabs.addTab(self.create_transactions_tab, "Transactions")
            # self.tabs.addTab(self.categories_tab, "Categories")
            # self.tabs.addTab(self.reports_tab, "Reports")

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
        QMessageBox.information(self, "Not Implemented", "Import functionality is in the works.")

    def export_transactions(self):
        """Export transactions to zip."""
        QMessageBox.information(self, "Not Implemented", "Export functionality is in the works.")

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
