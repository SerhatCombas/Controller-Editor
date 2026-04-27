"""SimulationResultsPanel — Faz UI-4a.

Central panel in the System Controlling module.
Contains the 2x2 plot grid (Time Response, Step Response, Bode, Pole-Zero)
and a "Run Simulation" button at the bottom.

Evolves from the existing AnalysisPanel — reuses MplCanvas but adds
the Run button and restructures the header.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.widgets.plot_widget import MplCanvas


class SimulationResultsPanel(QWidget):
    """2x2 plot grid with Run Simulation button.

    Attributes
    ----------
    run_button : QPushButton
        "Run Simulation" button — connect to CompileAnalyzeService.
    step_canvas, bode_canvas, pz_canvas, live_canvas : MplCanvas
        Matplotlib canvases for each plot.
    step_axes, bode_mag_axes, bode_phase_axes, pole_zero_axes, live_axes
        Matplotlib axes for direct plotting.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SimulationResultsPanel")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header
        header_label = QLabel("Results and Analysis")
        header_label.setStyleSheet("font-size: 15px; font-weight: 700;")
        layout.addWidget(header_label)

        # 2x2 plot grid
        grid = QGridLayout()
        grid.setSpacing(8)

        self.live_canvas = MplCanvas(height=4.2)
        self.live_axes = self.live_canvas.figure.add_subplot(111)

        self.step_canvas = MplCanvas(height=4.2)
        self.step_axes = self.step_canvas.figure.add_subplot(111)

        self.bode_canvas = MplCanvas(height=4.2)
        self.bode_mag_axes = self.bode_canvas.figure.add_subplot(211)
        self.bode_phase_axes = self.bode_canvas.figure.add_subplot(212)

        self.pz_canvas = MplCanvas(height=4.2)
        self.pole_zero_axes = self.pz_canvas.figure.add_subplot(111)

        grid.addWidget(self._wrap_plot("Time Response", self.live_canvas), 0, 0)
        grid.addWidget(self._wrap_plot("Step Response", self.step_canvas), 0, 1)
        grid.addWidget(self._wrap_plot("Bode", self.bode_canvas), 1, 0)
        grid.addWidget(self._wrap_plot("Pole-Zero", self.pz_canvas), 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

        layout.addLayout(grid, 1)

        # Run Simulation button
        self.run_button = QPushButton("Run Simulation")
        self.run_button.setObjectName("RunSimulationButton")
        self.run_button.setMinimumHeight(36)
        self.run_button.setStyleSheet(
            "QPushButton {"
            "  background: #2f6fb3; color: #f5f7f8;"
            "  font-weight: 600; font-size: 13px;"
            "  border: 1px solid #6aa5e8; border-radius: 4px;"
            "}"
            "QPushButton:hover { background: #3a7fc3; }"
            "QPushButton:pressed { background: #256099; }"
        )
        layout.addWidget(self.run_button)

        # Initial empty state
        self.show_empty_state()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _wrap_plot(self, heading: str, canvas: MplCanvas) -> QWidget:
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(2)
        label = QLabel(heading)
        label.setStyleSheet("font-size: 12px; font-weight: 600;")
        vbox.addWidget(label)
        vbox.addWidget(canvas, 1)
        return container

    def show_empty_state(self, message: str = "Run simulation to inspect response.") -> None:
        """Clear all plots and show placeholder text."""
        for ax_name, ax in [
            ("live", self.live_axes),
            ("step", self.step_axes),
            ("bode_mag", self.bode_mag_axes),
            ("bode_phase", self.bode_phase_axes),
            ("pz", self.pole_zero_axes),
        ]:
            ax.clear()
            ax.text(
                0.5, 0.5, message,
                ha="center", va="center",
                fontsize=10, color="#7f8992",
                transform=ax.transAxes,
            )
            ax.set_xticks([])
            ax.set_yticks([])

        self.live_canvas.draw()
        self.step_canvas.draw()
        self.bode_canvas.draw()
        self.pz_canvas.draw()
