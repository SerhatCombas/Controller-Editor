from __future__ import annotations

from collections import deque

import numpy as np
from scipy import signal

from app.services.simulation_backend import SimulationBackend


class PlottingService:
    def __init__(self, backend: SimulationBackend, max_samples: int = 500) -> None:
        self.backend = backend
        self.max_samples = max_samples
        self._selected_live_outputs: tuple[str, ...] = ()
        self.history_time: deque[float] = deque(maxlen=self.max_samples)
        self.history_series: dict[str, deque[float]] = {}

    def configure_live_outputs(self, output_signals: list[str] | tuple[str, ...], *, reset: bool = False) -> None:
        normalized = tuple(output_signals)
        if reset or normalized != self._selected_live_outputs:
            self._selected_live_outputs = normalized
            self.history_time = deque(maxlen=self.max_samples)
            self.history_series = {signal_id: deque(maxlen=self.max_samples) for signal_id in normalized}
        else:
            for signal_id in normalized:
                self.history_series.setdefault(signal_id, deque(maxlen=self.max_samples))

    def reset_history(self) -> None:
        self.history_time = deque(maxlen=self.max_samples)
        self.history_series = {signal_id: deque(maxlen=self.max_samples) for signal_id in self._selected_live_outputs}

    def append_live_sample(
        self,
        *,
        time_value: float,
        outputs: dict[str, float],
        selected_outputs: list[str] | tuple[str, ...],
    ) -> dict[str, np.ndarray | dict[str, np.ndarray]]:
        self.configure_live_outputs(selected_outputs)
        self.history_time.append(time_value)
        for signal_id in self._selected_live_outputs:
            self.history_series.setdefault(signal_id, deque(maxlen=self.max_samples))
            self.history_series[signal_id].append(float(outputs.get(signal_id, 0.0)))
        return self.live_output_data()

    def live_output_data(self) -> dict[str, np.ndarray | dict[str, np.ndarray]]:
        return {
            "time": np.asarray(self.history_time, dtype=float),
            "series": {
                signal_id: np.asarray(values, dtype=float)
                for signal_id, values in self.history_series.items()
            },
        }

    def response_data(
        self,
        *,
        output_signals: list[str] | tuple[str, ...],
        input_channel: str,
        duration: float = 5.0,
        sample_count: int = 400,
    ) -> dict[str, np.ndarray | dict[str, np.ndarray]]:
        time = np.linspace(0.0, duration, sample_count)
        responses: dict[str, np.ndarray] = {}
        for output_signal in output_signals:
            system = self._siso_system(output_signal=output_signal, input_channel=input_channel)
            response_time, response = signal.step(system, T=time)
            responses[output_signal] = np.asarray(response, dtype=float)
            time = response_time
        return {"time": time, "responses": responses}

    def bode_data(self, *, output_signals: list[str] | tuple[str, ...], input_channel: str) -> dict[str, object]:
        w = np.logspace(-1, 2, 350)
        series: dict[str, dict[str, np.ndarray]] = {}
        for output_signal in output_signals:
            system = self._siso_system(output_signal=output_signal, input_channel=input_channel)
            frequency, magnitude, phase = signal.bode(system, w=w)
            series[output_signal] = {"magnitude": magnitude, "phase": phase}
        return {"frequency": frequency, "series": series}

    def pole_zero_data(self, *, output_signals: list[str] | tuple[str, ...], input_channel: str) -> dict[str, object]:
        series: dict[str, dict[str, np.ndarray]] = {}
        for output_signal in output_signals:
            system = self._siso_system(output_signal=output_signal, input_channel=input_channel)
            zeros, poles, gain = signal.ss2zpk(system.A, system.B, system.C, system.D)
            series[output_signal] = {"poles": poles, "zeros": zeros, "gain": np.asarray([gain], dtype=float)}
        return {"series": series}

    def _siso_system(self, *, output_signal: str, input_channel: str) -> signal.StateSpace:
        state_space = self.backend.get_state_space(
            input_channel=input_channel,
            output_variables=[output_signal],
        )
        return signal.StateSpace(
            state_space.a_matrix,
            state_space.b_matrix,
            state_space.c_matrix,
            state_space.d_matrix,
        )
