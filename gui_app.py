import sys
import os
import site
import PyQt5

# 添加项目根目录到路径
repo_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, repo_root)


def _candidate_qt_roots():
    roots = [os.path.join(repo_root, "qt_vendor", "PyQt5", "Qt5")]
    pyqt_root = os.path.dirname(os.path.realpath(PyQt5.__file__))
    roots.append(os.path.join(pyqt_root, "Qt5"))
    for base in site.getsitepackages() + [site.getusersitepackages()]:
        roots.append(os.path.join(base, "PyQt5", "Qt5"))
    seen = set()
    unique = []
    for root in roots:
        norm = os.path.normcase(os.path.abspath(root))
        if norm not in seen:
            unique.append(root)
            seen.add(norm)
    return unique


def _setup_qt_paths():
    for qt_root in _candidate_qt_roots():
        plugins = os.path.join(qt_root, "plugins")
        platforms = os.path.join(plugins, "platforms")
        qwindows = os.path.join(platforms, "qwindows.dll")
        bin_path = os.path.join(qt_root, "bin")
        if os.path.exists(qwindows):
            os.environ["QT_PLUGIN_PATH"] = plugins
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = platforms
            if os.path.isdir(bin_path):
                os.environ["PATH"] = bin_path + os.pathsep + os.environ.get("PATH", "")
            return qt_root
    return None


QT_ROOT = _setup_qt_paths()

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from gui.main_window import MainWindow


def main():
    """主函数"""
    if not QT_ROOT:
        print("Qt platform plugin not found. Reinstall PyQt5 or run: pip install --force-reinstall PyQt5", file=sys.stderr)

    # 设置高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # 创建应用
    app = QApplication(sys.argv)
    app.setStyle("fusion")
    app.setFont(QFont("Segoe UI Variable", 10))
    app.setApplicationName("Gemini2API")
    app.setApplicationVersion("2.1.0")
    app.setOrganizationName("xiaoliACG")
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    # 运行应用
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
