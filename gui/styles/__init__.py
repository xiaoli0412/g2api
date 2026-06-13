"""Windows 11 native design tokens for the PyQt shell."""

from PyQt5.QtGui import QFont


COLORS = {
    "bg": "#202020",
    "nav_bg": "#1B1E21",
    "surface": "#1F1F1F",
    "card_bg": "#2A2D33",
    "card_hover": "#30333A",
    "card_pressed": "#343740",
    "mica_tint_alpha": 226,
    "acrylic_tint_alpha": 184,
    "photo_tint_alpha": 174,
    "acrylic_gradient": 0xB8202020,
    "menu_alpha": 238,
    "hover_bg": "#2D2D2D",
    "selected_bg": "#3B3B3B",
    "pressed_bg": "#454545",
    "text_primary": "#FFFFFF",
    "text_secondary": "#999999",
    "text_disabled": "#666666",
    "border": "#333333",
    "accent": "#0078D4",
    "danger": "#E81123",
    "control_bg": "#2B2B2B",
    "control_bg_alt": "#34343A",
    "success": "#FFFFFF",
    "warning": "#999999",
    "shadow": "#000000",
}

SPACING = {
    "xxs": 2,
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 20,
    "xxl": 24,
}

RADIUS = {
    "control": 4,
    "window": 8,
    "card": 8,
}

SIZES = {
    "titlebar_height": 48,
    "nav_width": 320,
    "nav_item_height": 44,
    "toolbar_height": 40,
    "button_height": 32,
    "icon_button": 24,
    "row_height": 56,
    "large_icon_button": 32,
    "settings_card_height": 72,
}

FONT_FAMILY = "Segoe UI Variable"
FALLBACK_FONT_FAMILY = "Segoe UI"
ICON_FONT_FAMILY = "Segoe Fluent Icons"
ICON_FALLBACK_FONT_FAMILY = "Segoe MDL2 Assets"

FONT_SPECS = {
    "window_title": (14, 600),
    "page_title": (28, 600),
    "section_title": (20, 600),
    "body": (13, 400),
    "button": (13, 400),
    "menu": (13, 400),
    "helper": (12, 400),
    "column": (12, 500),
    "caption": (11, 400),
    "code": (12, 400),
    "icon": (16, 400),
}


def font(name="body"):
    size, weight = FONT_SPECS.get(name, FONT_SPECS["body"])
    qfont = QFont(FONT_FAMILY, size)
    if weight >= 600:
        qfont.setWeight(QFont.DemiBold)
    elif weight >= 500:
        qfont.setWeight(QFont.Medium)
    else:
        qfont.setWeight(QFont.Normal)
    return qfont


TRANSITION_MS = 150


def qss_font(name="body"):
    size, weight = FONT_SPECS.get(name, FONT_SPECS["body"])
    return f"font-family: '{FONT_FAMILY}', '{FALLBACK_FONT_FAMILY}'; font-size: {size}px; font-weight: {weight};"


def qss_icon_font(size=16):
    return f"font-family: '{ICON_FONT_FAMILY}', '{ICON_FALLBACK_FONT_FAMILY}'; font-size: {size}px; font-weight: 400;"


def base_qss():
    return f"""
        QWidget {{
            color: {COLORS['text_primary']};
            background: transparent;
            {qss_font('body')}
        }}
        QMainWindow {{
            background: transparent;
        }}
        QWidget#Page, QStackedWidget, QFrame#ContentRoot {{
            background: transparent;
        }}
        QFrame#Shell {{
            background: transparent;
            border: none;
        }}
        QFrame#TitleBar {{
            background: transparent;
            border-bottom: 1px solid {COLORS['border']};
        }}
        QFrame#PageHeader {{
            background: transparent;
            border: none;
        }}
        QFrame#SystemSection {{
            background: transparent;
            border: none;
        }}
        QFrame#SettingsCard {{
            background-color: {COLORS['card_bg']};
            border: 1px solid rgba(255, 255, 255, 12);
            border-radius: {RADIUS['card']}px;
        }}
        QFrame#SettingsCard:hover {{
            background-color: {COLORS['card_hover']};
        }}
        QFrame#CommandBar {{
            background: transparent;
            border: none;
        }}
        QLabel#SectionLabel {{
            color: {COLORS['text_secondary']};
            {qss_font('column')}
        }}
        QFrame#ListRow {{
            background: transparent;
            border-radius: {RADIUS['control']}px;
        }}
        QFrame#ListRow:hover {{
            background-color: {COLORS['hover_bg']};
        }}
        QFrame#ListRow[active="true"] {{
            background-color: {COLORS['selected_bg']};
        }}
        QToolTip {{
            color: {COLORS['text_primary']};
            background-color: rgba(32, 32, 32, {COLORS['menu_alpha']});
            border: 1px solid {COLORS['border']};
            border-radius: {RADIUS['control']}px;
            padding: 4px 8px;
            {qss_font('caption')}
        }}
        QMenu {{
            color: {COLORS['text_primary']};
            background-color: rgba(32, 32, 32, {COLORS['menu_alpha']});
            border: 1px solid {COLORS['border']};
            border-radius: {RADIUS['control']}px;
            padding: 4px 0;
            {qss_font('menu')}
        }}
        QMenu::item {{
            min-height: 32px;
            padding: 0 28px 0 36px;
            background: transparent;
        }}
        QMenu::item:selected {{
            background-color: {COLORS['hover_bg']};
        }}
        QMenu::item:disabled {{
            color: {COLORS['text_disabled']};
        }}
        QMenu::separator {{
            height: 1px;
            background: {COLORS['border']};
            margin: 4px 0;
        }}
        QAbstractItemView {{
            color: {COLORS['text_primary']};
            background-color: transparent;
            border: none;
            outline: none;
            selection-background-color: {COLORS['selected_bg']};
            selection-color: {COLORS['text_primary']};
        }}
        QHeaderView::section {{
            color: {COLORS['text_secondary']};
            background: transparent;
            border: none;
            border-bottom: 1px solid {COLORS['border']};
            padding: 0 8px;
            {qss_font('column')}
        }}
        QTableView, QListView, QTreeView {{
            background: transparent;
            border: none;
            gridline-color: {COLORS['border']};
            alternate-background-color: transparent;
        }}
        QTableView::item, QListView::item, QTreeView::item {{
            min-height: {SIZES['row_height']}px;
            padding: 8px;
            border-radius: {RADIUS['control']}px;
        }}
        QTableView::item:hover, QListView::item:hover, QTreeView::item:hover {{
            background: {COLORS['hover_bg']};
        }}
        QTableView::item:selected, QListView::item:selected, QTreeView::item:selected {{
            background: {COLORS['selected_bg']};
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {COLORS['selected_bg']};
            border-radius: 4px;
            min-height: 24px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 8px;
            margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            background: {COLORS['selected_bg']};
            border-radius: 4px;
            min-width: 24px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    """
