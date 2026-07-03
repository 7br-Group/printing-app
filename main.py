import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from gui.main_window import MainWindow, load_stylesheet


def main():
    app = QApplication(sys.argv)

    app.setFont(QFont("Segoe UI", 12))
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

    style = load_stylesheet()
    if style:
        app.setStyleSheet(style)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
