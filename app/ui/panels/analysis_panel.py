from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from app.ui.widgets.plot_widget import MplCanvas


class AnalysisPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel("Results and Analysis")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        subtitle = QLabel("Time response, step response, bode, and pole-zero views are shown together.")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

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
        self._plot_states = {"live": False, "step": False, "bode": False, "pole_zero": False}
        self._series_snapshot = {
            "live": {"count": 0, "labels": [], "colors": []},
            "step": {"count": 0, "labels": [], "colors": []},
            "bode": {"count": 0, "labels": [], "colors": []},
            "pole_zero": {"count": 0, "labels": [], "colors": []},
        }
        self.show_empty_state()

    def _wrap_plot(self, heading: str, canvas: MplCanvas) -> QWidget:
        container = QWidget()
        inner = QVBoxLayout(container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(4)
        label = QLabel(heading)
        label.setStyleSheet("font-size: 14px; font-weight: 600;")
        inner.addWidget(label)
        inner.addWidget(canvas, 1)
        return container

    def show_empty_state(self, message: str = "No simulation run yet.") -> None:
        self._draw_empty_axes(self.live_axes, title="Time Response", xlabel="Time [s]", message=message)
        self._draw_empty_axes(self.step_axes, title="Step Response", xlabel="Time [s]", message=message)
        self._draw_empty_axes(self.bode_mag_axes, title="Bode Magnitude", ylabel="Magnitude [dB]", message=message)
        self._draw_empty_axes(self.bode_phase_axes, title="Bode Phase", xlabel="Frequency [rad/s]", ylabel="Phase [deg]")
        self._draw_empty_axes(self.pole_zero_axes, title="Pole-Zero", xlabel="Real axis", ylabel="Imaginary axis", message=message)
        self.live_canvas.draw_idle()
        self.step_canvas.draw_idle()
        self.bode_canvas.draw_idle()
        self.pz_canvas.draw_idle()
        self._plot_states = {key: False for key in self._plot_states}
        self._series_snapshot = {
            "live": {"count": 0, "labels": [], "colors": []},
            "step": {"count": 0, "labels": [], "colors": []},
            "bode": {"count": 0, "labels": [], "colors": []},
            "pole_zero": {"count": 0, "labels": [], "colors": []},
        }

    def _draw_empty_axes(self, axes, *, title: str, xlabel: str = "", ylabel: str = "", message: str | None = None) -> None:
        axes.clear()
        axes.set_title(title)
        if xlabel:
            axes.set_xlabel(xlabel)
        if ylabel:
            axes.set_ylabel(ylabel)
        axes.grid(True, alpha=0.15)
        if message:
            axes.text(0.5, 0.5, message, ha="center", va="center", transform=axes.transAxes, color="#6b7280")

    def plot_state_snapshot(self) -> dict[str, bool]:
        return dict(self._plot_states)

    def series_snapshot(self) -> dict[str, dict[str, object]]:
        return {
            name: {"count": payload["count"], "labels": list(payload["labels"]), "colors": list(payload["colors"])}
            for name, payload in self._series_snapshot.items()
        }

    def update_live_plot(self, data: dict[str, object], *, selected_outputs: list[tuple[str, str, str]]) -> None:
        self.live_axes.clear()
        self.live_axes.set_title("Live Outputs")
        time = data.get("time", np.asarray([], dtype=float))
        series_data = data.get("series", {})
        labels: list[str] = []
        colors: list[str] = []
        for signal_id, label, color in selected_outputs:
            series = series_data.get(signal_id)
            if series is None:
                continue
            self.live_axes.plot(time, series, label=label, color=color, linewidth=2.0)
            labels.append(label)
            colors.append(color)
        self.live_axes.set_xlabel("Time [s]")
        self.live_axes.grid(True, alpha=0.25)
        if labels:
            self.live_axes.legend(loc="upper right", fontsize=8)
        self.live_canvas.draw_idle()
        self._plot_states["live"] = bool(getattr(time, "size", 0) and labels)
        self._series_snapshot["live"] = {"count": len(labels), "labels": labels, "colors": colors}

    def update_step_response(self, data: dict[str, object], *, selected_outputs: list[tuple[str, str, str]], input_label: str) -> None:
        self.step_axes.clear()
        self.step_axes.set_title(f"{input_label} -> Selected outputs")
        time = data.get("time", np.asarray([], dtype=float))
        responses = data.get("responses", {})
        labels: list[str] = []
        colors: list[str] = []
        for signal_id, label, color in selected_outputs:
            response = responses.get(signal_id)
            if response is None:
                continue
            self.step_axes.plot(time, response, color=color, linewidth=2.0, label=label)
            labels.append(label)
            colors.append(color)
        self.step_axes.set_xlabel("Time [s]")
        self.step_axes.grid(True, alpha=0.25)
        if labels:
            self.step_axes.legend(loc="upper right", fontsize=8)
        self.step_canvas.draw_idle()
        self._plot_states["step"] = bool(getattr(time, "size", 0) and labels)
        self._series_snapshot["step"] = {"count": len(labels), "labels": labels, "colors": colors}

    def update_bode(self, data: dict[str, object], *, selected_outputs: list[tuple[str, str, str]], input_label: str) -> None:
        self.bode_mag_axes.clear()
        self.bode_phase_axes.clear()
        self.bode_mag_axes.set_title(f"{input_label} -> Selected outputs")
        frequency = data.get("frequency", np.asarray([], dtype=float))
        series = data.get("series", {})
        labels: list[str] = []
        colors: list[str] = []
        for signal_id, label, color in selected_outputs:
            payload = series.get(signal_id)
            if payload is None:
                continue
            self.bode_mag_axes.semilogx(frequency, payload["magnitude"], color=color, label=label)
            self.bode_phase_axes.semilogx(frequency, payload["phase"], color=color, label=label)
            labels.append(label)
            colors.append(color)
        self.bode_mag_axes.set_ylabel("Magnitude [dB]")
        self.bode_phase_axes.set_ylabel("Phase [deg]")
        self.bode_phase_axes.set_xlabel("Frequency [rad/s]")
        self.bode_mag_axes.grid(True, alpha=0.25)
        self.bode_phase_axes.grid(True, alpha=0.25)
        if labels:
            self.bode_mag_axes.legend(loc="best", fontsize=8)
        self.bode_canvas.draw_idle()
        self._plot_states["bode"] = bool(getattr(frequency, "size", 0) and labels)
        self._series_snapshot["bode"] = {"count": len(labels), "labels": labels, "colors": colors}

    def update_pole_zero(self, data: dict[str, object], *, selected_outputs: list[tuple[str, str, str]], input_label: str) -> None:
        self.pole_zero_axes.clear()
        self.pole_zero_axes.set_title(f"{input_label} -> Selected outputs")
        series = data.get("series", {})
        labels: list[str] = []
        colors: list[str] = []
        poles_drawn = False
        for signal_id, label, color in selected_outputs:
            payload = series.get(signal_id)
            if payload is None:
                continue
            poles = payload["poles"]
            zeros = payload["zeros"]
            if poles.size and not poles_drawn:
                self.pole_zero_axes.scatter(np.real(poles), np.imag(poles), marker="x", color="#d32f2f", s=64, label="Poles")
                poles_drawn = True
            if zeros.size:
                self.pole_zero_axes.scatter(np.real(zeros), np.imag(zeros), marker="o", facecolors="none", edgecolors=color, s=64, label=f"{label} zeros")
            labels.append(label)
            colors.append(color)
        self.pole_zero_axes.axhline(0.0, color="#777", linewidth=0.8)
        self.pole_zero_axes.axvline(0.0, color="#777", linewidth=0.8)
        self.pole_zero_axes.set_xlabel("Real axis")
        self.pole_zero_axes.set_ylabel("Imaginary axis")
        self.pole_zero_axes.grid(True, alpha=0.25)
        if labels or poles_drawn:
            self.pole_zero_axes.legend(loc="best", fontsize=8)
        self.pz_canvas.draw_idle()
        self._plot_states["pole_zero"] = bool(labels or poles_drawn)
        self._series_snapshot["pole_zero"] = {"count": len(labels), "labels": labels, "colors": colors}
