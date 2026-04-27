"""ModelLibraryPanel — Faz UI-2a.

Standalone component library panel extracted from ModelPanel.
Contains the 4-level palette tree + search box.
Designed to be placed inside a CollapsibleSidebar.

Usage:
    library_panel = ModelLibraryPanel()
    sidebar = CollapsibleSidebar("Library", library_panel, side="left")
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.panels.model_panel import ComponentPalette


class ModelLibraryPanel(QWidget):
    """Component library with search and 4-level hierarchy tree.

    Reuses ComponentPalette (the existing tree implementation) but
    wraps it in a standalone panel suitable for CollapsibleSidebar.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModelLibraryPanel")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Search box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search components...")
        self.search_input.setClearButtonEnabled(True)
        layout.addWidget(self.search_input)

        # Palette tree (4-level: Domain > Subdomain > Category > Component)
        self.palette = ComponentPalette()
        palette_scroll = QScrollArea()
        palette_scroll.setWidgetResizable(True)
        palette_scroll.setFrameShape(QFrame.NoFrame)
        palette_scroll.setWidget(self.palette)
        layout.addWidget(palette_scroll, 1)

        # Wire search → filter
        self.search_input.textChanged.connect(self.palette.apply_filter)

    # ------------------------------------------------------------------
    # Public API — delegate to palette
    # ------------------------------------------------------------------

    @property
    def sections(self) -> dict:
        """Direct access to palette sections for backward compat."""
        return self.palette.sections

    def apply_filter(self, query: str) -> None:
        self.palette.apply_filter(query)
