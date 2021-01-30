if __name__ == '__main__':
    from labeldcm.module.app import LabelApp
    from PyQt5.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    labelApp = LabelApp()
    labelApp.show()
    sys.exit(app.exec())
