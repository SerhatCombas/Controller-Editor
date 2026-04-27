"""ComponentInspectorPanel — Faz UI-2b (v3).

Sits below the canvas in the System Modeling area.
Full-width 4-column grid layout matching the reference design:

  ┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
  │ Selected │ Capacitor│ Comp. ID │ xxx/yyy  │ Domain   │ Electr.  │ Category │ Compon.  │
  │ Boundary │ Free     │ Motion   │ -        │ Direct.  │ No       │ Source   │ No       │
  │ Src Type │ -        │ Rotation │ 0        │ Ports    │ 2        │ Status   │ Selected │
  ├──────────┴──────────┼──────────┴──────────┴──────────┴──────────┴──────────┴──────────┤
  │ Capacitance [F]     │  0,000   :                                                      │
  └─────────────────────┴─────────────────────────────────────────────────────────────────┘

Parameters are stored on CanvasVisualComponent.user_params and
passed to CanvasCompiler at compile time.

Usage:
    inspector = ComponentInspectorPanel()
    canvas.component_selected.connect(inspector.show_component)
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)


# Parameter metadata: type_key → list of (param_key, display_label, unit, default, min, max, step)
_PARAM_SPECS: dict[str, list[tuple[str, str, str, float, float, float, float]]] = {
    "mass": [
        ("m", "Mass", "kg", 1.0, 0.001, 100000.0, 0.1),
    ],
    "translational_spring": [
        ("k", "Stiffness", "N/m", 1000.0, 0.001, 1e8, 10.0),
    ],
    "translational_damper": [
        ("d", "Damping", "N·s/m", 100.0, 0.001, 1e8, 1.0),
    ],
    "resistor": [
        ("R", "Resistance", "Ω", 1000.0, 0.001, 1e9, 10.0),
    ],
    "capacitor": [
        ("C", "Capacitance", "F", 1e-6, 1e-12, 1.0, 1e-7),
    ],
    "inductor": [
        ("L", "Inductance", "H", 1e-3, 1e-9, 1000.0, 1e-4),
    ],
    "dc_voltage_source": [
        ("V", "Voltage", "V", 12.0, -1e6, 1e6, 0.1),
    ],
    "dc_current_source": [
        ("I", "Current", "A", 1.0, -1e6, 1e6, 0.01),
    ],
    "ideal_force_source": [
        ("F", "Force", "N", 1.0, -1e8, 1e8, 0.1),
    ],
}

# Label style: bold white
_LBL_STYLE = "font-weight: 700; font-size: 12px; color: #e0e4e8;"
# Value style: regular white
_VAL_STYLE = "font-weight: 400; font-size: 12px; color: #c9d0d5;"


class ComponentInspectorPanel(QFrame):
    """Component inspector: 4-column info grid + editable parameters.

    Signals
    -------
    parameter_changed(str, str, float)
        Emitted as (component_id, param_key, new_value) when the user
        edits a parameter spinbox.
    """

    parameter_changed = Signal(str, str, float)

    # Info fields: (display_label, detail_key) — 4 per row
    _INFO_FIELDS = [
        # Row 0
        ("Selected",    "name"),
        ("Component ID", "component_id"),
        ("Domain",      "domain"),
        ("Category",    "visual_category"),
        # Row 1
        ("Boundary",    "boundary_role"),
        ("Motion",      "motion_profile"),
        ("Directional", "directional"),
        ("Source",      "source_component"),
        # Row 2
        ("Source Type", "source_type"),
        ("Rotation",    "rotation_degrees"),
        ("Ports",       "ports"),
        ("Status",      "status_text"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ComponentInspectorPanel")
        self.setFrameShape(QFrame.StyledPanel)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(80)
        self.setMaximumHeight(200)

        self._current_component_id: str = ""
        self._current_component_ref = None
        self._param_spinboxes: dict[str, QDoubleSpinBox] = {}

        # --- Single grid layout: 8 columns (4 label-value pairs) ---
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(12, 8, 12, 8)
        self._grid.setHorizontalSpacing(10)
        self._grid.setVerticalSpacing(6)

        # Set column stretches so values get more space than labels
        for col in range(4):
            self._grid.setColumnStretch(col * 2, 0)      # label: no stretch
            self._grid.setColumnStretch(col * 2 + 1, 1)  # value: stretch

        # Build info field labels and value placeholders
        self._info_labels: dict[str, QLabel] = {}
        for i, (display_label, key) in enumerate(self._INFO_FIELDS):
            row = i // 4
            col_pair = i % 4

            lbl = QLabel(display_label)
            lbl.setStyleSheet(_LBL_STYLE)

            val = QLabel("-")
            val.setStyleSheet(_VAL_STYLE)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)

            self._grid.addWidget(lbl, row, col_pair * 2)
            self._grid.addWidget(val, row, col_pair * 2 + 1)
            self._info_labels[key] = val

        # Parameter row — starts at row 3 (below 3 info rows)
        # Will be populated dynamically in _rebuild_parameters
        self._param_row = 3
        self._param_widgets: list[QWidget] = []

        # Start hidden
        self.hide()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_component(self, details: dict[str, object]) -> None:
        """Update inspector with component details."""
        name = str(details.get("name", ""))
        if not name or name == "No selection":
            self.hide()
            return

        self._current_component_id = str(details.get("component_id", ""))
        self._current_component_ref = details.get("_component_ref")

        # Update info fields
        for _display_label, key in self._INFO_FIELDS:
            label_widget = self._info_labels.get(key)
            if label_widget is None:
                continue
            raw = details.get(key, "-")
            label_widget.setText(str(raw) if raw is not None else "-")

        # Parameters
        self._rebuild_parameters(details)

        self.show()

    def clear_selection(self) -> None:
        self._current_component_id = ""
        self._current_component_ref = None
        self.hide()

    # ------------------------------------------------------------------
    # Parameter editing
    # ------------------------------------------------------------------

    def _rebuild_parameters(self, details: dict[str, object]) -> None:
        """Rebuild parameter spinboxes for the selected component."""
        # Clear existing parameter widgets
        self._param_spinboxes.clear()
        for w in self._param_widgets:
            self._grid.removeWidget(w)
            w.deleteLater()
        self._param_widgets.clear()

        type_key = str(details.get("type_key", ""))
        param_specs = _PARAM_SPECS.get(type_key, [])
        user_params = details.get("user_params", {}) or {}
        default_params = details.get("default_params", {}) or {}

        if not param_specs:
            return

        # Add each parameter as label + spinbox on the parameter row
        for i, (param_key, label, unit, default, pmin, pmax, step) in enumerate(param_specs):
            current_value = user_params.get(param_key,
                            default_params.get(param_key, default))

            row_label = QLabel(f"{label} [{unit}]")
            row_label.setStyleSheet(_LBL_STYLE)

            spinbox = QDoubleSpinBox()
            spinbox.setRange(pmin, pmax)
            spinbox.setSingleStep(step)
            spinbox.setDecimals(self._auto_decimals(current_value, step))
            spinbox.setValue(float(current_value))
            spinbox.setStyleSheet(
                "QDoubleSpinBox {"
                "  background: #2a2d30; color: #f5f7f8;"
                "  border: 1px solid #555a5e; border-radius: 3px;"
                "  min-height: 22px; min-width: 90px; padding: 1px 4px;"
                "  font-size: 12px;"
                "}"
            )

            pk = param_key
            spinbox.valueChanged.connect(
                lambda val, key=pk: self._on_param_changed(key, val)
            )

            col_offset = i * 2
            self._grid.addWidget(row_label, self._param_row, col_offset)
            self._grid.addWidget(spinbox, self._param_row, col_offset + 1)
            self._param_widgets.extend([row_label, spinbox])
            self._param_spinboxes[param_key] = spinbox

    def _on_param_changed(self, param_key: str, value: float) -> None:
        """Store parameter on the canvas component and emit signal."""
        if self._current_component_ref is not None:
            self._current_component_ref.user_params[param_key] = value
        self.parameter_changed.emit(self._current_component_id, param_key, value)

    @staticmethod
    def _auto_decimals(value: float, step: float) -> int:
        """Pick decimal count based on value magnitude."""
        ref = min(abs(value), abs(step)) if value != 0 else abs(step)
        if ref >= 1.0:
            return 1
        elif ref >= 0.01:
            return 3
        elif ref >= 0.0001:
            return 5
        elif ref >= 0.000001:
            return 7
        return 9
