"""
TreasureGoblin UI Components

Reusable UI components and widgets for the TreasureGoblin application.
"""

from PyQt5.QtWidgets import (QFrame, QPushButton, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QGraphicsDropShadowEffect)
from PyQt5.QtGui import QColor

from theme import TreasureGoblinTheme


class GoblinCard(QFrame):
    """Custom card widget with styling"""

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.title = title
        self.setup_ui()
        self.apply_effects()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)

        if self.title:
            title_label = QLabel(self.title)
            title_label.setObjectName("subheadingLabel")
            self.layout.addWidget(title_label)

    def apply_effects(self):
        # Adding drop shadow for more depth
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(TreasureGoblinTheme.COLORS['shadow']))
        self.setGraphicsEffect(shadow)


class TreasureButton(QPushButton):
    """Button with hover animations"""

    def __init__(self, text, button_type="primary", parent=None):
        super().__init__(text, parent)
        self.button_type = button_type
        self.setup_style()

    def setup_style(self):
        if self.button_type == "accent":
            self.setObjectName("accentButton")
        elif self.button_type == "danger":
            self.setObjectName("dangerButton")

    def enterEvent(self, event):
        super().enterEvent(event)

    def leaveEvent(self, event):
        super().leaveEvent(event)


class MoneyDisplay(QWidget):
    """Custom widget for displaying monetary values"""

    def __init__(self, label="", amount=0.0, is_positive=True, parent=None):
        super().__init__(parent)
        self.label = label
        self.amount = amount
        self.is_positive = is_positive
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if self.label:
            label_widget = QLabel(self.label)
            label_widget.setStyleSheet(f"color: {TreasureGoblinTheme.COLORS['text_secondary']};")
            layout.addWidget(label_widget)

        amount_label = QLabel(f"${self.amount:,.2f}")
        color = TreasureGoblinTheme.COLORS['success_light'] if self.is_positive else TreasureGoblinTheme.COLORS['danger_light']
        amount_label.setStyleSheet(f"""
              color: {color};
              font-family: Consolas;
              font-size: 16px;
              font-weight: bold;
        """)
        layout.addWidget(amount_label)
        layout.addStretch()

    def update_amount(self, amount, is_positive=None):
        self.amount = amount
        if is_positive is not None:
            self.is_positive = is_positive
            
        # Update the display
        self.setup_ui()


class CategoryButton(QPushButton):
    """Special button for category display with visuals"""

    def __init__(self, text, category_type="expense", parent=None):
        super().__init__(text, parent)
        self.category_type = category_type
        self.setMinimumSize(120, 60)
        self.setup_style()

    def setup_style(self):
        c = TreasureGoblinTheme.COLORS
        if self.category_type == "expense":
            bg_color = c['danger']
            hover_color = c['danger_light']
        else:
            bg_color = c['success']
            hover_color = c['success_light']

        self.setStyleSheet(f"""
            QPushButton{{
                background-color: {bg_color};
                color: {c['text_primary']};
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
                border: 2px solid {c['accent']};
            }}
        """)


class TransactionItemWidget(QWidget):
    """Custom widget for transaction list items with hover effects"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_selected = False
        self.is_hovered = False
        self.default_style = ""

    def set_default_style(self, style):
        """Set the default style for no-category"""
        self.default_style = style
        self.update_style()

    def update_style(self):
        """Update the widget style based on state"""
        if self.is_selected:
            self.setStyleSheet(f"""
                {self.default_style}
                background-color: {TreasureGoblinTheme.COLORS['primary_dark']};
                border: 1px solid {TreasureGoblinTheme.COLORS['accent']};
                border-radius: 4px;
            """)
        elif self.is_hovered:
            self.setStyleSheet(f"""
                {self.default_style}
                background-color: rgba(45, 106, 79, 0.3);
                border-radius: 4px;
            """)
        else:
            self.setStyleSheet(self.default_style)

    def enterEvent(self, event):
        """Mouse enters the widget"""
        self.is_hovered = True
        self.update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Mouse leaves the widget"""
        self.is_hovered = False
        self.update_style()
        super().leaveEvent(event)

    def set_selected(self, selected):
        """Set selection state"""
        self.is_selected = selected
        self.update_style()
