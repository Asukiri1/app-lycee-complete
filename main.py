# main.py
import sys
import os
from PyQt6.QtWidgets import QApplication
from main_window import MainWindow

def main():
    if os.path.exists('logs.db'):
        os.remove('logs.db')
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
