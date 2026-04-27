"""CollapsibleSidebar — Faz UI-1.

Reusable sidebar widget with expand/collapse support.
Used in 3 locations:
  - System Modeling: Library panel (side=left, default expanded)
  - System Controlling: Configuration panel (side=left, default expanded)
  - System Controlling: Model Equations panel (side=right, default collapsed)

States:
  - Expanded: header (title + toggle button) + content widget, fixed width
  - Collapsed: narrow vertical rail with rotated title, click to expand

API:
  sidebar = CollapsibleSidebar("Library", my_panel, side="left", expanded=True)
  sidebar.toggle()
  sidebar.expand()
  sidebar.collapse()
  sidebar.is_expanded  # bool
"""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class CollapsedSidebarRail(QWidget):
    """Narrow vertical rail shown when the sidebar is collapsed.

    Displays the sidebar title rotated -90 degrees with a subtle accent line.
    Clicking anywhere on the rail expands the parent sidebar.
    """

    def __init__(self, title: str, side: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self.side = side
        self.setObjectName("CollapsedSidebarRail")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"Open {title}")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            sidebar = self.parent()
            if isinstance(sidebar, CollapsibleSidebar):
                sidebar.expand()
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background rounded rect
        rect = self.rect().adjusted(5, 5, -5, -5)
        painter.setBrush(QColor("#252729"))
        painter.setPen(QPen(QColor("#464b50"), 1))
        painter.drawRoundedRect(rect, 7, 7)

        # Accent line (blue vertical stripe)
        accent_x = rect.left() + 5 if self.side == "left" else rect.right() - 5
        painter.setPen(QPen(QColor("#4a90e2"), 2))
        painter.drawLine(accent_x, rect.top() + 14, accent_x, rect.bottom() - 14)

        # Rotated title text
        painter.setPen(QPen(QColor("#d8dde2")))
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(-90)
        text_rect = QRect(
            -self.height() // 2,
            -self.width() // 2,
            self.height(),
            self.width(),
        )
        painter.drawText(text_rect, Qt.AlignCenter, self.title)


class CollapsibleSidebar(QFrame):
    """Expandable/collapsible sidebar container.

    Parameters
    ----------
    title : str
        Label shown in the header and on the collapsed rail.
    content : QWidget
        The panel widget to display when expanded.
    side : str
        ``"left"`` or ``"right"`` — determines toggle button placement
        and accent stripe position.
    expanded : bool
        Initial state.  ``True`` = start expanded.
    expanded_width : int
        Fixed width when expanded (default 300px).
    collapsed_width : int
        Fixed width when collapsed (default 44px).
    """

    toggled = Signal(bool)  # emitted with new is_expanded state

    DEFAULT_EXPANDED_WIDTH = 300
    DEFAULT_COLLAPSED_WIDTH = 44

    def __init__(
        self,
        title: str,
        content: QWidget,
        *,
        side: str = "left",
        expanded: bool = True,
        expanded_width: int = DEFAULT_EXPANDED_WIDTH,
        collapsed_width: int = DEFAULT_COLLAPSED_WIDTH,
    ) -> None:
        super().__init__()
        self.title = title
        self.side = side
        self.content = content
        self.is_expanded = expanded
        self._expanded_width = expanded_width
        self._collapsed_width = collapsed_width

        self.setObjectName("CollapsibleSidebar")
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        # --- Toggle button ---
        self.toggle_button = QPushButton("›" if side == "left" else "‹")
        self.toggle_button.setObjectName("SidebarToggleButton")
        self.toggle_button.setFixedSize(24, 24)
        self.toggle_button.setToolTip(f"Toggle {title}")
        self.toggle_button.clicked.connect(self.toggle)

        # --- Title label ---
        self.title_label = QLabel(title)
        self.title_label.setObjectName("SidebarTitle")

        # --- Header ---
        header = QWidget()
        header.setObjectName("SidebarHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 8, 10, 8)
        header_layout.setSpacing(8)

        if side == "right":
            header_layout.addWidget(self.toggle_button)
            header_layout.addWidget(self.title_label, 1)
        else:
            header_layout.addWidget(self.title_label, 1)
            header_layout.addWidget(self.toggle_button)

        # --- Expanded page ---
        self.expanded_page = QWidget()
        expanded_layout = QVBoxLayout(self.expanded_page)
        expanded_layout.setContentsMargins(0, 0, 0, 0)
        expanded_layout.setSpacing(0)
        expanded_layout.addWidget(header)
        expanded_layout.addWidget(content, 1)

        # --- Collapsed page ---
        self.collapsed_page = CollapsedSidebarRail(title, side, self)

        # --- Main layout ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.expanded_page)
        layout.addWidget(self.collapsed_page)

        self._apply_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def toggle(self) -> None:
        """Toggle between expanded and collapsed."""
        self.is_expanded = not self.is_expanded
        self._apply_state()
        self.toggled.emit(self.is_expanded)

    def expand(self) -> None:
        """Force expand."""
        if not self.is_expanded:
            self.is_expanded = True
            self._apply_state()
            self.toggled.emit(True)

    def collapse(self) -> None:
        """Force collapse."""
        if self.is_expanded:
            self.is_expanded = False
            self._apply_state()
            self.toggled.emit(False)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _apply_state(self) -> None:
        self.expanded_page.setVisible(self.is_expanded)
        self.collapsed_page.setVisible(not self.is_expanded)
        self.setFixedWidth(
            self._expanded_width if self.is_expanded else self._collapsed_width
        )
        # Arrow points inward when expanded (collapse direction)
        if self.is_expanded:
            self.toggle_button.setText("‹" if self.side == "left" else "›")
        else:
            self.toggle_button.setText("›" if self.side == "left" else "‹")
