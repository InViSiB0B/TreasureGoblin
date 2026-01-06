"""
TreasureGoblin Theme Module

Centralized theme and styling for the TreasureGoblin application.
"""

from PyQt5.QtGui import QFont


class TreasureGoblinTheme:
    """Central theme manager"""

    # Main color palette
    COLORS = {
        # Primary colors
        'primary_dark': '#1B4332',
        'primary': '#2D6A4F',
        'primary_light': '#40916C',
        'primary_lighter': '#52B788',

        # Accent colors
        'accent_dark': '#D4A574',
        'accent': '#FFB700',
        'accent_light': '#FFD60A',

        # Supporting colors
        'danger': '#9D0208',
        'danger_light': '#DC2F02',
        'success': '#2D6A4F',
        'success_light': '#40916C',

        # Neutral colors
        'background': '#0D1B2A',
        'surface': '#1B263B',
        'surface_light': '#415A77',
        'text_primary': '#E0E1DD',
        'text_secondary': '#778DA9',

        # Special effects
        'glow': '#FFD60A',
        'shadow': '#000814',
    }

    # Typography
    FONTS = {
        'heading': ('Georgia', 24, QFont.Bold),
        'subheading': ('Georgia', 18, QFont.Bold),
        'body': ('Segoe UI', 11, QFont.Normal),
        'button': ('Segoe UI', 10, QFont.Bold),
        'small': ('Segoe UI', 9, QFont.Normal),
        'number': ('Consolas', 14, QFont.Bold),
    }

    @staticmethod
    def get_stylesheet():
        """Generate the main stylesheet"""
        c = TreasureGoblinTheme.COLORS
        return f"""
        /* Main Window */
        QMainWindow {{
            background-color: {c['background']};
        }}

        /* Central Widget */
        QWidget {{
            background-color: {c['background']};
            color: {c['text_primary']};
        }}

        /* Tab Widget */
        QTabWidget::pane {{
            background-color: {c['surface']};
            border: 2px solid {c['primary_dark']};
            border-radius: 8px;
            margin-top: -2px;
        }}

        QTabBar::tab {{
            background-color: {c['surface_light']};
            color: {c['text_secondary']};
            padding: 15px 30px;
            margin-right: 4px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            font-weight: bold;
            font-size: 12px;
            min-width: 100px;
            min-height: 40px;
        }}

        QTabBar::tab:selected {{
            background-color: {c['primary']};
            color: {c['text_primary']};
            border-bottom: 3px solid {c['accent']};
        }}

        QTabBar::tab:hover {{
            background-color: {c['primary_light']};
            color: {c['text_primary']};
        }}

        /* Group Boxes */
        QGroupBox {{
            background-color: {c['surface']};
            border: 2px solid {c['primary_dark']};
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 10px;
            font-weight: bold;
            color: {c['accent']};
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 10px 0 10px;
            background-color: transparent;
            color: {c['accent']};
            font-size: 24px;
            font-family: Georgia;
            font-weight: bold;
        }}

        /* Buttons */
        QPushButton {{
            background-color: {c['primary']};
            color: {c['text_primary']};
            border: 2px solid transparent;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
            min-height: 32px;
        }}

        QPushButton:hover {{
            background-color: {c['primary_light']};
            border: 2px solid {c['accent']};
        }}

        QPushButton:pressed {{
            background-color: {c['primary_dark']};
        }}

        QPushButton:disabled {{
            background-color: {c['surface_light']};
            color: {c['text_secondary']};
        }}

        /* Accent Buttons */
        QPushButton#accentButton {{
            background-color: {c['accent']};
            color: {c['background']};
            border: 2px solid transparent;
        }}

        QPushButton#accentButton:hover {{
            background-color: {c['accent_light']};
        }}

        /* Danger Buttons */
        QPushButton#dangerButton {{
            background-color: {c['danger']};
            border: 2px solid transparent;
        }}

        QPushButton#dangerButton:hover {{
            background-color: {c['danger_light']};
        }}

        /* List Widgets */
        QListWidget {{
            background-color: {c['surface']};
            border: 2px solid {c['primary_dark']};
            border-radius: 8px;
            padding: 5px;
            outline: none;
            alternate-background-color: {c['surface']};
        }}

        QListWidget::item {{
            background-color: transparent;
            border: none;
            border-radius: 0px;
            padding: 0px;
            margin: 2px 0;
        }}

        QListWidget::item:selected {{
            background-color: rgba(45, 106, 79, 0.2);
            border: none;
        }}

        QListWidget::item:hover {{
            background-color: rgba(45, 106, 79, 0.1);
            border: none;
        }}

        QListWidget::item:focus {{
            outline: none;
            border: none;
        }}

        /* Input Fields */
        QLineEdit, QDateEdit, QComboBox {{
            background-color: {c['surface_light']};
            border: 2px solid {c['primary_dark']};
            border-radius: 6px;
            padding: 6px 10px;
            color: {c['text_primary']};
            font-size: 11px;
        }}

        QLineEdit:focus, QDateEdit:focus, QComboBox:focus {{
            border: 2px solid {c['accent']};
            background-color: {c['surface']};
        }}

        QComboBox::drop-down {{
            border: none;
            width: 30px;
        }}

        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid {c['text_primary']};
            margin-right: 5px;
        }}

        /* Labels */
        QLabel {{
            color: {c['text_primary']};
        }}

        QLabel#headingLabel {{
            color: {c['accent']};
            font-size: 24px;
            font-weight: bold;
            font-family: Georgia;
        }}

        QLabel#subheadingLabel {{
            color: {c['accent_light']};
            font-size: 18px;
            font-weight: bold;
        }}

        /* Frames */
        QFrame#cardFrame {{
            background-color: {c['surface']};
            border: 2px solid {c['primary_dark']};
            border-radius: 12px;
            padding: 15px;
        }}

        /* Scrollbars */
        QScrollBar:vertical {{
            background-color: {c['surface']};
            width: 12px;
            border-radius: 6px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {c['primary']};
            border-radius: 6px;
            min-height: 20px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {c['primary_light']};
        }}

        /* Status Bar */
        QStatusBar {{
            background-color: {c['surface']};
            color: {c['text_secondary']};
            border-top: 2px solid {c['primary_dark']};
        }}
        """
