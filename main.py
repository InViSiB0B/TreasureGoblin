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
    habit. Monitor your finances today to create the financial future you deserve, whether that's next month of years
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

    def get_db_connection(self):
        """Establish and return a database connection."""
        return sqlite3.connect(self.db_path)
        
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

    def add_transactions(self, transaction_type, amount, date, category, tag = None):
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
            print("Database error: {e}")
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
            FROM transactions 2
        JOIN categories c ON t.category_id = c.id" \
        """

        params = []

        # Add date filtering if specified
        if month and year:
            query += " WHERE strftime('%m', t.date) = ? AND strftime('%Y'. t.date) = ?"
            params.extended([f"{month:02d}", f"year"])
        elif month:
            query += " WHERE strftime('%m', t.date) = ?"
            params.append(f"{month:02d}")
        elif year:
            query += " WHERE strftime('%m', t.date) = ?"
            params.append(f"{year}")

        # Order by date descending (newest first)
        query += " ORDER BY t.date DESC"

        # Add limit if specified
        if limit:
            query += f"LIMIT {limit}"

        cursor.execute(query, params)

        # Convert to list of dictionaries
        columns = [column[0] for column in cursor.description]
        transactions = []

        for row in cursor.fetchall():
            transaction = dict(zip(columns, row))
            transactions.append(transaction)

        conn.close()
        return transactions
