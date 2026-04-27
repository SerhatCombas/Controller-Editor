#!/usr/bin/env python3
"""System Designer — application entry point.

Uses src.application.SystemDesignerShell for the 2-module layout.
"""
import sys

from PySide6.QtWidgets import QApplication

from src.application.SystemDesignerShell import SystemDesignerShell


def main() -> int:
    app = QApplication(sys.argv)
    window = SystemDesignerShell()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
