"""SystemControllingView — Faz UI-4c.

Composition view for the "System Controlling" module.

Layout:
  ┌───────────────┬─────────────────────────┬──────────────┐
  │  Collapsible   │  SimulationResultsPanel  │  Collapsible  │
  │  Sidebar       │    Time | Step           │  Sidebar      │
  │  "Config"      │    Bode | Pole-Zero      │  "Equations"  │
  │                │                           │               │
  │  Controller    │  [Run Simulation]         │  Equations    │
  │  I/O Selection │                           │  (read-only)  │
  │  Sim Settings  │                           │               │
  └───────────────┴─────────────────────────┴──────────────┘

Signals:
  - run_button.clicked → parent wires to CompileAnalyzeService
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QWidget,
)

from src.features.ControllerDesignModule.panels.controller_tuning_panel import ControllerTuningPanel
from src.features.ControllerDesignModule.panels.model_equations_panel import ModelEquationsPanel
from src.features.ControllerDesignModule.panels.simulation_results_panel import SimulationResultsPanel
from src.shared.widgets.collapsible_sidebar import CollapsibleSidebar


class SystemControllingView(QWidget):
    """System Controlling module — right half of the application.

    Composes:
      - ControllerTuningPanel in CollapsibleSidebar (left, expanded)
      - SimulationResultsPanel (center)
      - ModelEquationsPanel in CollapsibleSidebar (right, collapsed)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # --- Configuration sidebar (left, expanded by default) ---
        self.controller_panel = ControllerTuningPanel()
        self.config_sidebar = CollapsibleSidebar(
            "Configuration",
            self.controller_panel,
            side="left",
            expanded=True,
            expanded_width=320,
        )

        # --- Results panel (center) ---
        self.results_panel = SimulationResultsPanel()

        # --- Equations sidebar (right, collapsed by default) ---
        self.equations_panel = ModelEquationsPanel()
        self.equations_sidebar = CollapsibleSidebar(
            "Model Equations",
            self.equations_panel,
            side="right",
            expanded=False,
            expanded_width=300,
        )

        # --- Main layout ---
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.config_sidebar)
        layout.addWidget(self.results_panel, 1)
        layout.addWidget(self.equations_sidebar)

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def run_button(self):
        """Direct access to the Run Simulation button for signal wiring."""
        return self.results_panel.run_button

    def show_empty_state(self, message: str = "") -> None:
        """Clear all results and equations."""
        self.results_panel.show_empty_state(message)
        self.equations_panel.show_empty_state(message)
