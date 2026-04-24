from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.ui.widgets.plot_widget import MplCanvas


class OutputPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("Live Outputs and Step Response")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.canvas = MplCanvas(height=5.8)
        self.live_axes = self.canvas.figure.add_subplot(211)
        self.step_axes = self.canvas.figure.add_subplot(212)
        layout.addWidget(title)
        layout.addWidget(self.canvas, 1)

    def update_live_plot(self, data: dict[str, np.ndarray]) -> None:
        self.live_axes.clear()
        self.live_axes.set_title("Live Outputs")
        self.live_axes.plot(data["time"], data["body_displacement"], label="Body disp.")
        self.live_axes.plot(data["time"], data["wheel_displacement"], label="Wheel disp.")
        self.live_axes.plot(data["time"], data["suspension_deflection"], label="Susp. deflection")
        self.live_axes.plot(data["time"], data["body_acceleration"], label="Body accel.")
        self.live_axes.set_xlabel("Time [s]")
        self.live_axes.grid(True, alpha=0.25)
        self.live_axes.legend(loc="upper right")
        self.canvas.draw_idle()

    def update_step_response(self, data: dict[str, np.ndarray]) -> None:
        self.step_axes.clear()
        self.step_axes.set_title("Step Response")
        self.step_axes.plot(data["time"], data["body_displacement"], label="Body")
        self.step_axes.plot(data["time"], data["wheel_displacement"], label="Wheel")
        self.step_axes.set_xlabel("Time [s]")
        self.step_axes.grid(True, alpha=0.25)
        self.step_axes.legend(loc="upper right")
        self.canvas.draw_idle()

