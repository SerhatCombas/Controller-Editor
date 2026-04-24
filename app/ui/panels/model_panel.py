from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import QByteArray, QMimeData, QSize, Qt, QTimer
from PySide6.QtGui import QDrag, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QMenu,
    QPushButton,
    QInputDialog,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.canvas.component_system import component_catalog, component_spec_for_display_name
from app.ui.canvas.model_canvas import ModelCanvas
from app.ui.widgets.property_editor import PropertyEditor


@dataclass(frozen=True, slots=True)
class PaletteItemSpec:
    display_name: str


@dataclass(frozen=True, slots=True)
class PaletteNodeSpec:
    title: str
    items: tuple[PaletteItemSpec, ...] = ()
    children: tuple["PaletteNodeSpec", ...] = ()


@dataclass(frozen=True, slots=True)
class WorkspaceLayout:
    id: str
    name: str
    source_type: str
    payload: dict[str, object]
    created_at: str = ""
    updated_at: str = ""


PALETTE_GROUP_ASSIGNMENTS: dict[str, tuple[str, str]] = {
    "mass": ("Mechanical", "Passive"),
    "translational_spring": ("Mechanical", "Passive"),
    "translational_damper": ("Mechanical", "Passive"),
    "wheel": ("Mechanical", "Passive"),
    "mechanical_reference": ("Mechanical", "Passive"),
    "translational_free_end": ("Mechanical", "Passive"),
    "mechanical_random_reference": ("Mechanical", "Sources"),
    "ideal_force_source": ("Mechanical", "Sources"),
    "ideal_torque_source": ("Mechanical", "Sources"),
    "ideal_force_sensor": ("Mechanical", "Sensors"),
    "ideal_torque_sensor": ("Mechanical", "Sensors"),
    "ideal_translational_motion_sensor": ("Mechanical", "Sensors"),
    "resistor": ("Electrical", "Passive"),
    "capacitor": ("Electrical", "Passive"),
    "inductor": ("Electrical", "Passive"),
    "diode": ("Electrical", "Passive"),
    "switch": ("Electrical", "Passive"),
    "ac_voltage_source": ("Electrical", "Sources"),
    "dc_voltage_source": ("Electrical", "Sources"),
    "ac_current_source": ("Electrical", "Sources"),
    "dc_current_source": ("Electrical", "Sources"),
    "voltage_sensor": ("Electrical", "Sensors"),
    "current_sensor": ("Electrical", "Sensors"),
    "dc_current_sensor": ("Electrical", "Sensors"),
    "electrical_reference": ("Electrical", "References"),
}

PALETTE_GROUP_ORDER: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Mechanical", ("Passive", "Sources", "Sensors")),
    ("Electrical", ("Passive", "Sources", "Sensors", "References")),
)


def build_palette_tree() -> tuple[PaletteNodeSpec, ...]:
    catalog = component_catalog()
    grouped: dict[tuple[str, str], list[PaletteItemSpec]] = {}
    for type_key, spec in catalog.items():
        path = PALETTE_GROUP_ASSIGNMENTS.get(type_key)
        if path is None:
            continue
        grouped.setdefault(path, []).append(PaletteItemSpec(spec.display_name))

    sections: list[PaletteNodeSpec] = []
    for top_level, subgroup_order in PALETTE_GROUP_ORDER:
        children: list[PaletteNodeSpec] = []
        for subgroup in subgroup_order:
            items = tuple(sorted(grouped.get((top_level, subgroup), []), key=lambda item: item.display_name))
            children.append(PaletteNodeSpec(title=subgroup, items=items))
        sections.append(PaletteNodeSpec(title=top_level, children=tuple(children)))
    return tuple(sections)


PALETTE_TREE: tuple[PaletteNodeSpec, ...] = build_palette_tree()


DEFAULT_LAYOUTS: tuple[WorkspaceLayout, ...] = (
    WorkspaceLayout(
        id="default_quarter_car",
        name="Quarter-Car Suspension",
        source_type="default",
        payload={"template_id": "quarter_car"},
    ),
    WorkspaceLayout(
        id="default_single_mass",
        name="Single Mass-Spring-Damper",
        source_type="default",
        payload={"template_id": "single_mass"},
    ),
    WorkspaceLayout(
        id="default_two_mass",
        name="Two-Mass System",
        source_type="default",
        payload={"template_id": "two_mass"},
    ),
)


def default_saved_layouts_path() -> Path:
    return Path(__file__).resolve().parents[3] / "models" / "saved_layouts.json"


class ComponentLibraryList(QListWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAlternatingRowColors(True)
        self.setIconSize(QSize(26, 26))

    def populate(self, items: tuple[PaletteItemSpec, ...]) -> None:
        self.clear()
        for item_spec in items:
            spec = component_spec_for_display_name(item_spec.display_name)
            item = QListWidgetItem(item_spec.display_name)
            item.setData(Qt.UserRole, len(spec.connector_ports))
            item.setData(Qt.UserRole + 1, spec.type_key)
            icon = _palette_icon_for_display_name(item_spec.display_name)
            if not icon.isNull():
                item.setIcon(icon)
            self.addItem(item)

    def startDrag(self, supportedActions) -> None:
        item = self.currentItem()
        if item is None:
            return
        mime = QMimeData()
        payload = f"{item.text()}|{item.data(Qt.UserRole)}"
        mime.setData(ModelCanvas.MIME_TYPE, QByteArray(payload.encode("utf-8")))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(supportedActions)

    def visible_items(self) -> list[str]:
        return [self.item(index).text() for index in range(self.count()) if not self.item(index).isHidden()]

    def apply_filter(self, query: str) -> bool:
        lowered = query.strip().lower()
        any_visible = False
        for index in range(self.count()):
            item = self.item(index)
            visible = not lowered or lowered in item.text().lower()
            item.setHidden(not visible)
            any_visible = any_visible or visible
        return any_visible


class LayoutLibraryList(QListWidget):
    def __init__(self, parent=None, *, editable_items: bool = False) -> None:
        super().__init__(parent)
        self._editable_items = editable_items
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._rename_timer = QTimer(self)
        self._rename_timer.setSingleShot(True)
        self._rename_timer.timeout.connect(self._begin_pending_rename)
        self._pending_rename_item: QListWidgetItem | None = None

    def populate(self, layouts: list[WorkspaceLayout] | tuple[WorkspaceLayout, ...]) -> None:
        self.clear()
        for layout_spec in layouts:
            item = QListWidgetItem(layout_spec.name)
            item.setData(Qt.UserRole, layout_spec.id)
            item.setData(Qt.UserRole + 1, layout_spec.source_type)
            if self._editable_items and layout_spec.source_type == "user":
                item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.addItem(item)

    def mousePressEvent(self, event) -> None:
        if self._editable_items and event.button() == Qt.LeftButton:
            clicked_item = self.itemAt(event.position().toPoint())
            already_selected = clicked_item is not None and clicked_item is self.currentItem() and clicked_item.isSelected()
            super().mousePressEvent(event)
            if already_selected and clicked_item is not None:
                self._pending_rename_item = clicked_item
                self._rename_timer.start(QApplication.instance().styleHints().mouseDoubleClickInterval())
                return
            self.cancel_pending_rename()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self.cancel_pending_rename()
        super().mouseDoubleClickEvent(event)

    def cancel_pending_rename(self) -> None:
        self._rename_timer.stop()
        self._pending_rename_item = None

    def _begin_pending_rename(self) -> None:
        item = self._pending_rename_item
        self._pending_rename_item = None
        if item is None or item is not self.currentItem() or not item.isSelected():
            return
        if not (item.flags() & Qt.ItemIsEditable):
            return
        self.editItem(item)


class ComponentPaletteSection(QWidget):
    def __init__(self, node_spec: PaletteNodeSpec, *, expanded: bool = True, depth: int = 0, parent=None) -> None:
        super().__init__(parent)
        self.node_spec = node_spec
        self.depth = depth
        self.child_sections: dict[str, ComponentPaletteSection] = {}
        self._search_active = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(depth * 10, 0, 0, 0)
        layout.setSpacing(6)

        self.toggle_button = QToolButton()
        self.toggle_button.setText(node_spec.title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.toggle_button.setStyleSheet("font-weight: 600; padding: 4px 2px;")
        layout.addWidget(self.toggle_button)

        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        self.library: ComponentLibraryList | None = None
        if node_spec.items:
            self.library = ComponentLibraryList()
            self.library.populate(node_spec.items)
            content_layout.addWidget(self.library)

        for child_index, child in enumerate(node_spec.children):
            child_section = ComponentPaletteSection(child, expanded=child_index == 0, depth=depth + 1)
            self.child_sections[child.title] = child_section
            content_layout.addWidget(child_section)

        content_layout.addStretch(1)
        self.content.setVisible(expanded)
        layout.addWidget(self.content)

        self.toggle_button.toggled.connect(self._set_expanded)

    def _set_expanded(self, expanded: bool) -> None:
        self.toggle_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.content.setVisible(expanded if not self._search_active else self.content.isVisible())

    def is_expanded(self) -> bool:
        return self.toggle_button.isChecked()

    def find_section(self, path: list[str]) -> "ComponentPaletteSection | None":
        if not path:
            return self
        next_title = path[0]
        child = self.child_sections.get(next_title)
        if child is None:
            return None
        return child.find_section(path[1:])

    def leaf_items(self) -> list[str]:
        items: list[str] = []
        if self.library is not None:
            items.extend(self.library.item(index).text() for index in range(self.library.count()))
        for child in self.child_sections.values():
            items.extend(child.leaf_items())
        return items

    def visible_leaf_items(self) -> list[str]:
        items: list[str] = []
        if self.library is not None:
            items.extend(self.library.visible_items())
        for child in self.child_sections.values():
            items.extend(child.visible_leaf_items())
        return items

    def apply_filter(self, query: str) -> bool:
        lowered = query.strip().lower()
        self._search_active = bool(lowered)
        local_match = self.library.apply_filter(lowered) if self.library is not None else False
        child_match = any(child.apply_filter(lowered) for child in self.child_sections.values())
        has_match = local_match or child_match or not lowered
        self.setVisible(has_match)
        self.content.setVisible(has_match and (self.toggle_button.isChecked() or self._search_active))
        self.toggle_button.setArrowType(Qt.DownArrow if self.content.isVisible() else Qt.RightArrow)
        return has_match


class ComponentPalette(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.sections: dict[str, ComponentPaletteSection] = {}
        for index, node in enumerate(PALETTE_TREE):
            section = ComponentPaletteSection(node, expanded=index == 0)
            self.sections[node.title] = section
            layout.addWidget(section)
        layout.addStretch(1)

    def group_titles(self) -> list[str]:
        return list(self.sections.keys())

    def subgroup_titles(self, path: str) -> list[str]:
        section = self.section(path)
        return list(section.child_sections.keys()) if section is not None else []

    def group_items(self, path: str) -> list[str]:
        section = self.section(path)
        return section.leaf_items() if section is not None else []

    def section(self, path: str) -> ComponentPaletteSection | None:
        parts = [part for part in path.split("/") if part]
        if not parts:
            return None
        top = self.sections.get(parts[0])
        if top is None:
            return None
        return top.find_section(parts[1:])

    def apply_filter(self, query: str) -> None:
        for section in self.sections.values():
            section.apply_filter(query)

    def visible_group_items(self, path: str) -> list[str]:
        section = self.section(path)
        return section.visible_leaf_items() if section is not None else []


class ModelPanel(QWidget):
    def __init__(self, parent=None, *, saved_layouts_path: Path | None = None) -> None:
        super().__init__(parent)
        self._saved_layouts_path = saved_layouts_path
        self._refreshing_layout_lists = False
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel("Predefined Suspension Model")
        header.setStyleSheet("font-size: 18px; font-weight: 600;")
        subtitle = QLabel(
            "Start with an empty workspace, then open a built-in or saved layout explicitly. "
            "The component palette remains organized by reusable engineering families."
        )
        subtitle.setWordWrap(True)
        layout.addWidget(header)
        layout.addWidget(subtitle)

        splitter = QSplitter(Qt.Horizontal)
        self.canvas = ModelCanvas()
        self.property_editor = PropertyEditor()

        sidebar = QWidget()
        sidebar.setMinimumWidth(440)
        sidebar.setMaximumWidth(440)
        self.sidebar = sidebar
        sidebar_layout = QVBoxLayout(sidebar)
        workflow_box = QFrame()
        workflow_box.setFrameShape(QFrame.StyledPanel)
        workflow_layout = QVBoxLayout(workflow_box)
        workflow_layout.addWidget(QLabel("Current Workflow"))
        workflow_layout.addWidget(QLabel("Open a layout, tune parameters, pick I/O, then run the simulation."))

        layouts_group = QGroupBox("Workspace Layouts")
        layouts_layout = QVBoxLayout(layouts_group)
        layouts_layout.addWidget(QLabel("Default Layouts"))
        self.default_layouts_list = LayoutLibraryList()
        layouts_layout.addWidget(self.default_layouts_list)
        layouts_layout.addWidget(QLabel("Saved Layouts"))
        self.saved_layouts_list = LayoutLibraryList(editable_items=True)
        layouts_layout.addWidget(self.saved_layouts_list)
        self.new_workspace_button = QPushButton("New Workspace")
        self.save_layout_button = QPushButton("Save Layout")
        layouts_layout.addWidget(self.new_workspace_button)
        layouts_layout.addWidget(self.save_layout_button)

        library_group = QGroupBox("Component Palette")
        library_layout = QVBoxLayout(library_group)
        self.palette = ComponentPalette()
        self.palette_search = QLineEdit()
        self.palette_search.setPlaceholderText("Search components...")
        self.library_sections = self.palette.sections
        first_section = next(iter(self.library_sections.values()))
        self.library = first_section.library or next(iter(first_section.child_sections.values())).library
        palette_scroll = QScrollArea()
        palette_scroll.setWidgetResizable(True)
        palette_scroll.setFrameShape(QFrame.NoFrame)
        palette_scroll.setWidget(self.palette)
        self.palette_scroll = palette_scroll
        library_layout.addWidget(self.palette_search)
        library_layout.addWidget(palette_scroll)
        sidebar_layout.addWidget(workflow_box)
        sidebar_layout.addWidget(layouts_group)
        sidebar_layout.addWidget(library_group, 1)
        sidebar_layout.addWidget(self.property_editor)

        splitter.addWidget(sidebar)
        splitter.addWidget(self.canvas)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        layout.addWidget(splitter, 1)

        self.canvas.component_selected.connect(self.property_editor.set_component)
        self.default_layouts: list[WorkspaceLayout] = list(DEFAULT_LAYOUTS)
        self.saved_layouts: list[WorkspaceLayout] = self._load_saved_layouts()
        self._refresh_layout_lists()
        self.default_layouts_list.itemDoubleClicked.connect(self._open_default_layout_item)
        self.saved_layouts_list.itemDoubleClicked.connect(self._open_saved_layout_item)
        self.saved_layouts_list.itemChanged.connect(self._saved_layout_item_changed)
        self.saved_layouts_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.saved_layouts_list.customContextMenuRequested.connect(self._open_saved_layout_context_menu)
        self.new_workspace_button.clicked.connect(self.new_workspace)
        self.save_layout_button.clicked.connect(self.prompt_save_layout)
        self.palette_search.textChanged.connect(self.palette.apply_filter)

    def load_default_model(self) -> None:
        self.load_layout_by_id("default_quarter_car")

    def new_workspace(self) -> None:
        self.canvas.clear_workspace()

    def set_saved_layouts(self, layouts: list[WorkspaceLayout]) -> None:
        self.saved_layouts = list(layouts)
        self._refresh_layout_lists()
        self._persist_saved_layouts()

    def save_current_layout(self, name: str) -> WorkspaceLayout:
        trimmed_name = name.strip()
        if not trimmed_name:
            raise ValueError("Layout name must not be empty.")
        existing = next((layout for layout in self.saved_layouts if layout.name == trimmed_name), None)
        timestamp = datetime.now().isoformat(timespec="seconds")
        layout = WorkspaceLayout(
            id=existing.id if existing is not None else f"user_{len(self.saved_layouts) + 1}",
            name=trimmed_name,
            source_type="user",
            payload=self.canvas.snapshot_workspace(),
            created_at=existing.created_at if existing is not None else timestamp,
            updated_at=timestamp,
        )
        if existing is not None:
            index = self.saved_layouts.index(existing)
            self.saved_layouts[index] = layout
        else:
            self.saved_layouts.append(layout)
        self._refresh_layout_lists()
        self._persist_saved_layouts()
        return layout

    def prompt_save_layout(self) -> WorkspaceLayout | None:
        name, accepted = QInputDialog.getText(self, "Save Layout", "Layout name:")
        if not accepted:
            return None
        trimmed_name = name.strip()
        if not trimmed_name:
            QMessageBox.warning(self, "Save Layout", "Layout name cannot be empty.")
            return None
        existing = next((layout for layout in self.saved_layouts if layout.name == trimmed_name), None)
        if existing is not None:
            overwrite = QMessageBox.question(
                self,
                "Overwrite Layout",
                f'A saved layout named "{trimmed_name}" already exists. Overwrite it?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if overwrite != QMessageBox.Yes:
                return None
        return self.save_current_layout(trimmed_name)

    def rename_saved_layout(self, layout_id: str, new_name: str) -> WorkspaceLayout:
        layout = self._saved_layout_by_id(layout_id)
        if layout is None:
            raise ValueError("Saved layout could not be found.")
        trimmed_name = new_name.strip()
        if not trimmed_name:
            raise ValueError("Layout name must not be empty.")
        if trimmed_name == layout.name:
            return layout
        duplicate = next(
            (candidate for candidate in self.saved_layouts if candidate.name == trimmed_name and candidate.id != layout_id),
            None,
        )
        if duplicate is not None:
            raise ValueError("A saved layout with this name already exists.")
        updated = WorkspaceLayout(
            id=layout.id,
            name=trimmed_name,
            source_type=layout.source_type,
            payload=layout.payload,
            created_at=layout.created_at,
            updated_at=datetime.now().isoformat(timespec="seconds"),
        )
        index = self.saved_layouts.index(layout)
        self.saved_layouts[index] = updated
        self._refresh_layout_lists()
        self._persist_saved_layouts()
        return updated

    def prompt_rename_saved_layout(self, layout_id: str) -> WorkspaceLayout | None:
        layout = self._saved_layout_by_id(layout_id)
        if layout is None:
            return None
        name, accepted = QInputDialog.getText(self, "Rename Layout", "New layout name:", text=layout.name)
        if not accepted:
            return None
        trimmed_name = name.strip()
        if not trimmed_name:
            QMessageBox.warning(self, "Rename Layout", "Layout name cannot be empty.")
            return None
        duplicate = next(
            (candidate for candidate in self.saved_layouts if candidate.name == trimmed_name and candidate.id != layout_id),
            None,
        )
        if duplicate is not None:
            QMessageBox.warning(self, "Rename Layout", f'A saved layout named "{trimmed_name}" already exists.')
            return None
        return self.rename_saved_layout(layout_id, trimmed_name)

    def delete_saved_layout(self, layout_id: str) -> bool:
        layout = self._saved_layout_by_id(layout_id)
        if layout is None:
            return False
        self.saved_layouts.remove(layout)
        self._refresh_layout_lists()
        self._persist_saved_layouts()
        return True

    def prompt_delete_saved_layout(self, layout_id: str) -> bool:
        layout = self._saved_layout_by_id(layout_id)
        if layout is None:
            return False
        confirmed = QMessageBox.question(
            self,
            "Delete Layout",
            f'Delete saved layout "{layout.name}"?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirmed != QMessageBox.Yes:
            return False
        return self.delete_saved_layout(layout_id)

    def load_layout_by_id(self, layout_id: str) -> None:
        layout = self._layout_by_id(layout_id)
        if layout is None:
            return
        if layout.payload.get("template_id"):
            self.canvas.clear_workspace()
            self.canvas.load_template_layout(str(layout.payload["template_id"]))
            return
        self.canvas.load_workspace_snapshot(layout.payload)

    def layout_section_titles(self) -> list[str]:
        return ["Default Layouts", "Saved Layouts"]

    def default_layout_titles(self) -> list[str]:
        return [layout.name for layout in self.default_layouts]

    def saved_layout_titles(self) -> list[str]:
        return [layout.name for layout in self.saved_layouts]

    def saved_layout_action_titles(self, layout_id: str) -> list[str]:
        return ["Rename", "Delete"] if self._saved_layout_by_id(layout_id) is not None else []

    def default_layout_action_titles(self, layout_id: str) -> list[str]:
        return []

    def _refresh_layout_lists(self) -> None:
        self._refreshing_layout_lists = True
        self.default_layouts_list.populate(self.default_layouts)
        self.saved_layouts_list.populate(self.saved_layouts)
        self._refreshing_layout_lists = False

    def _layout_by_id(self, layout_id: str) -> WorkspaceLayout | None:
        for layout in [*self.default_layouts, *self.saved_layouts]:
            if layout.id == layout_id:
                return layout
        return None

    def _saved_layout_by_id(self, layout_id: str) -> WorkspaceLayout | None:
        for layout in self.saved_layouts:
            if layout.id == layout_id:
                return layout
        return None

    def _open_default_layout_item(self, item: QListWidgetItem) -> None:
        self.load_layout_by_id(str(item.data(Qt.UserRole)))

    def _open_saved_layout_item(self, item: QListWidgetItem) -> None:
        self.saved_layouts_list.cancel_pending_rename()
        self.load_layout_by_id(str(item.data(Qt.UserRole)))

    def _open_saved_layout_context_menu(self, position) -> None:
        item = self.saved_layouts_list.itemAt(position)
        if item is None:
            return
        layout_id = str(item.data(Qt.UserRole))
        if self._saved_layout_by_id(layout_id) is None:
            return
        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        chosen = menu.exec(self.saved_layouts_list.viewport().mapToGlobal(position))
        if chosen == rename_action:
            self.prompt_rename_saved_layout(layout_id)
        elif chosen == delete_action:
            self.prompt_delete_saved_layout(layout_id)

    def _saved_layout_item_changed(self, item: QListWidgetItem) -> None:
        if self._refreshing_layout_lists:
            return
        layout_id = str(item.data(Qt.UserRole))
        existing = self._saved_layout_by_id(layout_id)
        if existing is None:
            return
        try:
            self.rename_saved_layout(layout_id, item.text())
        except ValueError as exc:
            self._refresh_layout_lists()
            QMessageBox.warning(self, "Rename Layout", str(exc))

    def _load_saved_layouts(self) -> list[WorkspaceLayout]:
        if self._saved_layouts_path is None or not self._saved_layouts_path.exists():
            return []
        try:
            payload = json.loads(self._saved_layouts_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        layouts: list[WorkspaceLayout] = []
        if not isinstance(payload, list):
            return layouts
        for raw_layout in payload:
            if not isinstance(raw_layout, dict):
                continue
            try:
                layout = WorkspaceLayout(
                    id=str(raw_layout["id"]),
                    name=str(raw_layout["name"]),
                    source_type="user",
                    payload=dict(raw_layout["payload"]),
                    created_at=str(raw_layout.get("created_at", "")),
                    updated_at=str(raw_layout.get("updated_at", "")),
                )
            except (KeyError, TypeError, ValueError):
                continue
            layouts.append(layout)
        return layouts

    def _persist_saved_layouts(self) -> None:
        if self._saved_layouts_path is None:
            return
        self._saved_layouts_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "id": layout.id,
                "name": layout.name,
                "source_type": "user",
                "payload": layout.payload,
                "created_at": layout.created_at,
                "updated_at": layout.updated_at,
            }
            for layout in self.saved_layouts
        ]
        self._saved_layouts_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _palette_icon_for_display_name(display_name: str) -> QIcon:
    spec = component_spec_for_display_name(display_name)
    if spec.svg_symbol is None:
        return QIcon()
    resolved = Path(__file__).resolve().parents[3] / spec.svg_symbol.asset_path
    if not resolved.exists():
        return QIcon()
    return QIcon(str(resolved))
