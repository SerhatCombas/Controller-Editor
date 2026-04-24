#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ModuleNotFoundError:
    FigureCanvasQTAgg = None
    NavigationToolbar2QT = None
    Figure = None
    MATPLOTLIB_AVAILABLE = False


class RootLocusWidget(QFrame):
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

        self.current_config = None
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(8)

        if MATPLOTLIB_AVAILABLE:
            self.figure = Figure(figsize=(5.2, 4.0), tight_layout=True)
            self.canvas = FigureCanvasQTAgg(self.figure)
            self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.axes = self.figure.add_subplot(111)
            self.toolbar = NavigationToolbar2QT(self.canvas, self)
            self.enable_interaction_tools()
            self.layout.addWidget(self.toolbar)
            self.layout.addWidget(self.canvas, 1)
            self.update_plot()
        else:
            self.figure = None
            self.canvas = None
            self.axes = None
            self.toolbar = None
            self._build_missing_dependency_panel()

    def _tint_icon_black(self, icon):
        """Recolor matplotlib toolbar icons to solid black for dark-theme safety."""
        if icon.isNull():
            return icon

        tinted_icon = QIcon()
        icon_size = self.toolbar.iconSize()
        for size in [icon_size, icon.actualSize(icon_size)]:
            if not size.isValid() or size.isEmpty():
                continue
            pixmap = icon.pixmap(size)
            if pixmap.isNull():
                continue

            tinted = QPixmap(pixmap.size())
            tinted.fill(Qt.transparent)
            painter = QPainter(tinted)
            painter.drawPixmap(0, 0, pixmap)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(tinted.rect(), QColor("#000000"))
            painter.end()
            tinted_icon.addPixmap(tinted)

        return tinted_icon if not tinted_icon.isNull() else icon

    def enable_interaction_tools(self):
        """Keep matplotlib zoom/pan tools embedded inside the Qt panel with strong contrast.

        We force a light toolbar surface and recolor the action icons to black so the
        toolbar stays readable even under dark application themes.
        """
        if self.toolbar is None:
            return

        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.toolbar.setIconSize(self.toolbar.iconSize().scaled(20, 20, Qt.KeepAspectRatio))
        self.toolbar.setContentsMargins(6, 4, 6, 4)
        self.toolbar.setStyleSheet(
            """
            QToolBar {
                background-color: #f4f7fb;
                border: 1px solid #a9b8c6;
                border-radius: 6px;
                spacing: 6px;
                padding: 4px;
            }
            QToolBar QToolButton {
                background-color: #ffffff;
                color: #111111;
                border: 1px solid #b5c1cc;
                border-radius: 4px;
                padding: 4px;
                margin: 1px;
            }
            QToolBar QToolButton:hover {
                background-color: #dbe8f5;
                border: 1px solid #7f97ad;
            }
            QToolBar QToolButton:pressed,
            QToolBar QToolButton:checked {
                background-color: #c8dbef;
                border: 1px solid #5f7f99;
            }
            QToolBar QToolButton:disabled {
                background-color: #eef2f6;
                color: #7f8c96;
                border: 1px solid #c7d0d8;
            }
            QToolBar QToolButton::menu-indicator {
                image: none;
            }
            QToolTip {
                background-color: #fffef2;
                color: #111111;
                border: 1px solid #9aa7b2;
            }
            """
        )

        for action in self.toolbar.actions():
            action.setIcon(self._tint_icon_black(action.icon()))

    def _build_missing_dependency_panel(self):
        title = QLabel("Grid Alani 3 - Root Locus")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")

        message = QLabel(
            "Bu panel icin matplotlib gerekli, ancak mevcut ortamda kurulu degil.\n\n"
            "Kurulum sonrasi embedded Root Locus grafigi burada otomatik olarak gosterilecek.\n"
            "Ornek kurulum: pip install matplotlib"
        )
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignCenter)

        self.layout.addStretch()
        self.layout.addWidget(title)
        self.layout.addWidget(message)
        self.layout.addStretch()

    def current_open_loop_transfer_function(self, control_config=None):
        """Build the open-loop transfer function from the current PID selection.

        Assumed plant model for Grid Area 3 analysis:
            G(s) = 1 / (s * (s + 1) * (s + 2))
        Controller:
            C(s) = Kd*s + Kp + Ki/s
        """
        config = control_config or self.current_config or {}
        gains = config.get("gains", {})
        components = config.get("components", {})

        kp = gains.get("P", 0.0) if components.get("P", False) else 0.0
        ki = gains.get("I", 0.0) if components.get("I", False) else 0.0
        kd = gains.get("D", 0.0) if components.get("D", False) else 0.0

        controller_num = np.array([kd, kp, ki], dtype=float)
        controller_den = np.array([1.0, 0.0], dtype=float)

        while controller_num.size > 1 and np.isclose(controller_num[0], 0.0):
            controller_num = controller_num[1:]

        if np.allclose(controller_num, 0.0):
            controller_num = np.array([1e-6], dtype=float)
            controller_den = np.array([1.0], dtype=float)

        plant_num = np.array([1.0], dtype=float)
        plant_den = np.array([1.0, 3.0, 2.0, 0.0], dtype=float)

        open_loop_num = np.polymul(controller_num, plant_num)
        open_loop_den = np.polymul(controller_den, plant_den)
        return open_loop_num, open_loop_den

    def update_root_locus(self, system_config=None):
        self.update_plot(system_config)

    def compute_root_locus(self, numerator, denominator, gains=None):
        if gains is None:
            gains = np.concatenate(([0.0], np.logspace(-3, 3, 550)))

        branch_count = len(np.roots(denominator))
        branches = np.zeros((len(gains), branch_count), dtype=complex)
        previous_roots = None

        for index, gain in enumerate(gains):
            closed_loop_poly = self._poly_add(denominator, gain * numerator)
            roots = np.roots(closed_loop_poly)

            if previous_roots is None:
                roots = roots[np.argsort(roots.real)]
            else:
                roots = self._match_roots(previous_roots, roots)

            branches[index, :] = roots
            previous_roots = roots

        return gains, branches

    def _poly_add(self, first, second):
        length = max(len(first), len(second))
        first_padded = np.pad(first, (length - len(first), 0))
        second_padded = np.pad(second, (length - len(second), 0))
        return first_padded + second_padded

    def _match_roots(self, previous_roots, current_roots):
        matched = np.empty_like(current_roots)
        available = list(current_roots)

        for index, previous_root in enumerate(previous_roots):
            distances = [abs(previous_root - candidate) for candidate in available]
            closest_index = int(np.argmin(distances))
            matched[index] = available.pop(closest_index)

        return matched

    def update_plot(self, control_config=None):
        if control_config is not None:
            self.current_config = control_config

        if not MATPLOTLIB_AVAILABLE:
            return

        numerator, denominator = self.current_open_loop_transfer_function(control_config)
        poles = np.roots(denominator)
        zeros = np.roots(numerator) if len(numerator) > 1 else np.array([], dtype=complex)
        _, branches = self.compute_root_locus(numerator, denominator)
        zeta = (self.current_config or {}).get("analysis", {}).get("damping_ratio", 0.5)

        self.axes.clear()
        self.axes.set_facecolor("#fbfdff")

        branch_handle = None
        root2_handle = None
        for branch_index in range(branches.shape[1]):
            branch = branches[:, branch_index]
            if branch_index == 1:
                root2_handle, = self.axes.plot(
                    branch.real,
                    branch.imag,
                    color="purple",
                    linewidth=2.8,
                    label="Root 2",
                    zorder=3,
                )
                valid_points = branch[np.isfinite(branch.real) & np.isfinite(branch.imag)]
                if valid_points.size:
                    point = valid_points[-1]
                    self.axes.annotate(
                        f"Root 2 = ({point.real:.2f}, {point.imag:.2f})",
                        xy=(point.real, point.imag),
                        xytext=(10, 10),
                        textcoords="offset points",
                        color="purple",
                        fontsize=9,
                        bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "purple", "alpha": 0.9},
                    )
            else:
                handle, = self.axes.plot(
                    branch.real,
                    branch.imag,
                    color="#5b7c99",
                    linewidth=1.4,
                    alpha=0.92,
                    label="Root Locus" if branch_handle is None else None,
                    zorder=2,
                )
                if branch_handle is None:
                    branch_handle = handle

        poles_handle = None
        zeros_handle = None
        if poles.size:
            poles_handle = self.axes.scatter(
                poles.real,
                poles.imag,
                marker="x",
                color="red",
                s=76,
                linewidths=2.1,
                label="Poles",
                zorder=5,
            )
        if zeros.size:
            zeros_handle = self.axes.scatter(
                zeros.real,
                zeros.imag,
                marker="o",
                facecolors="none",
                edgecolors="blue",
                s=76,
                linewidths=2.1,
                label="Zeros",
                zorder=5,
            )

        limits = self._fit_axes(branches, poles, zeros)
        asymptote_handle = self.draw_asymptotes(poles, zeros, limits)
        damping_handle = self.draw_damping_line(zeta, limits)

        self.axes.axhline(0.0, color="#9aa7b2", linewidth=0.9)
        self.axes.axvline(0.0, color="#9aa7b2", linewidth=0.9)
        self.axes.grid(True, linestyle="--", linewidth=0.6, alpha=0.6)
        self.axes.set_xlabel("Real Axis")
        self.axes.set_ylabel("Imaginary Axis")
        self.axes.set_title("Embedded Root Locus Analysis")

        handles = [
            handle for handle in [poles_handle, zeros_handle, branch_handle, root2_handle, asymptote_handle, damping_handle]
            if handle is not None
        ]
        if handles:
            self.axes.legend(handles=handles, loc="best")

        self.canvas.draw_idle()

    def draw_asymptotes(self, poles, zeros, limits):
        pole_count = len(poles)
        zero_count = len(zeros)
        asymptote_count = pole_count - zero_count
        if asymptote_count <= 0:
            return None

        centroid = (np.sum(poles) - np.sum(zeros)) / asymptote_count if zero_count else np.sum(poles) / asymptote_count
        centroid_real = float(np.real(centroid))
        span = max(limits[1] - limits[0], limits[3] - limits[2]) * 0.9
        asymptote_handle = None

        # Root-locus asymptote angles: (2q + 1) * pi / (n - m)
        for idx in range(asymptote_count):
            angle = ((2 * idx + 1) * math.pi) / asymptote_count
            x_values = np.array([
                centroid_real - span * math.cos(angle),
                centroid_real + span * math.cos(angle),
            ])
            y_values = np.array([
                -span * math.sin(angle),
                span * math.sin(angle),
            ])
            line, = self.axes.plot(
                x_values,
                y_values,
                linestyle="--",
                linewidth=1.0,
                color="#7f8c8d",
                alpha=0.9,
                label="Asymptotes" if asymptote_handle is None else None,
                zorder=1,
            )
            if asymptote_handle is None:
                asymptote_handle = line

        self.axes.scatter([centroid_real], [0.0], color="#7f8c8d", s=26, zorder=4)
        self.axes.annotate(
            f"Centroid = {centroid_real:.2f}",
            xy=(centroid_real, 0.0),
            xytext=(8, -14),
            textcoords="offset points",
            color="#566573",
            fontsize=8,
        )
        return asymptote_handle

    def draw_damping_line(self, zeta, limits):
        if zeta is None:
            return None
        zeta = float(zeta)
        if zeta <= 0.0 or zeta > 1.0:
            return None

        span = max(abs(limits[0]), abs(limits[1]), abs(limits[2]), abs(limits[3]), 1.0) * 1.05
        damping_handle = None

        if math.isclose(zeta, 1.0):
            line, = self.axes.plot(
                [-span, 0.0],
                [0.0, 0.0],
                linestyle=(0, (4, 4)),
                linewidth=1.2,
                color="green",
                label=f"zeta = {zeta:.2f}",
                zorder=1,
            )
            return line

        beta = math.sqrt(max(1.0 - zeta * zeta, 0.0))
        radius = np.linspace(0.0, span, 100)
        sigma = -radius * zeta
        omega = radius * beta

        for sign in (1.0, -1.0):
            line, = self.axes.plot(
                sigma,
                sign * omega,
                linestyle=(0, (6, 3)),
                linewidth=1.2,
                color="green",
                alpha=0.85,
                label=f"zeta = {zeta:.2f}" if damping_handle is None else None,
                zorder=1,
            )
            if damping_handle is None:
                damping_handle = line

        self.axes.annotate(
            f"zeta = {zeta:.2f}",
            xy=(sigma[-1], omega[-1]),
            xytext=(-70, 10),
            textcoords="offset points",
            color="green",
            fontsize=8,
        )
        return damping_handle

    def _fit_axes(self, branches, poles, zeros):
        points = [branches.flatten()]
        if poles.size:
            points.append(poles)
        if zeros.size:
            points.append(zeros)

        combined = np.concatenate(points)
        real_min = float(np.min(combined.real))
        real_max = float(np.max(combined.real))
        imag_min = float(np.min(combined.imag))
        imag_max = float(np.max(combined.imag))

        real_span = max(real_max - real_min, 1.0)
        imag_span = max(imag_max - imag_min, 1.0)
        padding_real = 0.15 * real_span
        padding_imag = 0.20 * imag_span

        limits = (
            real_min - padding_real,
            real_max + padding_real,
            imag_min - padding_imag,
            imag_max + padding_imag,
        )
        self.axes.set_xlim(limits[0], limits[1])
        self.axes.set_ylim(limits[2], limits[3])
        return limits


class PlotPanel(RootLocusWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
