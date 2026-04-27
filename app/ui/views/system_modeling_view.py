"""SystemModelingView — Faz UI-2c (v2).

Composition view for the "System Modelling" module.

Layout:
  ┌────────────────────────────────────────────────────────┐
  │  CollapsibleSidebar("Library")  │  Canvas (workspace)  │
  │    ModelLibraryPanel            │    ModelCanvas        │
  │    - Search box                 │    - drag/drop        │
  │    - 4-level palette tree       │    - wire drawing     │
  │                                 │    - right-click I/O  │
  ├─────────────────────────────────┴──────────────────────┤
  │  ComponentInspectorPanel (full width, shows on select)  │
  └────────────────────────────────────────────────────────┘

Inspector spans full width below BOTH library and canvas.
When inspector opens, the top area (library + canvas) shrinks.

Signals:
  - Canvas → InspectorPanel: component_selected
  - Library → Canvas: drag-and-drop (via MIME type)
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.ui.canvas.model_canvas import ModelCanvas
from app.ui.panels.component_inspector_panel import ComponentInspectorPanel
from app.ui.panels.model_library_panel import ModelLibraryPanel
from app.ui.widgets.collapsible_sidebar import CollapsibleSidebar


class SystemModelingView(QWidget):
    """System Modelling module — left half of the application.

    Composes:
      - ModelLibraryPanel inside a CollapsibleSidebar (left)
      - ModelCanvas as the central workspace
      - ComponentInspectorPanel spanning full width below both
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # --- Library sidebar ---
        self.library_panel = ModelLibraryPanel()
        self.library_sidebar = CollapsibleSidebar(
            "Library",
            self.library_panel,
            side="left",
            expanded=True,
            expanded_width=280,
        )

        # --- Canvas ---
        self.canvas = ModelCanvas()

        # --- Inspector panel (full-width bottom, hidden until selection) ---
        self.inspector_panel = ComponentInspectorPanel()

        # --- Workspace toolbar ---
        toolbar = QWidget()
        toolbar.setFixedHeight(36)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)
        toolbar_layout.setSpacing(8)
        self.workspace_title = QLabel("Workspace")
        self.workspace_title.setStyleSheet("font-weight: 700; font-size: 13px;")
        self.component_count_label = QLabel("0 components")
        self.component_count_label.setStyleSheet("color: #8a9099; font-size: 12px;")
        toolbar_layout.addWidget(self.workspace_title)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.component_count_label)

        # --- Canvas area (toolbar + canvas) ---
        canvas_area = QWidget()
        canvas_layout = QVBoxLayout(canvas_area)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)
        canvas_layout.addWidget(toolbar)
        canvas_layout.addWidget(self.canvas, 1)

        # --- Top area: sidebar + canvas area side by side ---
        top_area = QWidget()
        top_layout = QHBoxLayout(top_area)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)
        top_layout.addWidget(self.library_sidebar)
        top_layout.addWidget(canvas_area, 1)

        # --- Vertical splitter: top area | inspector (full width) ---
        self._main_splitter = QSplitter(Qt.Vertical)
        self._main_splitter.setChildrenCollapsible(False)
        self._main_splitter.addWidget(top_area)
        self._main_splitter.addWidget(self.inspector_panel)
        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 0)
        self._main_splitter.setSizes([600, 0])

        # --- Main layout ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self._main_splitter, 1)

        # --- Signal wiring ---
        self.canvas.component_selected.connect(self._on_component_selected)
        self.canvas.component_selected.connect(self._update_component_count)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _on_component_selected(self, details: dict | None = None) -> None:
        """Show/hide inspector and adjust splitter sizes accordingly."""
        self.inspector_panel.show_component(details)
        if self.inspector_panel.isVisible():
            # Give inspector ~180px, rest to top area (library + canvas)
            total = self._main_splitter.height() or 700
            self._main_splitter.setSizes([total - 180, 180])
        else:
            total = self._main_splitter.height() or 700
            self._main_splitter.setSizes([total, 0])

    def _update_component_count(self, _details: dict | None = None) -> None:
        count = len(self.canvas._components)
        text = f"{count} component{'s' if count != 1 else ''}"
        self.component_count_label.setText(text)

    def load_default_model(self) -> None:
        """Start with blank workspace (Faz 5MVP compat)."""
        self.canvas.clear_workspace()
