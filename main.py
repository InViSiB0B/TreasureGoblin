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
                             QMenu, QFileDialog, QDialog, QCheckBox, QProgressBar, QFrame, QGraphicsDropShadowEffect,
                             QHBoxLayout, QVBoxLayout)
from PyQt5.QtCore import Qt, QDate, QDateTime, QObject, pyqtSignal, QTimer, QThread, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIcon, QFont, QPixmap, QPalette, QColor, QLinearGradient, QPainter, QBrush
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import webbrowser
import threading

# TreasureGoblin modules
from theme import TreasureGoblinTheme
from ui.components import (GoblinCard, TreasureButton, MoneyDisplay,
                           CategoryButton, TransactionItemWidget)
from core.models import TreasureGoblin
from services.google_drive import GoogleDriveSync, GoogleDriveSyncDialog
from utils.import_export import TreasureGoblinImportExport

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

            # Set the application icon
            try:
                # Try to load the icon from the same directory as the script
                script_dir = os.path.dirname(os.path.abspath(__file__))
                icon_path = os.path.join(script_dir, "nibble-icon.ico")

                if os.path.exists(icon_path):
                    self.setWindowIcon(QIcon(icon_path))
                else:
                    # Try alternative locations
                    icon_path_alt = os.path.join(script_dir, "icons", "nibble-icon.ico")
                    if os.path.exists(icon_path_alt):
                        self.setWindowIcon(QIcon(icon_path_alt))
                    else:
                        print(f"Icon file not found at {icon_path} or {icon_path_alt}")
            except Exception as e:
                print(f"Error setting application icon: {e}")

            # Apply theme
            self.setStyleSheet(TreasureGoblinTheme.get_stylesheet())

            # Create the central widget and main layout
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            main_layout = QVBoxLayout(central_widget)
            main_layout.setContentsMargins(0, 0, 0, 0)

            # Header with application title
            header = self.create_header()
            main_layout.addWidget(header)

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

    def create_header(self):
        """Create a themed header for the application"""
        header = QWidget()
        header.setFixedHeight(80)
        header.setStyleSheet(f"""
            background-color: {TreasureGoblinTheme.COLORS['surface']};                        
        """)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 10, 20, 10)

        # Title
        title = QLabel("TreasureGoblin")
        title.setStyleSheet(f"""
            color: {TreasureGoblinTheme.COLORS['accent']};    
            font-size: 32px;
            font-weight: bold;
            font-family: Georgia;
        """)
        layout.addWidget(title)

        layout.addStretch()

        return header

    def get_db_connection(self):
        """Relay database connection to the data manager."""
        return self.treasure_goblin.get_db_connection()
    
    def handle_tab_changed(self, index):
        """Handle actions when tabs are changed."""
        # When switching to transactions tab (index 1), update category options
        if index == 1:
            # Update category options for the form
            self.update_category_options()

            #  Refresh the month selector to include any new months from recent transactions
            self.populate_month_selector()

            # Refresh the transaction list to show any changes
            self.load_transactions_for_month()

        # When swtiching to dahsboard tab (index 0), update dashboard
        elif index == 0:
            self.update_dashboard()

        # When switching to reports tab (index 3), refresh the period selector
        elif index == 3:
            # Refresh the reports period selector in case new data was added
            self.populate_month_selector()

    def create_dashboard_tab(self):
        """Create the dashboard tab with summary information."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Welcome section with title
        welcome_title = QLabel("Welcome to TreasureGoblin!")
        welcome_title.setStyleSheet(f"""
            color: {TreasureGoblinTheme.COLORS['accent']};    
            font-size: 18px;
            font-weight: bold;
            font-family: Georgia;
        """)
        layout.addWidget(welcome_title)

        welcome_group = QGroupBox()
        welcome_group.setStyleSheet(f"""
            QGroupBox {{
                background-color: {TreasureGoblinTheme.COLORS['surface']};
                border: 2px solid {TreasureGoblinTheme.COLORS['primary_dark']};
                border-radius: 8px;
                padding-top: 10px;
            }}
        """)
        welcome_layout = QVBoxLayout(welcome_group)
        welcome_text = QLabel(
            "TreasureGoblin is your personal finance companion, helping you track spending and build wealth through smarter money"
            " habits. Monitor your finances today to create the financial future you deserve, whether that's next month or years"
            " from now!"
        )
        welcome_text.setWordWrap(True)
        welcome_text.setStyleSheet("font-size: 16px; line-height: 1.4;")
        welcome_layout.addWidget(welcome_text)
        layout.addWidget(welcome_group)
        
        # Financial Summary section wtih custom title
        summary_title = QLabel("Financial Summary:")
        summary_title.setStyleSheet(f"""
            color: {TreasureGoblinTheme.COLORS['accent']};    
            font-size: 18px;
            font-weight: bold;
            font-family: Georgia;
        """)
        layout.addWidget(summary_title)

        summary_group = QGroupBox()
        summary_group.setStyleSheet(f"""
            QGroupBox {{
                background-color: {TreasureGoblinTheme.COLORS['surface']};
                border: 2px solid {TreasureGoblinTheme.COLORS['primary_dark']};
                border-radius: 8px;
                padding-top: 10px;
            }}
        """)
        summary_layout = QHBoxLayout(summary_group)
        
        # Total balance box
        balance_box = QFrame()
        balance_box.setFrameStyle(QFrame.StyledPanel)
        balance_layout = QVBoxLayout(balance_box)
        
        balance_title = QLabel("Total balance across all accounts:")
        balance_title.setAlignment(Qt.AlignCenter)
        balance_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        balance_layout.addWidget(balance_title)
        
        self.balance_amount = QLabel()
        self.balance_amount.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setBold(True)
        font.setPointSize(24)
        self.balance_amount.setFont(font)
        balance_layout.addWidget(self.balance_amount)
        
        summary_layout.addWidget(balance_box)
        
        # Month-to-date income and expenses box
        mtd_box = QFrame()
        mtd_box.setFrameStyle(QFrame.StyledPanel)
        mtd_layout = QVBoxLayout(mtd_box)
        
        mtd_title = QLabel("Month-to-date income & expenses:")
        mtd_title.setAlignment(Qt.AlignCenter)
        mtd_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        mtd_layout.addWidget(mtd_title)
        
        self.month_income = QLabel()
        self.month_income.setAlignment(Qt.AlignRight)
        self.month_income.setStyleSheet("color: green; font-size: 18px; font-weight: bold;")
        mtd_layout.addWidget(self.month_income)
        
        self.month_expenses = QLabel()
        self.month_expenses.setAlignment(Qt.AlignRight)
        self.month_expenses.setStyleSheet("color: red; font-size: 18px; font-weight: bold;")
        mtd_layout.addWidget(self.month_expenses)
        
        self.month_net = QLabel()
        self.month_net.setAlignment(Qt.AlignRight)
        self.month_net.setStyleSheet("font-size: 18px; font-weight: bold;")
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
        self.comparison_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        comparison_layout.addWidget(self.comparison_title)
        
        self.prev_month_label = QLabel()
        self.prev_month_label.setAlignment(Qt.AlignRight)
        self.prev_month_label.setStyleSheet("font-size: 16px;")
        comparison_layout.addWidget(self.prev_month_label)
        
        self.curr_month_label = QLabel()
        self.curr_month_label.setAlignment(Qt.AlignRight)
        self.curr_month_label.setStyleSheet("font-size: 16px;")
        comparison_layout.addWidget(self.curr_month_label)
        
        self.difference_label = QLabel()
        self.difference_label.setAlignment(Qt.AlignRight)
        self.difference_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        comparison_layout.addWidget(self.difference_label)
        
        summary_layout.addWidget(comparison_box)
        
        layout.addWidget(summary_group)
        
        # Recent Transactions section with custom title
        recent_title = QLabel("Recent Transactions:")
        recent_title.setStyleSheet(f"""
            color: {TreasureGoblinTheme.COLORS['accent']};    
            font-size: 18px;
            font-weight: bold;
            font-family: Georgia;
        """)
        layout.addWidget(recent_title)

        recent_group = QGroupBox()
        recent_group.setStyleSheet(f"""
            QGroupBox {{
                background-color: {TreasureGoblinTheme.COLORS['surface']};
                border: 2px solid {TreasureGoblinTheme.COLORS['primary_dark']};
                border-radius: 8px;
                padding: 0px;
            }}
        """)
        recent_layout = QVBoxLayout(recent_group)
        
        self.transactions_list = QListWidget()
        self.transactions_list.setMaximumHeight(250)
        self.transactions_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {TreasureGoblinTheme.COLORS['surface']};
                border: none;
                border-radius: 0px;
                padding: 8px;
                outline: none;
                font-size: 14px;
            }}
            QListWidget::item {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px;
                margin: 3px 0;
                min-height: 35px;
            }}
            QListWidget::item:selected {{
                background-color: rgba(45, 106, 79, 0.3);
                border: none;
            }}
            QListWidget::item:hover {{
                background-color: rgba(45, 106, 79, 0.15);
                border: none;
            }}
            QListWidget::item:focus {{
                outline: none;
                border: none;
            }}
        """)
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
        self.nibble_tips.setStyleSheet("font-size: 16px; line-height: 1.3;")
        tips_layout.addWidget(self.nibble_tips)
        
        # Right side - Nibble's image
        self.nibble_image_label = QLabel()
        self.nibble_image_label.setFixedSize(140, 140)
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
            color = TreasureGoblinTheme.COLORS['success_light'] if difference >= 0 else TreasureGoblinTheme.COLORS['danger_light']
            self.difference_label.setText(f"$ {difference:.2f} ({percentage:.2f}%)")
            self.difference_label.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")


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
                
                # Create container widget
                item_widget = QWidget()
                item_layout = QHBoxLayout(item_widget)
                item_layout.setContentsMargins(10, 8, 10, 8)

                # Date label
                date_label = QLabel(date_obj)
                date_label.setStyleSheet(f"""
                color: {TreasureGoblinTheme.COLORS['text_secondary']};
                font-size: 14px;
                min-width: 65px;
                font-weight: bold;
            """)
                item_layout.addWidget(date_label)

                # Description label
                desc_label = QLabel(description)
                desc_label.setStyleSheet(f"""
                color: {TreasureGoblinTheme.COLORS['text_primary']};
                font-size: 14px;
                padding-left: 10px;
                font-weight: bold;
            """)
                item_layout.addWidget(desc_label)

                # Spacer
                item_layout.addStretch()

                # Amount label
                if type == 'income':
                    amount_color = TreasureGoblinTheme.COLORS['success_light']  # Green for income
                else:
                    amount_color = TreasureGoblinTheme.COLORS['danger_light']   # Red for expenses

                amount_label = QLabel(f"${amount:.2f}")
                amount_label.setStyleSheet(f"""
                    color: {amount_color};
                    font-weight: bold;
                    font-family: Consolas;
                    font-size: 16px;
                    min-width: 80px;
                    text-align: right;
                """)
                amount_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                item_layout.addWidget(amount_label)

                # Set the widget size
                item_widget.setMinimumHeight(40)

                # Add to list
                self.transactions_list.addItem(item)
                self.transactions_list.setItemWidget(item, item_widget)

                item.setSizeHint(item_widget.sizeHint())

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

        transactions_for_label = QLabel("Transactions for:")
        transactions_for_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        month_selector_layout.addWidget(transactions_for_label)
        
        self.month_combo = QComboBox()
        self.month_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {TreasureGoblinTheme.COLORS['surface_light']};
                border: 2px solid {TreasureGoblinTheme.COLORS['primary_dark']};
                border-radius: 6px;
                padding: 8px 12px;
                color: {TreasureGoblinTheme.COLORS['text_primary']};
                font-size: 14px;
                font-weight: bold;
                min-height: 25px;
            }}
            QComboBox:focus {{
                border: 2px solid {TreasureGoblinTheme.COLORS['accent']};
                background-color: {TreasureGoblinTheme.COLORS['surface']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {TreasureGoblinTheme.COLORS['text_primary']};
                margin-right: 5px;
            }}
        """)
        
        month_selector_layout.addWidget(self.month_combo)
        
        transactions_list_layout.addLayout(month_selector_layout)

        # Populate with months that have transaction data
        self.populate_month_selector()

        self.month_combo.currentIndexChanged.connect(self.load_transactions_for_month)
        
        # Transactions list with selection functionality
        self.transactions_list_widget = QListWidget()
        self.transactions_list_widget.setMinimumWidth(300)
        self.transactions_list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.transactions_list_widget.setSelectionBehavior(QListWidget.SelectRows)
        self.transactions_list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {TreasureGoblinTheme.COLORS['surface']};
                border: 2px solid {TreasureGoblinTheme.COLORS['primary_dark']};
                border-radius: 8px;
                padding: 8px;
                outline: none;
                font-size: 15px;
            }}
            QListWidget::item {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px;
                margin: 3px 0;
                min-height: 35px;
            }}
            QListWidget::item:selected {{
                background-color: rgba(45, 106, 79, 0.3);
                border: none;
            }}
            QListWidget::item:hover {{
                background-color: rgba(45, 106, 79, 0.15);
                border: none;
            }}
            QListWidget::item:focus {{
                outline: none;
                border: none;
            }}
        """)
        
        # Connect selection change to update button states
        self.transactions_list_widget.itemSelectionChanged.connect(self.on_transaction_selection_changed)
        
        transactions_list_layout.addWidget(self.transactions_list_widget)

        # Edit and Delete buttons at bottom of transaction list
        transaction_buttons_layout = QHBoxLayout()

        # Edit button - initially disabled
        self.edit_transaction_button = QPushButton("Edit Transaction")
        self.edit_transaction_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #A0A0A0;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 15px;
                min-height: 35px;
            }}
        """)
        self.edit_transaction_button.setEnabled(False)
        self.edit_transaction_button.clicked.connect(self.on_edit_transaction_clicked)
        transaction_buttons_layout.addWidget(self.edit_transaction_button)

        # Delete button - initially disabled
        self.delete_transaction_button = QPushButton("Delete Transaction")
        self.delete_transaction_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #A0A0A0;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 15px;
                min-height: 35px;
            }}
        """)
        self.delete_transaction_button.setEnabled(False)
        self.delete_transaction_button.clicked.connect(self.on_delete_transaction_clicked)
        transaction_buttons_layout.addWidget(self.delete_transaction_button)

        transactions_list_layout.addLayout(transaction_buttons_layout)
        
        # Right side - container for form and buttons
        right_container = QVBoxLayout()

        form_title_label = QLabel("Enter a Transaction:")
        form_title_label.setStyleSheet(f"""
            color: {TreasureGoblinTheme.COLORS['accent']};    
            font-size: 20px;
            font-weight: bold;
            font-family: Georgia;
            margin-bottom: 15px;
        """)
        right_container.addWidget(form_title_label)
        
        # Transaction form (used for both adding new transactions and editing existing transactions)
        transaction_form = QFrame()
        transaction_form.setFrameStyle(QFrame.StyledPanel)
        form_layout = QVBoxLayout(transaction_form)
        form_layout.setSpacing(20)
        
        # Transaction form (changes based on add/edit mode)
        self.form_title = form_title_label
        
        # Form fields
        transaction_form_fields = QFormLayout()
        transaction_form_fields.setVerticalSpacing(15)
        
        # Transaction type
        self.transaction_type_combo = QComboBox()
        self.transaction_type_combo.addItems(["Expense", "Income"])
        self.transaction_type_combo.currentTextChanged.connect(self.update_category_options)
        self.transaction_type_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {TreasureGoblinTheme.COLORS['surface_light']};
                border: 2px solid {TreasureGoblinTheme.COLORS['primary_dark']};
                border-radius: 6px;
                padding: 10px 12px;
                color: {TreasureGoblinTheme.COLORS['text_primary']};
                font-size: 14px;
                font-weight: bold;
                min-height: 25px;
            }}
            QComboBox:focus {{
                border: 2px solid {TreasureGoblinTheme.COLORS['accent']};
                background-color: {TreasureGoblinTheme.COLORS['surface']};
            }}
        """)

        type_label = QLabel("Transaction Type:")
        type_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        transaction_form_fields.addRow(type_label, self.transaction_type_combo)
        
        # Transaction amount
        amount_layout = QHBoxLayout()
        dollar_label = QLabel("$")
        dollar_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        amount_layout.addWidget(dollar_label)

        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("0.00")
        self.amount_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {TreasureGoblinTheme.COLORS['surface_light']};
                border: 2px solid {TreasureGoblinTheme.COLORS['primary_dark']};
                border-radius: 6px;
                padding: 10px 12px;
                color: {TreasureGoblinTheme.COLORS['text_primary']};
                font-size: 14px;
                min-height: 25px;
            }}
            QLineEdit:focus {{
                border: 2px solid {TreasureGoblinTheme.COLORS['accent']};
                background-color: {TreasureGoblinTheme.COLORS['surface']};
            }}
        """)
        amount_layout.addWidget(self.amount_input)
        
        amount_label = QLabel("Transaction Amount:")
        amount_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        transaction_form_fields.addRow(amount_label, amount_layout)
        
        # Transaction date
        self.date_input = QDateEdit()
        self.date_input.setDisplayFormat("MM/dd/yy")
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setStyleSheet(f"""
            QDateEdit {{
                background-color: {TreasureGoblinTheme.COLORS['surface_light']};
                border: 2px solid {TreasureGoblinTheme.COLORS['primary_dark']};
                border-radius: 6px;
                padding: 10px 12px;
                color: {TreasureGoblinTheme.COLORS['text_primary']};
                font-size: 14px;
                min-height: 25px;
            }}
            QDateEdit:focus {{
                border: 2px solid {TreasureGoblinTheme.COLORS['accent']};
                background-color: {TreasureGoblinTheme.COLORS['surface']};
            }}
        """)
        
        date_label = QLabel("Transaction Date:")
        date_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        transaction_form_fields.addRow(date_label, self.date_input)
        
        # Transaction category
        self.category_combo = QComboBox()
        self.category_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {TreasureGoblinTheme.COLORS['surface_light']};
                border: 2px solid {TreasureGoblinTheme.COLORS['primary_dark']};
                border-radius: 6px;
                padding: 10px 12px;
                color: {TreasureGoblinTheme.COLORS['text_primary']};
                font-size: 14px;
                font-weight: bold;
                min-height: 25px;
            }}
            QComboBox:focus {{
                border: 2px solid {TreasureGoblinTheme.COLORS['accent']};
                background-color: {TreasureGoblinTheme.COLORS['surface']};
            }}
        """)

        category_label = QLabel("Transaction Category:")
        category_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        transaction_form_fields.addRow(category_label, self.category_combo)
        
        # Transaction tag
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Tag")
        self.tag_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {TreasureGoblinTheme.COLORS['surface_light']};
                border: 2px solid {TreasureGoblinTheme.COLORS['primary_dark']};
                border-radius: 6px;
                padding: 10px 12px;
                color: {TreasureGoblinTheme.COLORS['text_primary']};
                font-size: 14px;
                min-height: 25px;
            }}
            QLineEdit:focus {{
                border: 2px solid {TreasureGoblinTheme.COLORS['accent']};
                background-color: {TreasureGoblinTheme.COLORS['surface']};
            }}
        """)
        
        tag_label = QLabel("Transaction Tag (Optional):")
        tag_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        transaction_form_fields.addRow(tag_label, self.tag_input)
        
        form_layout.addLayout(transaction_form_fields)

        # Buttons container
        buttons_layout = QHBoxLayout()
        
        # Submit button (text changes based on mode)
        self.submit_button = QPushButton("Submit Transaction")
        self.submit_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #CD5C5C;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 20px;
                min-height: 40px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #DC2F02;
            }}
        """)
        self.submit_button.clicked.connect(self.submit_transaction)
        buttons_layout.addWidget(self.submit_button)

        # Cancel edit button (only shown during edit mode)
        self.cancel_edit_button = QPushButton("Cancel Edit")
        self.cancel_edit_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #808080;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 20px;
                min-height: 40px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #606060;
            }}
        """)
        self.cancel_edit_button.clicked.connect(self.cancel_edit)
        self.cancel_edit_button.setVisible(False)
        buttons_layout.addWidget(self.cancel_edit_button)

        form_layout.addLayout(buttons_layout)

        right_container.addWidget(transaction_form)
        
        # Spacer
        right_container.addStretch()
        
        # Import/Export buttons container
        backup_title_label = QLabel("Backup & Restore:")
        backup_title_label.setStyleSheet(f"""
            color: {TreasureGoblinTheme.COLORS['accent']};    
            font-size: 18px;
            font-weight: bold;
            font-family: Georgia;
            margin-top: 20px;
            margin-bottom: 10px;
        """)
        right_container.addWidget(backup_title_label)
        
        import_export_frame = QFrame()
        import_export_frame.setFrameStyle(QFrame.StyledPanel)
        import_export_layout = QVBoxLayout(import_export_frame)

        # Regular Import/Export buttons
        local_backup_layout = QHBoxLayout()
        
        # Import button
        import_button = QPushButton("Import Transactions")
        import_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #CD5C5C;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 15px;
                min-height: 35px;
            }}
            QPushButton:hover {{
                background-color: #DC2F02;
            }}
        """)
        import_button.clicked.connect(self.import_transactions)
        local_backup_layout.addWidget(import_button)
        
        # Export button
        export_button = QPushButton("Export Transactions")
        export_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #CD5C5C;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 15px;
                min-height: 35px;
            }}
            QPushButton:hover {{
                background-color: #DC2F02;
            }}
        """)
        export_button.clicked.connect(self.export_transactions)
        local_backup_layout.addWidget(export_button)

        import_export_layout.addLayout(local_backup_layout)
        
        # Google Drive Sync section
        drive_sync_layout = QHBoxLayout()

        # Google Drive Sync button
        self.drive_sync_button = QPushButton("Google Drive Sync")
        self.drive_sync_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #4285F4;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 15px;
                min-height: 35px;
            }}
            QPushButton:hover {{
                background-color: #3367D6;
            }}
        """)
        self.drive_sync_button.clicked.connect(self.open_drive_sync_dialog)
        drive_sync_layout.addWidget(self.drive_sync_button)

        # Sync Now button
        self.sync_now_button = QPushButton("Sync Now")
        self.sync_now_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #4285F4;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 15px;
                min-height: 35px;
            }}
            QPushButton:hover {{
                background-color: #3367D6;
            }}
        """)
        self.sync_now_button.clicked.connect(self.sync_to_drive_now)
        
        # Enable/disable based on whether sync is configured
        self.sync_now_button.setEnabled(self.treasure_goblin.drive_sync.config.get('token') is not None)
        drive_sync_layout.addWidget(self.sync_now_button)

        import_export_layout.addLayout(drive_sync_layout)

        # Add sync status indicator
        self.sync_status_label = QLabel()
        self.sync_status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.update_sync_status_label()
        import_export_layout.addWidget(self.sync_status_label)

        right_container.addWidget(import_export_frame)
        
        # Add left and right sides to main layout
        layout.addWidget(transactions_list_container, 1)
        layout.addLayout(right_container, 1)

        # Initialize edit mode tracking
        self.editing_transaction_id = None
        
        # Initialize the category options based on the default transaction type
        self.update_category_options()
        
        # Load transactions for the current month
        self.load_transactions_for_month()
        
        return tab
    
    def populate_month_selector(self):
        """Populate the month selector with only months that have transaction data."""
        self.month_combo.clear()

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Get all unique year-month combination from transactions
            query = """
                SELECT DISTINCT
                    strftime('%Y', date) as year,
                    strftime('%m', date) as month,
                    strftime('%Y-%m', date) as year_month
                FROM transactions
                ORDER BY year_month DESC    
            """

            cursor.execute(query)
            results = cursor.fetchall()

            # Add each month-year combination to the dropdown
            for year, month, year_month in results:
                # Conver to readable format
                date_obj = datetime.strptime(f"{year}-{month}-01", "%Y-%m-%d")
                display_text = date_obj.strftime("%B %Y")

                # Add to combo box with month and year as data
                self.month_combo.addItem(display_text, (int(month), int(year)))

            conn.close()

            # If no transactions exist, add current month as default
            if self.month_combo.count() == 0:
                current_date = QDate.currentDate()
                current_month_text = current_date.toString("MMMM yyyy")
                self.month_combo.addItem(current_month_text, (current_date.month(), current_date.year()))

        except Exception as e:
            print(f"Error populating the month selector: {e}")
            # Fallback: add current month
            current_date = QDate.currentDate()
            current_month_text = current_date.toString("MMMM yyyy")
            self.month_combo.addItem(current_month_text, (current_date.month(), current_date.year()))
    
    def update_category_options(self):
        """Update category dropdown based on selected transaction type."""
        self.category_combo.clear()

        # Get transaction type (conver to lowercase for database query)
        transaction_type = self.transaction_type_combo.currentText().lower()

        # Get categories from database (exclude system categories)
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM categories WHERE type = ? AND (is_system IS NULL OR is_system = FALSE) ORDER BY name",
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
                
                 # Create a custom widget item
                 item = QListWidgetItem()
                 item.setData(Qt.UserRole, transaction['id'])  # Store transaction ID

                 # Create container widget with proper layout
                 item_widget = TransactionItemWidget()
                 item_layout = QHBoxLayout(item_widget)
                 item_layout.setContentsMargins(12, 12, 12, 12)

                 # Check if it's a no-category transaction
                 if transaction['category'] == '{NO_CATEGORY}':
                     # Warning icon for no category
                     warning_label = QLabel("⚠️")
                     warning_label.setStyleSheet("font-size: 16px;")
                     item_layout.addWidget(warning_label)

                # Date
                 date_label = QLabel(date_obj)
                 date_label.setStyleSheet(f"""
                     color: {TreasureGoblinTheme.COLORS['text_secondary']};
                     font-size: 16px;
                     min-width: 75px;
                     font-weight: bold;
                 """)
                 item_layout.addWidget(date_label)

                 # Category and tag
                 desc_label = QLabel(description)
                 desc_label.setStyleSheet(f"""
                     color: {TreasureGoblinTheme.COLORS['text_primary']};
                     font-size: 16px;
                     padding-left: 12px;
                     font-weight: bold;
                 """)
                 item_layout.addWidget(desc_label)

                 # Spacer
                 item_layout.addStretch()

                 # Amount with proprer color based on type
                 if transaction['type'] == 'income':
                     amount_color = TreasureGoblinTheme.COLORS['success_light'] # Green for income
                 else:
                    amount_color = TreasureGoblinTheme.COLORS['danger_light'] # Red for expenses

                 amount_label = QLabel(f"${transaction['amount']:.2f}")
                 amount_label.setStyleSheet(f"""
                     color: {amount_color};
                     font-weight: bold;
                     font-family: Consolas;
                     font-size: 18px;
                     min-width: 90px;
                     text-align: right;                    
                 """)
                 amount_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                 item_layout.addWidget(amount_label)

                 # Set minimum height for better visibility
                 item_widget.setMinimumHeight(50) 
                 
                 # Connect to list widget selection changes
                 self.transactions_list_widget.itemSelectionChanged.connect(
                    lambda: self.update_transaction_selection_visual()
                 )

                 # Special styling for no-category items
                 if transaction['category'] == "{NO_CATEGORY}":
                    item_widget.set_default_style(f"""
                        background-color: {TreasureGoblinTheme.COLORS['surface']};
                        border-left: 3px solid {TreasureGoblinTheme.COLORS['accent']};
                        border-radius: 4px;                      
                """)
                 item_widget.setToolTip("This transaction needs a category assignment")

                 # Add item to list
                 self.transactions_list_widget.addItem(item)
                 self.transactions_list_widget.setItemWidget(item, item_widget)

                 # Set size hint to ensure proper display
                 item.setSizeHint(item_widget.sizeHint()) 
            
        except Exception as e:
            print(f"Error loading transactions: {e}")

    def update_transaction_selection_visual(self):
        """Update visual selection state of transaction items"""
        for i in range(self.transactions_list_widget.count()):
            item = self.transactions_list_widget.item(i)
            widget = self.transactions_list_widget.itemWidget(item)
            if isinstance(widget, TransactionItemWidget):
                widget.set_selected(item.isSelected())

    def on_transaction_selection_changed(self):
        """Handle when a transaction is selected or deselected in the list."""
        # Get the currently selected item
        selected_items = self.transactions_list.selectedItems()
        current_item = self.transactions_list_widget.currentItem()

        if current_item:
            # A transaction is selected - enable the buttons and change their color
            self.edit_transaction_button.setEnabled(True)
            self.edit_transaction_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: #4CAF50;
                    color: white;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 10px 15px;
                    min-height: 35px;
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    background-color: #45A049;
                }}
            """)

            self.delete_transaction_button.setEnabled(True)
            self.delete_transaction_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #f44336;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 15px;
                min-height: 35px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #da190b;
            }}
        """)

        else:
            # No transactions selected - disable the buttons and make them gray
            self.edit_transaction_button.setEnabled(False)
            self.delete_transaction_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: #A0A0A0;
                    color: white;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 10px 15px;
                    min-height: 35px;
                    border-radius: 6px;
                }}
            """)

    def on_edit_transaction_clicked(self):
        """Handle clicking the Edit Transaction button."""
        # Get the currently selected item
        current_item = self.transactions_list_widget.currentItem()

        if current_item:
            # Get the transaction ID from the current item
            transaction_id = current_item.data(Qt.UserRole)
            if transaction_id:
                self.edit_transaction(transaction_id)

    def edit_transaction(self, transaction_id):
        """Load transaction data into the form for editing"""
        try:
            # Get transaction details from database
            conn = self.get_db_connection()
            cursor = conn.cursor()

            query = """
                SELECT t.type, t.amount, t.date, t.tag, c.name as category
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE t.id = ?
            """

            cursor.execute(query, (transaction_id,))
            result = cursor.fetchone()
            conn.close()

            if result:
                transaction_type, amount, date, tag, category = result

                # Set form to edit mode
                self.editing_transaction_id = transaction_id
                self.form_title.setText("Edit Transaction:")
                self.submit_button.setText("Save Transaction")
                self.cancel_edit_button.setVisible(True)

                # Populate form fields
                # Set transaction type
                type_text = "Income" if transaction_type == 'income' else "Expense"
                self.transaction_type_combo.setCurrentText(type_text)

                # Update categories based on type and set the current category
                self.update_category_options()
                self.category_combo.setCurrentText(category)

                # Set amount
                self.amount_input.setText(str(amount))

                # Set date
                date_obj = QDate.fromString(date, "MM-dd-yyyy")
                self.date_input.setDate(date_obj)

                # Set tag
                self.tag_input.setText(tag if tag else "")

                # Clear the selection and disable the edit/delete buttons
                self.transactions_list_widget.clearSelection()

            else:
                QMessageBox.warning(self, "Error", "Transaction not found.")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load transactions: {str(e)}")

    def on_delete_transaction_clicked(self):
        """Handle clicking the Delete Transaction button."""
        # Get the currently selected item
        current_item = self.transactions_list_widget.currentItem()
        
        if current_item:
            # Get the transaction ID from the current item
            transaction_id = current_item.data(Qt.UserRole)
            if transaction_id:
                self.delete_transaction(transaction_id)
    

    def delete_transaction(self, transaction_id):
        """Delete a transaction after confirmation."""
        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            "Are you sure you want to delete this transaction?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # Delete from database
                conn = self.get_db_connection()
                cursor = conn.cursor()

                cursor.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
                conn.commit()
                conn.close()

                # Refresh the month selector (in case we deleted all transactions from a month)
                self.populate_month_selector()

                # Refresh the transactions list
                self.load_transactions_for_month()

                # Update dashboard
                self.update_dashboard()

                QMessageBox.information(self, "Success", "Transaction deleted succesfully!")
            
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete transaction: {str(e)}")

    def cancel_edit(self):
        """Cancel editing mode and return to add mode."""
        # Reset to add mode
        self.editing_transaction_id = None
        self.form_title.setText("Enter a Transaction:")
        self.submit_button.setText("Submit Transaction")
        self.cancel_edit_button.setVisible(False)

        # Clear form fields
        self.amount_input.clear()
        self.tag_input.clear()
        self.date_input.setDate(QDate.currentDate())
        self.transaction_type_combo.setCurrentIndex(0)
        self.update_category_options()

        # Clear any selection in the transaction list
        self.transactions_list_widget.setCurrentItem(None)
        
        # Manually trigger the selection changed handler to update button states
        self.on_transaction_selection_changed()
 
    def submit_transaction(self):
        """Handle the submission of a new or edited transaction."""
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

            if self.editing_transaction_id:
                # Update exisiting transaction
                success = self.update_transaction(
                    self.editing_transaction_id, transaction_type, amount, date, category, tag
                )

                if success:
                    # Reset form to add mode
                    self.cancel_edit()

                    # Refresh the month selector to include any new months
                    self.populate_month_selector()

                    # Refresh the transactions list
                    self.load_transactions_for_month()

                    # Update the dashboard if needed
                    self.update_dashboard()

                    QMessageBox.information(self, "Success", "Transaction updated successfully!")
                else:
                    QMessageBox.warning(self, "Error", "Failed to update transaction. Please try again.")

            else:

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

    def update_transaction(self, transaction_id, transaction_type, amount, date, category, tag):
        """Update an exisiting transaction in the database."""
        try:
            # Conver string date to proper format
            if isinstance(date, str):
                date_obj = datetime.strptime(date, '%m-%d-%Y').date()
            else:
                date_obj = date

            # Make sure amount is positive
            amount = abs(float(amount))

            conn = self.get_db_connection()
            cursor = conn.cursor()

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

            # Update transaction
            cursor.execute('''
                UPDATE transactions
                SET type = ?, amount = ?, date = ?, category_id = ?, tag = ?
                WHERE id = ?
            ''', (transaction_type, amount, date_obj.isoformat(), category_id, tag, transaction_id))

            conn.commit()
            conn.close()
            return True
        
        except Exception as e:
            print(f"Database error: {e}")
            if conn:
                conn.rollback()
                conn.close()
            return False

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
            
            # Refresh the month selector to include any new months from import
            self.populate_month_selector()

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
            self.sync_status_label.setStyleSheet("color: gray; font-size: 14px; font-weight: bold;")
            return
        last_sync = drive_sync.config.get('last_sync')
        if last_sync:
            try:
                sync_time = datetime.fromisoformat(last_sync)
                last_sync_text = sync_time.strftime("%m/%d/%Y %I:%M %p")
                self.sync_status_label.setText(f"Last synced: {last_sync_text}")
                self.sync_status_label.setStyleSheet("color: green; font-size: 14px; font-weight: bold;")
            except:
                self.sync_status_label.setText("Last sync: Unknown")
                self.sync_status_label.setStyleSheet("color: gray; font-size: 14px; font-weight: bold;")
        else:
            self.sync_status_label.setText("Google Drive Sync: Not yet synced")
            self.sync_status_label.setStyleSheet("color: orange; font-size: 14px; font-weight: bold;")

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
        progress_dialog.setModal(True)
        
        dialog_layout = QVBoxLayout(progress_dialog)
        
        status_label = QLabel("Syncing data to Google Drive...")
        dialog_layout.addWidget(status_label)
        
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        progress_bar.setTextVisible(True)
        progress_bar.setFormat("%p%")
        dialog_layout.addWidget(progress_bar)

        # Connect signals with proper thread safety
        def update_progress(value):
            progress_bar.setValue(value)
            QApplication.processEvents()
        
        def handle_completion(success, message):
            progress_dialog.accept()
            self.handle_sync_completed(success, message, progress_dialog)
    
        # Connect the signals
        self.treasure_goblin.drive_sync.sync_progress.connect(update_progress)
        self.treasure_goblin.drive_sync.sync_completed.connect(handle_completion)
            
        # Connect the signals
        self.treasure_goblin.drive_sync.sync_progress.connect(update_progress)
        self.treasure_goblin.drive_sync.sync_completed.connect(handle_completion)
        
        # Start sync in main thread (since we're handling threading properly with QApplication.processEvents)
        progress_dialog.show()
        QApplication.processEvents()  # Ensure the dialog shows immediately
        
        # Run sync directly instead of in a separate thread
        # The upload_backup method already handles progress properly
        success, message = self.treasure_goblin.drive_sync.sync_now()
        
        # Disconnect signals to prevent memory leaks
        self.treasure_goblin.drive_sync.sync_progress.disconnect(update_progress)
        self.treasure_goblin.drive_sync.sync_completed.disconnect(handle_completion)

    def handle_sync_completed(self, success, message, dialog):
        """Handle completion of Google Drive sync."""

        if success:
            QMessageBox.information(self, "Sync Complete", message)
        else:
            QMessageBox.warning(self, "Sync Failed", message)
        
        # Update the status label
        self.update_sync_status_label()

    def _update_progress_safely(self, progress_bar, value):
        """Update progress bar in a thread-safe way"""
        # Use QMetaObject.invokeMethod or a simple check if we're on the main thread
        if threading.current_thread() is threading.main_thread():
            progress_bar.setValue(value)
        else:
            # Schedule the update on the main thread
            QTimer.singleShot(0, lambda: progress_bar.setValue(value))

    def _handle_sync_completion_safely(self, success, message, dialog):
        """Handle sync completion in a thread-safe way"""
        if threading.current_thread() is threading.main_thread():
            self.handle_sync_completed(success, message, dialog)
        else:
            # Schedule the handling on the main thread
            QTimer.singleShot(0, lambda: self.handle_sync_completed(success, message, dialog))

    def closeEvent(self, event):
        """Handle application close event."""
        # Check if we need to sync with Google Drive
        if hasattr(self.treasure_goblin, 'drive_sync'):
            if self.treasure_goblin.drive_sync.should_sync_on_close():
                # Create message box
                reply_dialog = QMessageBox(self)
                reply_dialog.setWindowTitle("Sync to Google Drive")
                reply_dialog.setText("Sync your data to Google Drive before closing?")
                reply_dialog.setInformativeText("This will backup your financial data to the cloud for safekeeping.")
                
                # Font styling
                reply_dialog.setStyleSheet("""
                    QMessageBox {
                        font-size: 14px;
                    }
                    QMessageBox QLabel {
                        font-size: 14px;
                        margin: 10px;
                    }
                    QMessageBox QPushButton {
                        font-size: 13px;
                        font-weight: bold;
                        padding: 8px 16px;
                        margin: 4px;
                        min-width: 70px;
                        min-height: 30px;
                    }
                """)
                
                # Set icon and buttons
                reply_dialog.setIcon(QMessageBox.Question)
                reply_dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                reply_dialog.setDefaultButton(QMessageBox.Yes)
                
                reply = reply_dialog.exec_()
                
                if reply == QMessageBox.Yes:
                    # Show a simple progress dialog
                    progress_dialog = QDialog(self)
                    progress_dialog.setWindowTitle("Syncing to Google Drive")
                    progress_dialog.setFixedSize(350, 120)
                    progress_dialog.setModal(True)
                    
                    dialog_layout = QVBoxLayout(progress_dialog)
                    dialog_layout.setContentsMargins(20, 15, 20, 15)
                    dialog_layout.setSpacing(10)
                    
                    # Status label
                    status_label = QLabel("Syncing data to Google Drive before closing...")
                    status_label.setStyleSheet("font-size: 13px; font-weight: bold;")
                    status_label.setAlignment(Qt.AlignCenter)
                    dialog_layout.addWidget(status_label)
                    
                    # Progress bar
                    progress_bar = QProgressBar()
                    progress_bar.setRange(0, 100)
                    progress_bar.setValue(0)
                    progress_bar.setTextVisible(True)
                    progress_bar.setFormat("%p%")
                    progress_bar.setStyleSheet("""
                        QProgressBar {
                            font-size: 12px;
                            font-weight: bold;
                            text-align: center;
                            min-height: 20px;
                            border: 1px solid #ccc;
                            border-radius: 3px;
                            background-color: #f0f0f0;
                        }
                        QProgressBar::chunk {
                            background-color: #4285F4;
                            border-radius: 2px;
                        }
                    """)
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
                        # Simple error dialog
                        error_dialog = QMessageBox(self)
                        error_dialog.setIcon(QMessageBox.Warning)
                        error_dialog.setWindowTitle("Sync Failed")
                        error_dialog.setText("Failed to sync to Google Drive")
                        error_dialog.setInformativeText(message)
                        error_dialog.setStyleSheet("""
                            QMessageBox {
                                font-size: 13px;
                            }
                            QMessageBox QLabel {
                                font-size: 13px;
                                margin: 8px;
                            }
                            QMessageBox QPushButton {
                                font-size: 12px;
                                font-weight: bold;
                                padding: 6px 12px;
                                min-width: 60px;
                                min-height: 25px;
                            }
                        """)
                        error_dialog.exec_()
        
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
        self.expenses_button.setStyleSheet(f"background-color: {TreasureGoblinTheme.COLORS['danger']}");
        self.expenses_button.setCheckable(True)
        self.expenses_button.setChecked(True)
        self.expenses_button.clicked.connect(lambda: self.switch_category_type('expense'))

        self.income_button = QPushButton("Income")
        self.income_button.setStyleSheet(f"background-color: {TreasureGoblinTheme.COLORS['success']}");
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
            self.expenses_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {TreasureGoblinTheme.COLORS['danger']};
                    color: white;
                    font-size: 16px;
                    font-weight: bold;
                    padding: 12px 20px;
                    border-radius: 6px;
                }}
            """)
            self.income_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {TreasureGoblinTheme.COLORS['surface_light']};
                    color: {TreasureGoblinTheme.COLORS['text_secondary']};
                    font-size: 16px;
                    font-weight: bold;
                    padding: 12px 20px;
                    border-radius: 6px;
                }}
            """)
        else:
            self.expenses_button.setChecked(False)
            self.income_button.setChecked(True)
            self.current_category_type = 'income'
            self.income_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {TreasureGoblinTheme.COLORS['success']};
                    color: white;
                    font-size: 16px;
                    font-weight: bold;
                    padding: 12px 20px;
                    border-radius: 6px;
                }}
            """)
            self.expenses_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {TreasureGoblinTheme.COLORS['surface_light']};
                    color: {TreasureGoblinTheme.COLORS['text_secondary']};
                    font-size: 16px;
                    font-weight: bold;
                    padding: 12px 20px;
                    border-radius: 6px;
                }}
            """)

        self.load_categories()

    def load_categories(self):
        """Load categories of the current type from the database."""
        # Clear existing categories
        while self.categories_grid.count():
            item = self.categories_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            # Get categories from database (exclude system categories)
            conn = self.get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                    "SELECT id, name FROM categories WHERE type = ? AND (is_system IS NULL OR is_system = FALSE)",
                    (self.current_category_type,)
            )

            categories = cursor.fetchall()
            conn.close()

            # Add categories to grid
            row, col = 0,0
            max_cols = 4 # Number of columns in the grid

            for category_id, category_name in categories:
                category_button = QPushButton(category_name)
                category_button.setMinimumSize(120, 80)

                # Set different colors based on category type
                if self.current_category_type == 'expense':
                    category_button.setStyleSheet("""
                        QPushButton {
                            background-color: #CC0000;
                            color: white;
                            font-size: 16px;
                            font-weight: bold;
                            border-radius: 8px;
                        }
                        QPushButton:hover {
                            background-color: #FF0000;
                        }
                    """)
                else:
                    category_button.setStyleSheet("""
                        QPushButton {
                            background-color: #008800;
                            color: white;
                            font-size: 16px;
                            font-weight: bold;
                            border-radius: 8px;
                        }
                        QPushButton:hover {
                            background-color: #00AA00;
                        }
                    """)

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
            add_button.setFont(QFont("Arial", 20))
            add_button.setMinimumSize(120, 80)
            add_button.setStyleSheet("""
                QPushButton {
                    background-color: #CD5C5C;
                    color: white;
                    font-size: 24px;
                    font-weight: bold;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #DC2F02;
                }
            """)
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
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Category")
        dialog.setFixedSize(400, 200)
        dialog.setModal(True)
        
        # Apply consistent styling
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {TreasureGoblinTheme.COLORS['surface']};
                color: {TreasureGoblinTheme.COLORS['text_primary']};
            }}
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 25, 30, 25)
        
        # Label
        label = QLabel("Enter category name:")
        label.setStyleSheet(f"""
            QLabel {{
                color: {TreasureGoblinTheme.COLORS['text_primary']};
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 10px;
            }}
        """)
        layout.addWidget(label)
        
        # Input field
        line_edit = QLineEdit()
        line_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {TreasureGoblinTheme.COLORS['surface_light']};
                border: 2px solid {TreasureGoblinTheme.COLORS['primary_dark']};
                border-radius: 6px;
                padding: 12px 15px;
                color: {TreasureGoblinTheme.COLORS['text_primary']};
                font-size: 14px;
                font-weight: bold;
                min-height: 20px;
            }}
            QLineEdit:focus {{
                border: 2px solid {TreasureGoblinTheme.COLORS['accent']};
                background-color: {TreasureGoblinTheme.COLORS['surface']};
            }}
        """)
        line_edit.setPlaceholderText("Category name...")
        layout.addWidget(line_edit)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {TreasureGoblinTheme.COLORS['surface_light']};
                color: {TreasureGoblinTheme.COLORS['text_primary']};
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
                min-height: 35px;
                border-radius: 6px;
                border: 2px solid {TreasureGoblinTheme.COLORS['primary_dark']};
            }}
            QPushButton:hover {{
                background-color: {TreasureGoblinTheme.COLORS['primary_dark']};
            }}
        """)
        cancel_button.clicked.connect(dialog.reject)
        
        # OK button
        ok_button = QPushButton("Add Category")
        ok_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #CD5C5C;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
                min-height: 35px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #DC2F02;
            }}
        """)
        ok_button.clicked.connect(dialog.accept)
        ok_button.setDefault(True)  # Make this the default button
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(ok_button)
        layout.addLayout(button_layout)
        
        # Set focus to the input field
        line_edit.setFocus()
        
        # Show dialog and get result
        if dialog.exec_() == QDialog.Accepted:
            category_name = line_edit.text().strip()
            
            if category_name:
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
                        # Create styled success message
                        success_msg = QMessageBox(self)
                        success_msg.setIcon(QMessageBox.Information)
                        success_msg.setWindowTitle("Success")
                        success_msg.setText(f"Category '{category_name}' added successfully!")
                        success_msg.setStyleSheet(f"""
                            QMessageBox {{
                                background-color: {TreasureGoblinTheme.COLORS['surface']};
                                color: {TreasureGoblinTheme.COLORS['text_primary']};
                                font-size: 16px;
                            }}
                            QMessageBox QLabel {{
                                color: {TreasureGoblinTheme.COLORS['text_primary']};
                                font-size: 16px;
                                font-weight: bold;
                                margin: 10px;
                            }}
                            QMessageBox QPushButton {{
                                background-color: #CD5C5C;
                                color: white;
                                font-size: 14px;
                                font-weight: bold;
                                padding: 8px 16px;
                                margin: 4px;
                                min-width: 70px;
                                min-height: 30px;
                                border-radius: 4px;
                            }}
                            QMessageBox QPushButton:hover {{
                                background-color: #DC2F02;
                            }}
                        """)
                        success_msg.exec_()
                        # Reload categories
                        self.load_categories()
                
                    conn.close()
                
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to add category: {str(e)}")
            else:
                QMessageBox.warning(self, "Invalid Input", "Please enter a category name.")

    def edit_category(self, category_id, current_name):
        """Edit an existing category."""
        # Create a custom dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Category")
        dialog.setFixedSize(400, 200)
        dialog.setModal(True)
        
        # Apply consistent styling
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {TreasureGoblinTheme.COLORS['surface']};
                color: {TreasureGoblinTheme.COLORS['text_primary']};
            }}
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 25, 30, 25)
        
        # Label with larger font
        label = QLabel("Enter new category name:")
        label.setStyleSheet(f"""
            QLabel {{
                color: {TreasureGoblinTheme.COLORS['text_primary']};
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 10px;
            }}
        """)
        layout.addWidget(label)
        
        # Input field with larger font and current name pre-filled
        line_edit = QLineEdit()
        line_edit.setText(current_name)  # Pre-fill with current name
        line_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {TreasureGoblinTheme.COLORS['surface_light']};
                border: 2px solid {TreasureGoblinTheme.COLORS['primary_dark']};
                border-radius: 6px;
                padding: 12px 15px;
                color: {TreasureGoblinTheme.COLORS['text_primary']};
                font-size: 14px;
                font-weight: bold;
                min-height: 20px;
            }}
            QLineEdit:focus {{
                border: 2px solid {TreasureGoblinTheme.COLORS['accent']};
                background-color: {TreasureGoblinTheme.COLORS['surface']};
            }}
        """)
        layout.addWidget(line_edit)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {TreasureGoblinTheme.COLORS['surface_light']};
                color: {TreasureGoblinTheme.COLORS['text_primary']};
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
                min-height: 35px;
                border-radius: 6px;
                border: 2px solid {TreasureGoblinTheme.COLORS['primary_dark']};
            }}
            QPushButton:hover {{
                background-color: {TreasureGoblinTheme.COLORS['primary_dark']};
            }}
        """)
        cancel_button.clicked.connect(dialog.reject)
        
        # Update button
        update_button = QPushButton("Update Category")
        update_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #CD5C5C;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
                min-height: 35px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #DC2F02;
            }}
        """)
        update_button.clicked.connect(dialog.accept)
        update_button.setDefault(True)  # Make this the default button
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(update_button)
        layout.addLayout(button_layout)
        
        # Select all text for easy editing
        line_edit.selectAll()
        line_edit.setFocus()
        
        # Show dialog and get result
        if dialog.exec_() == QDialog.Accepted:
            new_name = line_edit.text().strip()
            
            if new_name and new_name != current_name:
                try:
                    conn = self.get_db_connection()
                    cursor = conn.cursor()

                    # Check if the new name already exists
                    cursor.execute(
                        "SELECT id FROM categories WHERE name =? AND type = ? AND id != ?",
                            (new_name, self.current_category_type, category_id)
                    )

                    if cursor.fetchone():
                        # Create styled warning message
                        warning_msg = QMessageBox(self)
                        warning_msg.setIcon(QMessageBox.Warning)
                        warning_msg.setWindowTitle("Duplicate Category")
                        warning_msg.setText(f"A {self.current_category_type} category named '{new_name}' already exists")
                        warning_msg.setStyleSheet(f"""
                            QMessageBox {{
                                background-color: {TreasureGoblinTheme.COLORS['surface']};
                                color: {TreasureGoblinTheme.COLORS['text_primary']};
                                font-size: 16px;
                            }}
                            QMessageBox QLabel {{
                                color: {TreasureGoblinTheme.COLORS['text_primary']};
                                font-size: 16px;
                                font-weight: bold;
                                margin: 10px;
                            }}
                            QMessageBox QPushButton {{
                                background-color: #CD5C5C;
                                color: white;
                                font-size: 14px;
                                font-weight: bold;
                                padding: 8px 16px;
                                margin: 4px;
                                min-width: 70px;
                                min-height: 30px;
                                border-radius: 4px;
                            }}
                            QMessageBox QPushButton:hover {{
                                background-color: #DC2F02;
                            }}
                        """)
                        warning_msg.exec_()
                    else:
                        # Update category name
                        cursor.execute(
                            "UPDATE categories SET name = ? WHERE id = ?",
                                (new_name, category_id)
                        )
                        conn.commit()
                        
                        # Create styled success message
                        success_msg = QMessageBox(self)
                        success_msg.setIcon(QMessageBox.Information)
                        success_msg.setWindowTitle("Success")
                        success_msg.setText(f"Category renamed to '{new_name}' successfully!")
                        success_msg.setStyleSheet(f"""
                            QMessageBox {{
                                background-color: {TreasureGoblinTheme.COLORS['surface']};
                                color: {TreasureGoblinTheme.COLORS['text_primary']};
                                font-size: 16px;
                            }}
                            QMessageBox QLabel {{
                                color: {TreasureGoblinTheme.COLORS['text_primary']};
                                font-size: 16px;
                                font-weight: bold;
                                margin: 10px;
                            }}
                            QMessageBox QPushButton {{
                                background-color: #CD5C5C;
                                color: white;
                                font-size: 14px;
                                font-weight: bold;
                                padding: 8px 16px;
                                margin: 4px;
                                min-width: 70px;
                                min-height: 30px;
                                border-radius: 4px;
                            }}
                            QMessageBox QPushButton:hover {{
                                background-color: #DC2F02;
                            }}
                        """)
                        success_msg.exec_()
                        
                        # Reload categories
                        self.load_categories()

                    conn.close()

                except Exception as e:
                    # Create styled error message
                    error_msg = QMessageBox(self)
                    error_msg.setIcon(QMessageBox.Critical)
                    error_msg.setWindowTitle("Error")
                    error_msg.setText(f"Failed to update category: {str(e)}")
                    error_msg.setStyleSheet(f"""
                        QMessageBox {{
                            background-color: {TreasureGoblinTheme.COLORS['surface']};
                            color: {TreasureGoblinTheme.COLORS['text_primary']};
                            font-size: 16px;
                        }}
                        QMessageBox QLabel {{
                            color: {TreasureGoblinTheme.COLORS['text_primary']};
                            font-size: 16px;
                            font-weight: bold;
                            margin: 10px;
                        }}
                        QMessageBox QPushButton {{
                            background-color: #CD5C5C;
                            color: white;
                            font-size: 14px;
                            font-weight: bold;
                            padding: 8px 16px;
                            margin: 4px;
                            min-width: 70px;
                            min-height: 30px;
                            border-radius: 4px;
                        }}
                        QMessageBox QPushButton:hover {{
                            background-color: #DC2F02;
                        }}
                    """)
                    error_msg.exec_()

    def delete_category(self, category_id, category_name):
        """Delete a category after confirmation and reassign transactions to {NO_CATEGORY}."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Check if this is a system category (shouldn't happen, but safety check)
            cursor.execute(
                "SELECT is_system FROM categories WHERE id = ?",
                (category_id,)
            )
            is_system_result = cursor.fetchone()
            if is_system_result and is_system_result[0]:
                # Create styled warning message
                warning_msg = QMessageBox(self)
                warning_msg.setIcon(QMessageBox.Warning)
                warning_msg.setWindowTitle("Cannot Delete")
                warning_msg.setText("System categories cannot be deleted.")
                warning_msg.setStyleSheet(f"""
                    QMessageBox {{
                        background-color: {TreasureGoblinTheme.COLORS['surface']};
                        color: {TreasureGoblinTheme.COLORS['text_primary']};
                        font-size: 16px;
                    }}
                    QMessageBox QLabel {{
                        color: {TreasureGoblinTheme.COLORS['text_primary']};
                        font-size: 16px;
                        font-weight: bold;
                        margin: 10px;
                    }}
                    QMessageBox QPushButton {{
                        background-color: #CD5C5C;
                        color: white;
                        font-size: 14px;
                        font-weight: bold;
                        padding: 8px 16px;
                        margin: 4px;
                        min-width: 70px;
                        min-height: 30px;
                        border-radius: 4px;
                    }}
                    QMessageBox QPushButton:hover {{
                        background-color: #DC2F02;
                    }}
                """)
                warning_msg.exec_()
                conn.close()
                return

            # Get the category type to determine which {NO_CATEGORY} to use
            cursor.execute(
                "SELECT type FROM categories WHERE id = ?",
                (category_id,)
            )
            category_type_result = cursor.fetchone()
            if not category_type_result:
                # Create styled warning message
                warning_msg = QMessageBox(self)
                warning_msg.setIcon(QMessageBox.Warning)
                warning_msg.setWindowTitle("Error")
                warning_msg.setText("Category not found.")
                warning_msg.setStyleSheet(f"""
                    QMessageBox {{
                        background-color: {TreasureGoblinTheme.COLORS['surface']};
                        color: {TreasureGoblinTheme.COLORS['text_primary']};
                        font-size: 16px;
                    }}
                    QMessageBox QLabel {{
                        color: {TreasureGoblinTheme.COLORS['text_primary']};
                        font-size: 16px;
                        font-weight: bold;
                        margin: 10px;
                    }}
                    QMessageBox QPushButton {{
                        background-color: #CD5C5C;
                        color: white;
                        font-size: 14px;
                        font-weight: bold;
                        padding: 8px 16px;
                        margin: 4px;
                        min-width: 70px;
                        min-height: 30px;
                        border-radius: 4px;
                    }}
                    QMessageBox QPushButton:hover {{
                        background-color: #DC2F02;
                    }}
                """)
                warning_msg.exec_()
                conn.close()
                return
            
            category_type = category_type_result[0]

            # Check if category is in use
            cursor.execute(
                "SELECT COUNT(*) FROM transactions WHERE category_id = ?",
                (category_id,)
            )
            
            usage_count = cursor.fetchone()[0]

            if usage_count > 0:
                # Create styled confirmation dialog for categories in use
                confirm_msg = QMessageBox(self)
                confirm_msg.setIcon(QMessageBox.Question)
                confirm_msg.setWindowTitle("Category In Use")
                confirm_msg.setText(f"The category '{category_name}' is used in {usage_count} transactions.")
                confirm_msg.setInformativeText(
                    "Deleting it will move those transactions to {NO_CATEGORY} where you can "
                    "reassign them to other categories if needed.\n\nProceed?"
                )
                confirm_msg.setStyleSheet(f"""
                    QMessageBox {{
                        background-color: {TreasureGoblinTheme.COLORS['surface']};
                        color: {TreasureGoblinTheme.COLORS['text_primary']};
                        font-size: 16px;
                    }}
                    QMessageBox QLabel {{
                        color: {TreasureGoblinTheme.COLORS['text_primary']};
                        font-size: 16px;
                        font-weight: bold;
                        margin: 10px;
                    }}
                    QMessageBox QPushButton {{
                        background-color: #CD5C5C;
                        color: white;
                        font-size: 14px;
                        font-weight: bold;
                        padding: 8px 16px;
                        margin: 4px;
                        min-width: 70px;
                        min-height: 30px;
                        border-radius: 4px;
                    }}
                    QMessageBox QPushButton:hover {{
                        background-color: #DC2F02;
                    }}
                """)
                confirm_msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                confirm_msg.setDefaultButton(QMessageBox.No)

                if confirm_msg.exec_() != QMessageBox.Yes:
                    conn.close()
                    return
            else:
                # Create styled confirmation dialog for unused categories
                confirm_msg = QMessageBox(self)
                confirm_msg.setIcon(QMessageBox.Question)
                confirm_msg.setWindowTitle("Confirm Deletion")
                confirm_msg.setText(f"Are you sure you want to delete the category '{category_name}'?")
                confirm_msg.setStyleSheet(f"""
                    QMessageBox {{
                        background-color: {TreasureGoblinTheme.COLORS['surface']};
                        color: {TreasureGoblinTheme.COLORS['text_primary']};
                        font-size: 16px;
                    }}
                    QMessageBox QLabel {{
                        color: {TreasureGoblinTheme.COLORS['text_primary']};
                        font-size: 16px;
                        font-weight: bold;
                        margin: 10px;
                    }}
                    QMessageBox QPushButton {{
                        background-color: #CD5C5C;
                        color: white;
                        font-size: 14px;
                        font-weight: bold;
                        padding: 8px 16px;
                        margin: 4px;
                        min-width: 70px;
                        min-height: 30px;
                        border-radius: 4px;
                    }}
                    QMessageBox QPushButton:hover {{
                        background-color: #DC2F02;
                    }}
                """)
                confirm_msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                confirm_msg.setDefaultButton(QMessageBox.No)

                if confirm_msg.exec_() != QMessageBox.Yes:
                    conn.close()
                    return

            # Get the {NO_CATEGORY} ID for this transaction type
            cursor.execute(
                "SELECT id FROM categories WHERE name = '{NO_CATEGORY}' AND type = ?",
                (category_type,)
            )
            no_category_result = cursor.fetchone()
            if not no_category_result:
                # Create styled error message
                error_msg = QMessageBox(self)
                error_msg.setIcon(QMessageBox.Critical)
                error_msg.setWindowTitle("Error")
                error_msg.setText("System {NO_CATEGORY} not found. Database may be corrupted.")
                error_msg.setStyleSheet(f"""
                    QMessageBox {{
                        background-color: {TreasureGoblinTheme.COLORS['surface']};
                        color: {TreasureGoblinTheme.COLORS['text_primary']};
                        font-size: 16px;
                    }}
                    QMessageBox QLabel {{
                        color: {TreasureGoblinTheme.COLORS['text_primary']};
                        font-size: 16px;
                        font-weight: bold;
                        margin: 10px;
                    }}
                    QMessageBox QPushButton {{
                        background-color: #CD5C5C;
                        color: white;
                        font-size: 14px;
                        font-weight: bold;
                        padding: 8px 16px;
                        margin: 4px;
                        min-width: 70px;
                        min-height: 30px;
                        border-radius: 4px;
                    }}
                    QMessageBox QPushButton:hover {{
                        background-color: #DC2F02;
                    }}
                """)
                error_msg.exec_()
                conn.close()
                return
            
            no_category_id = no_category_result[0]

            # Begin transaction
            cursor.execute("BEGIN")

            try:
                # Reassign all transactions from the deleted category to {NO_CATEGORY}
                cursor.execute(
                    "UPDATE transactions SET category_id = ? WHERE category_id = ?",
                    (no_category_id, category_id)
                )

                # Delete the category
                cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))

                # Commit the transaction
                cursor.execute("COMMIT")

                if usage_count > 0:
                    # Create styled success message for categories with transactions
                    success_msg = QMessageBox(self)
                    success_msg.setIcon(QMessageBox.Information)
                    success_msg.setWindowTitle("Success")
                    success_msg.setText(f"Category '{category_name}' deleted successfully!")
                    success_msg.setInformativeText(
                        f"{usage_count} transactions have been moved to {{NO_CATEGORY}}. "
                        "You can find and reassign them in the Transactions tab."
                    )
                    success_msg.setStyleSheet(f"""
                        QMessageBox {{
                            background-color: {TreasureGoblinTheme.COLORS['surface']};
                            color: {TreasureGoblinTheme.COLORS['text_primary']};
                            font-size: 16px;
                        }}
                        QMessageBox QLabel {{
                            color: {TreasureGoblinTheme.COLORS['text_primary']};
                            font-size: 16px;
                            font-weight: bold;
                            margin: 10px;
                        }}
                        QMessageBox QPushButton {{
                            background-color: #CD5C5C;
                            color: white;
                            font-size: 14px;
                            font-weight: bold;
                            padding: 8px 16px;
                            margin: 4px;
                            min-width: 70px;
                            min-height: 30px;
                            border-radius: 4px;
                        }}
                        QMessageBox QPushButton:hover {{
                            background-color: #DC2F02;
                        }}
                    """)
                    success_msg.exec_()
                else:
                    # Create styled success message for unused categories
                    success_msg = QMessageBox(self)
                    success_msg.setIcon(QMessageBox.Information)
                    success_msg.setWindowTitle("Success")
                    success_msg.setText(f"Category '{category_name}' deleted successfully!")
                    success_msg.setStyleSheet(f"""
                        QMessageBox {{
                            background-color: {TreasureGoblinTheme.COLORS['surface']};
                            color: {TreasureGoblinTheme.COLORS['text_primary']};
                            font-size: 16px;
                        }}
                        QMessageBox QLabel {{
                            color: {TreasureGoblinTheme.COLORS['text_primary']};
                            font-size: 16px;
                            font-weight: bold;
                            margin: 10px;
                        }}
                        QMessageBox QPushButton {{
                            background-color: #CD5C5C;
                            color: white;
                            font-size: 14px;
                            font-weight: bold;
                            padding: 8px 16px;
                            margin: 4px;
                            min-width: 70px;
                            min-height: 30px;
                            border-radius: 4px;
                        }}
                        QMessageBox QPushButton:hover {{
                            background-color: #DC2F02;
                        }}
                    """)
                    success_msg.exec_()

                # Reload categories
                self.load_categories()

            except Exception as e:
                cursor.execute("ROLLBACK")
                raise e

            conn.close()

        except Exception as e:
            # Create styled error message
            error_msg = QMessageBox(self)
            error_msg.setIcon(QMessageBox.Critical)
            error_msg.setWindowTitle("Error")
            error_msg.setText(f"Failed to delete category: {str(e)}")
            error_msg.setStyleSheet(f"""
                QMessageBox {{
                    background-color: {TreasureGoblinTheme.COLORS['surface']};
                    color: {TreasureGoblinTheme.COLORS['text_primary']};
                    font-size: 16px;
                }}
                QMessageBox QLabel {{
                    color: {TreasureGoblinTheme.COLORS['text_primary']};
                    font-size: 16px;
                    font-weight: bold;
                    margin: 10px;
                }}
                QMessageBox QPushButton {{
                    background-color: #CD5C5C;
                    color: white;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 8px 16px;
                    margin: 4px;
                    min-width: 70px;
                    min-height: 30px;
                    border-radius: 4px;
                }}
                QMessageBox QPushButton:hover {{
                    background-color: #DC2F02;
                }}
            """)
            error_msg.exec_()

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
        self.report_expenses_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {TreasureGoblinTheme.COLORS['danger']};
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {TreasureGoblinTheme.COLORS['danger_light']};
            }}
        """)
        self.report_expenses_button.setCheckable(True)
        self.report_expenses_button.setChecked(True)
        self.report_expenses_button.clicked.connect(lambda: self.switch_report_type('expense'))

        self.report_income_button = QPushButton("Income")
        self.report_income_button.setCheckable(True)
        self.report_income_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {TreasureGoblinTheme.COLORS['success']};
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {TreasureGoblinTheme.COLORS['success_light']};
            }}
        """)
        self.report_income_button.clicked.connect(lambda: self.switch_report_type('income'))

        type_toggle_layout.addWidget(self.report_expenses_button)
        type_toggle_layout.addWidget(self.report_income_button)
        top_controls_layout.addLayout(type_toggle_layout)

        # Center - Period dropdown selector
        period_selector_layout = QHBoxLayout()

        # Create custom label for "Report Period:"
        report_period_label = QLabel("Report Period:")
        report_period_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        period_selector_layout.addWidget(report_period_label)

        self.report_period_combo = QComboBox()
        self.report_period_combo.setMinimumWidth(180)
        self.report_period_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {TreasureGoblinTheme.COLORS['surface_light']};
                border: 2px solid {TreasureGoblinTheme.COLORS['primary_dark']};
                border-radius: 6px;
                padding: 10px 12px;
                color: {TreasureGoblinTheme.COLORS['text_primary']};
                font-size: 15px;
                font-weight: bold;
                min-height: 25px;
            }}
            QComboBox:focus {{
                border: 2px solid {TreasureGoblinTheme.COLORS['accent']};
                background-color: {TreasureGoblinTheme.COLORS['surface']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {TreasureGoblinTheme.COLORS['text_primary']};
                margin-right: 5px;
            }}
        """)
        period_selector_layout.addWidget(self.report_period_combo)

        top_controls_layout.addLayout(period_selector_layout)

        # Right side - Time period toggle (Monthly/Yearly)
        period_toggle_layout = QHBoxLayout()
        self.report_monthly_button = QPushButton("Monthly")
        self.report_monthly_button.setCheckable(True)
        self.report_monthly_button.setChecked(True)
        self.report_monthly_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #CD5C5C;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #DC2F02;
            }}
        """)
        self.report_monthly_button.clicked.connect(lambda: self.switch_report_period('monthly'))

        self.report_yearly_button = QPushButton("Yearly")
        self.report_yearly_button.setCheckable(True)
        self.report_yearly_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #CD5C5C;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #DC2F02;
            }}
        """)
        self.report_yearly_button.clicked.connect(lambda: self.switch_report_period('yearly'))

        period_toggle_layout.addWidget(self.report_monthly_button)
        period_toggle_layout.addWidget(self.report_yearly_button)
        top_controls_layout.addLayout(period_toggle_layout)

        content_layout.addLayout(top_controls_layout)

        # Chart area
        self.chart_area = QLabel()
        self.chart_area.setMinimumHeight(400)
        self.chart_area.setStyleSheet(f"background-color: {TreasureGoblinTheme.COLORS['surface']};") 
        self.chart_layout = QVBoxLayout(self.chart_area)
        content_layout.addWidget(self.chart_area)

        # Bottom controls - Chart type toggle (Pie/Bar)
        bottom_controls_layout = QHBoxLayout()
        bottom_controls_layout.addStretch()

        self.pie_chart_button = QPushButton("Pie")
        self.pie_chart_button.setCheckable(True)
        self.pie_chart_button.setChecked(True)
        self.pie_chart_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #CD5C5C;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #DC2F02;
            }}
        """)
        self.pie_chart_button.clicked.connect(lambda: self.switch_chart_type('pie'))

        self.bar_chart_button = QPushButton("Bar")
        self.bar_chart_button.setCheckable(True)
        self.bar_chart_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #CD5C5C;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #DC2F02;
            }}
        """)
        self.bar_chart_button.clicked.connect(lambda: self.switch_chart_type('bar'))

        bottom_controls_layout.addWidget(self.pie_chart_button)
        bottom_controls_layout.addWidget(self.bar_chart_button)

        content_layout.addLayout(bottom_controls_layout)

        main_layout.addWidget(content_frame)

        # Initialize state
        self.current_report_type = 'expense'
        self.current_report_period = 'monthly'
        self.current_chart_type = 'pie'

        # Intitialize current date for reports (use current date)
        self.current_report_date = QDate.currentDate()

        # Populate period dropdown and connect signal
        self.populate_report_period_selector()
        self.report_period_combo.currentIndexChanged.connect(self.on_report_period_changed)

        # Load intial report
        self.generate_report()

        return tab
    
    def populate_report_period_selector(self):
        """Populate the period selector dropdown based on current period type and available data."""
        # Temporarily disconnect the signal to avoid triggering during population
        self.report_period_combo.blockSignals(True)
        self.report_period_combo.clear()

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            if self.current_report_period == 'monthly':
                # Get all unique year-month combinations from transactions
                query = """
                    SELECT DISTINCT
                        strftime('%Y', date) as year,
                        strftime('%m', date) as month,
                        strftime('%Y-%m', date) as year_month
                    FROM transactions
                    ORDER BY year_month DESC
                """

                cursor.execute(query)
                results = cursor.fetchall()

                # Add each month-year combination to the dropdown
                for year, month, year_month in results:
                    # Convert to readable format
                    date_obj = datetime.strptime(f"{year}-{month}-01", "%Y-%m-%d")
                    display_text = date_obj.strftime("%B %Y")

                    # Store as QDate for easy comparison
                    qdate = QDate(int(year), int(month), 1)
                    self.report_period_combo.addItem(display_text, qdate)

            else: # yearly
                # Get all unique years from transactions
                query = """
                    SELECT DISTINCT strftime('%Y', date) as year
                    FROM transactions
                    ORDER BY year DESC
                """

                cursor.execute(query)
                results = cursor.fetchall()

                # Add each year to the dropdown
                for (year,) in results:
                    display_text = year

                    # Store as QDate (January 1st of that year)
                    qdate = QDate(int(year), 1, 1)
                    self.report_period_combo.addItem(display_text, qdate)

            conn.close()

            # If no transactions exist, add current period as default
            if self.report_period_combo.count() == 0:
                current_date = QDate.currentDate()
                if self.current_report_period == 'monthly':
                    current_text = current_date.toString("MMMM yyyy")
                else:
                    current_text = str(current_date.year())
                self.report_period_combo.addItem(current_text, current_date)

            # Try to select the current report date if it exists in the list
            current_index = -1
            for i in range(self.report_period_combo.count()):
                combo_date = self.report_period_combo.itemData(i)
                if self.current_report_period == 'monthly':
                    # Compare year and month
                    if (combo_date.year() == self.current_report_date.year() and
                        combo_date.month() == self.current_report_date.month()):
                        current_index = i
                        break
                else: # yearly
                    # Compare year only
                    if combo_date.year() == self.current_report_date.year():
                        current_index = i
                        break

            # Set the current selection (defaultes to first item if not found)
            if current_index >= 0:
                self.report_period_combo.setCurrentIndex(current_index)
            else:
                self.report_period_combo.setCurrentIndex(0)

                # Updated current_report_date to match the selected item
                if self.report_period_combo.count() > 0:
                    self.current_report_date = self.report_period_combo.itemData(0)
        
        except Exception as e:
            print(f"Error populating report period selector: {e}")

            # Fallback add current period
            current_date = QDate.currentDate()
            if self.current_report_period == 'monthly':
                current_text = current_date.toString("MMMM yyyy")
            else:
                current_text = str(current_date.year())
            self.report_period_combo.addItem(current_text, current_date)
            self.current_report_date = current_date
        
        finally:
            # Re-enable signals
            self.report_period_combo.blockSignals(False)

    def on_report_period_changed(self):
        """Handle when the user selects a different period from the dropdown."""
        current_index = self.report_period_combo.currentIndex()
        if current_index >= 0:
            # Get the selected date
            selected_date = self.report_period_combo.itemData(current_index)
            if selected_date:
                self.current_report_date = selected_date
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

    def switch_report_period(self, period):
        """Switch between monthly and yearly reports."""
        if period == 'monthly':
            self.report_monthly_button.setChecked(True)
            self.report_yearly_button.setChecked(False)
        else: # period == 'yearly'
            self.report_monthly_button.setChecked(False)
            self.report_yearly_button.setChecked(True)

        self.current_report_period = period

        # Repopulate the dropdown with the new period type
        self.populate_report_period_selector()

        # Generate report for the new period
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

        query = """
            SELECT
                c.name as category,
                SUM(t.amount) as total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.type = ? AND t.date BETWEEN ? AND ? AND c.name != '{NO_CATEGORY}'
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
        message.setStyleSheet(f"""
            font-size: 16px;
            color: {TreasureGoblinTheme.COLORS['text_primary']};
        """)
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
        # Get period text from dropdown
        period_text = self.report_period_combo.currentText() if self.report_period_combo.currentText() else "Current Period"
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

        # Calculate the maximum label length to determine left margin
        max_label_length = max(len(str(cat)) for cat in categories) if categories else 10
        
        # Estimate character width (rough approximation)
        estimated_left_margin = min (0.3, max(0.15, max_label_length * 0.012))

        # Create a figure and a set of subplots
        figure = Figure(figsize=(10, 6), dpi=100)
        canvas = FigureCanvas(figure)
        ax = figure.add_subplot(111)

        # Create a horizontal bar chart
        bars = ax.barh(categories, amounts, color='#CD5C5C')

        # Add data labels to the right of each bar
        for bar in bars:
            width = bar.get_width()
            ax.text(width + max(amounts) * 0.01, bar.get_y() + bar.get_height()/2,
                    f'${width:.2f}', ha='left', va='center', fontweight='bold')
            
        # Remove the top and right spines
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Add gridlines
        ax.grid(axis='x', linestyle='--', alpha=0.7)

        # Add title based on current report settings
        period_text = self.report_period_combo.currentText() if self.report_period_combo.currentText() else "Current Period"
        type_text = "Income" if self.current_report_type == 'income' else "Expenses"
        ax.set_title(f"{type_text} Breakdown - {period_text}", fontsize=14, fontweight='bold', pad=20)

        # Set the background color of the figure to match the application
        figure.patch.set_facecolor('#E0E0E0')

        # Set x-axis label
        ax.set_xlabel('Amount ($)', fontweight='bold')

        # Additional adjustments to better center the bar chart
        figure.subplots_adjust(
            left=estimated_left_margin,
            right=0.85, 
            top=0.9, 
            bottom=0.15
        )

        # Add the bar chart to the chart area
        self.chart_layout.addWidget(canvas)


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