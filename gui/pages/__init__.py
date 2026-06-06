"""页面模块"""
from .home_page import HomePage
from .server_page import ServerPage
from .cookie_page import CookiePage
from .stream_page import StreamPage
from .search_page import SearchPage
from .settings_page import SettingsPage

__all__ = [
    'HomePage',
    'ServerPage', 
    'CookiePage',
    'StreamPage',
    'SearchPage',
    'SettingsPage'
]