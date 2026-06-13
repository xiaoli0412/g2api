"""Auto-start helper - adds/removes app from Windows startup."""
import winreg
import os
import sys

APP_NAME = "Gemini2API"
APP_PATH = os.path.abspath(sys.argv[0]) if getattr(sys, 'frozen', False) else os.path.abspath(__file__)


def add_startup():
    """Add app to Windows startup registry."""
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows\CurrentVersion\Run",
                         0, winreg.KEY_SET_VALUE)
    exe = APP_PATH if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{APP_PATH}"'
    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe)
    winreg.CloseKey(key)
    print(f"Added {APP_NAME} to startup")


def remove_startup():
    """Remove app from Windows startup registry."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
        print(f"Removed {APP_NAME} from startup")
    except FileNotFoundError:
        print(f"{APP_NAME} not in startup")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "remove":
        remove_startup()
    else:
        add_startup()
