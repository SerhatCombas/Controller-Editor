#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QSplitter, QVBoxLayout, QWidget

from animations.pendulum_widget import AnimationPanel
from controls.control_panel import ControlSelectionPanel
from plots.grid3.plot_panel import PlotPanel
from signals.grid4.signal_panel import SignalPanel
from transfer.grid5.transfer_function_panel import TransferFunctionPanel


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qt + Pygame Grid Arayuzu")
        self.resize(1360, 880)

        self.current_control_config = {}
        self.current_simulation_config = {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        self.animation_panel = AnimationPanel(width=520, height=320)
        self.control_panel = ControlSelectionPanel()
        self.transfer_panel = TransferFunctionPanel()
        self.plot_panel = PlotPanel()
        self.signal_panel = SignalPanel()

        self._configure_panel_policies()
        content_splitter = self._build_splitter_layout()

        self.control_panel.control_changed.connect(self._handle_control_changed)
        self.control_panel.play_requested.connect(self.start_simulation)
        self.control_panel.stop_requested.connect(self.stop_simulation)
        self.animation_panel.simulation_settings_changed.connect(self._handle_simulation_settings_changed)
        self.animation_panel.simulation_data_changed.connect(self.signal_panel.append_data_from_state)

        footer_layout = QHBoxLayout()
        footer_layout.addStretch()
        self.close_button = QPushButton("Pencereyi Kapat")
        self.close_button.setFixedHeight(40)
        self.close_button.clicked.connect(self.close)
        footer_layout.addWidget(self.close_button)

        main_layout.addWidget(content_splitter, 1)
        main_layout.addLayout(footer_layout)

        self.current_control_config = self._build_default_control_config()
        self.current_simulation_config = self.animation_panel.simulation_controls.current_settings()
        self.control_panel.set_physical_model(self.current_simulation_config.get("physical_model", "Motor-Belt-Pendulum"))
        self._push_merged_config(reset_signal_plot=False)

    def _build_default_control_config(self):
        return {
            "algorithm": "PID",
            "components": {"P": True, "I": False, "D": False},
            "gains": {"P": 35.0, "I": 0.8, "D": 6.0},
            "state_space": {"K": [1.6, 2.4, 34.0, 7.5]},
            "lqr": {"Q_diag": [1.0, 1.0, 100.0, 10.0], "R": 0.01, "K": [0.0, 0.0, 0.0, 0.0]},
            "analysis": {"damping_ratio": 0.50},
        }

    def _configure_panel_policies(self):
        self.animation_panel.setMinimumSize(320, 340)
        self.animation_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.control_panel.setMinimumWidth(320)
        self.control_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.transfer_panel.setMinimumWidth(300)
        self.transfer_panel.setMinimumHeight(220)
        self.transfer_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.plot_panel.setMinimumHeight(220)
        self.plot_panel.setMinimumWidth(320)
        self.plot_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.signal_panel.setMinimumHeight(220)
        self.signal_panel.setMinimumWidth(320)
        self.signal_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def _configure_splitter(self, splitter, stretch_factors):
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)
        for index, factor in enumerate(stretch_factors):
            splitter.setStretchFactor(index, factor)
        return splitter

    def _build_splitter_layout(self):
        top_splitter = QSplitter(Qt.Horizontal)
        top_splitter.addWidget(self.animation_panel)
        top_splitter.addWidget(self.control_panel)
        top_splitter.addWidget(self.transfer_panel)
        self._configure_splitter(top_splitter, [7, 4, 4])
        top_splitter.setSizes([700, 420, 360])

        bottom_splitter = QSplitter(Qt.Horizontal)
        bottom_splitter.addWidget(self.plot_panel)
        bottom_splitter.addWidget(self.signal_panel)
        self._configure_splitter(bottom_splitter, [5, 4])
        bottom_splitter.setSizes([760, 520])

        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(bottom_splitter)
        self._configure_splitter(main_splitter, [5, 3])
        main_splitter.setSizes([560, 320])
        return main_splitter

    def _merged_config(self):
        merged = {}
        merged.update(self.current_control_config)
        merged.update(self.current_simulation_config)
        return merged

    def _push_merged_config(self, reset_signal_plot=True):
        config = self._merged_config()
        self.animation_panel.set_control_config(config)
        self.plot_panel.update_root_locus(config)
        self.transfer_panel.update_transfer_functions(config)
        if reset_signal_plot:
            self.signal_panel.reset_plot()

    def _handle_control_changed(self, config):
        self.current_control_config = config
        self._push_merged_config(reset_signal_plot=True)

    def _handle_simulation_settings_changed(self, config):
        self.current_simulation_config = config
        self.control_panel.set_physical_model(config.get("physical_model", "Motor-Belt-Pendulum"))
        self._push_merged_config(reset_signal_plot=True)

    def start_simulation(self):
        self.signal_panel.reset_plot()
        self.animation_panel.reset_simulation()
        self.animation_panel.start_animation()

    def stop_simulation(self):
        self.animation_panel.stop_animation()
