from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QFrame, QLabel, QScrollArea, QSizePolicy


class ScrollableValueField(QScrollArea):
    def __init__(self, text: str = "-", parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(False)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(0)
        self.setFixedHeight(24)

        self._label = QLabel(text)
        self._label.setWordWrap(False)
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.setWidget(self._label)
        self.setText(text)

    def setText(self, text: str) -> None:
        self._label.setText(text)
        self._label.adjustSize()
        self.horizontalScrollBar().setValue(0)

    def text(self) -> str:
        return self._label.text()

    def has_horizontal_scrollbar(self) -> bool:
        return self.horizontalScrollBarPolicy() != Qt.ScrollBarAlwaysOff

    def has_horizontal_overflow(self) -> bool:
        return self.horizontalScrollBar().maximum() > 0


class PropertyEditor(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(0)

        layout = QFormLayout(self)
        layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        layout.setContentsMargins(8, 8, 8, 8)

        self.name_value = ScrollableValueField("No selection")
        self.port_value = ScrollableValueField("-")
        self.id_value = ScrollableValueField("-")
        self.domain_value = ScrollableValueField("-")
        self.category_value = ScrollableValueField("-")
        self.boundary_value = ScrollableValueField("-")
        self.motion_value = ScrollableValueField("-")
        self.directional_value = ScrollableValueField("-")
        self.source_value = ScrollableValueField("-")
        self.source_type_value = ScrollableValueField("-")
        self.rotation_value = ScrollableValueField("0")
        self.status_value = ScrollableValueField("Click a component to select it.")

        layout.addRow("Selected", self.name_value)
        layout.addRow("Component ID", self.id_value)
        layout.addRow("Domain", self.domain_value)
        layout.addRow("Category", self.category_value)
        layout.addRow("Boundary", self.boundary_value)
        layout.addRow("Motion", self.motion_value)
        layout.addRow("Directional", self.directional_value)
        layout.addRow("Source", self.source_value)
        layout.addRow("Source Type", self.source_type_value)
        layout.addRow("Rotation", self.rotation_value)
        layout.addRow("Ports", self.port_value)
        layout.addRow("Status", self.status_value)

    def set_component(self, details: dict[str, object]) -> None:
        self.name_value.setText(str(details.get("name", "No selection")))
        self.id_value.setText(str(details.get("component_id", "-")))
        self.domain_value.setText(str(details.get("domain", "-")))
        self.category_value.setText(str(details.get("visual_category", "-")))
        self.boundary_value.setText(str(details.get("boundary_role", "-")))
        self.motion_value.setText(str(details.get("motion_profile", "-")))
        self.directional_value.setText(str(details.get("directional", "-")))
        self.source_value.setText(str(details.get("source_component", "-")))
        self.source_type_value.setText(str(details.get("source_type", "-")))
        self.rotation_value.setText(f"{details.get('rotation_degrees', 0)}°")
        self.port_value.setText(str(details.get("ports", 0)))
        self.status_value.setText(str(details.get("status_text", "")))
