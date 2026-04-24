#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import deque

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ModuleNotFoundError:
    FigureCanvasQTAgg = None
    Figure = None
    MATPLOTLIB_AVAILABLE = False


class SignalPlotWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumHeight(240)
        self.setMinimumWidth(360)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(
            """
            QFrame {
                background-color: #e9eef3;
                border: 1px solid #9aa7b2;
                border-radius: 6px;
            }
            QLabel {
                color: #2f3b46;
                background-color: transparent;
            }
            """
        )

        self.max_points = 1200
        self.time_history = deque(maxlen=self.max_points)
        self.signal_histories = {
            "primary_signal": deque(maxlen=self.max_points),
            "secondary_signal": deque(maxlen=self.max_points),
            "u_control": deque(maxlen=self.max_points),
            "u_total": deque(maxlen=self.max_points),
        }
        self.signal_styles = {
            "primary_signal": {"label": "Primary Signal", "color": "#1565c0", "linewidth": 2.0},
            "secondary_signal": {"label": "Secondary Signal", "color": "#2e7d32", "linewidth": 1.8},
            "u_control": {"label": "u_control(t)", "color": "#ef6c00", "linewidth": 1.6},
            "u_total": {"label": "u_total(t)", "color": "#6a1b9a", "linewidth": 1.6},
        }
        self.active_signals = ["primary_signal"]
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(8)

        if MATPLOTLIB_AVAILABLE:
            self.figure = Figure(figsize=(5.2, 4.0), tight_layout=True)
            self.canvas = FigureCanvasQTAgg(self.figure)
            self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.axes = self.figure.add_subplot(111)
            self.layout.addWidget(self.canvas, 1)
            self.update_plot()
        else:
            self.figure = None
            self.canvas = None
            self.axes = None
            self._build_missing_dependency_panel()

    def _build_missing_dependency_panel(self):
        title = QLabel("Grid Alani 4 - Live Signal Plot")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        message = QLabel(
            "Bu panel icin matplotlib gerekli, ancak mevcut ortamda kurulu degil.\n\n"
            "Kurulum sonrasi canlı zaman cevabi grafigi burada otomatik olarak gosterilecek.\n"
            "Ornek kurulum: pip install matplotlib"
        )
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignCenter)
        self.layout.addStretch()
        self.layout.addWidget(title)
        self.layout.addWidget(message)
        self.layout.addStretch()

    def set_signals(self, signals):
        valid_signals = [name for name in signals if name in self.signal_histories]
        self.active_signals = valid_signals or ["primary_signal"]
        self.update_plot()

    def reset_plot(self):
        self.time_history.clear()
        for history in self.signal_histories.values():
            history.clear()
        self.update_plot()

    def append_data(self, time_value, signal_values):
        self.time_history.append(float(time_value))
        for key, history in self.signal_histories.items():
            history.append(float(signal_values.get(key, 0.0)))
        self.update_plot()

    def append_data_from_state(self, state):
        labels = state.get("signal_labels", {})
        for key, label in labels.items():
            if key in self.signal_styles:
                self.signal_styles[key]["label"] = label
        signal_values = {
            "primary_signal": state.get("primary_signal", state.get("phi_deg", 0.0)),
            "secondary_signal": state.get("secondary_signal", state.get("s", 0.0)),
            "u_control": state.get("u_control", 0.0),
            "u_total": state.get("u_total", 0.0),
        }
        self.append_data(state.get("time", 0.0), signal_values)

    def update_plot(self):
        if not MATPLOTLIB_AVAILABLE:
            return
        self.axes.clear()
        self.axes.set_facecolor("#fbfdff")
        self.axes.set_title("Live Step Response")
        self.axes.set_xlabel("Time (s)")
        self.axes.set_ylabel("Signal")
        self.axes.grid(True, linestyle="--", linewidth=0.6, alpha=0.6)

        if not self.time_history:
            self.axes.set_xlim(0.0, 10.0)
            self.axes.set_ylim(-1.0, 1.0)
            self.axes.text(0.5, 0.5, "Play ile simulasyonu baslatin", transform=self.axes.transAxes, ha="center", va="center", color="#607d8b", fontsize=11)
            self.canvas.draw_idle()
            return

        times = list(self.time_history)
        plotted_values = []
        handles = []
        for signal_name in self.active_signals:
            values = list(self.signal_histories[signal_name])
            style = self.signal_styles[signal_name]
            line, = self.axes.plot(times, values, color=style["color"], linewidth=style["linewidth"], label=style["label"])
            handles.append(line)
            plotted_values.extend(values)

        x_max = max(times[-1], 5.0)
        x_min = max(0.0, x_max - 12.0)
        self.axes.set_xlim(x_min, x_max + 0.25)
        y_min = min(plotted_values)
        y_max = max(plotted_values)
        if abs(y_max - y_min) < 1e-6:
            y_min -= 1.0
            y_max += 1.0
        padding = 0.15 * max(y_max - y_min, 1.0)
        self.axes.set_ylim(y_min - padding, y_max + padding)
        self.axes.legend(handles=handles, loc="best")
        self.canvas.draw_idle()


class SignalPanel(SignalPlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
