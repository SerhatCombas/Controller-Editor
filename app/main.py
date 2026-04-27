#!/usr/bin/env python3
"""System Designer — application entry point.

Faz UI-5: SystemDesignerShell — 2-module layout with dark theme.
Replaces MainWindowV2 (3-column layout, static analysis only).
"""
import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window_v3 import SystemDesignerShell


def main() -> int:
    app = QApplication(sys.argv)
    window = SystemDesignerShell()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
