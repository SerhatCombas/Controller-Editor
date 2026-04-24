from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.base.source_descriptor import SourceDescriptor

try:
    import numpy as np
except ModuleNotFoundError:
    np = None

try:
    from scipy import signal
except ModuleNotFoundError:
    signal = None

from app.core.models.sources.base_signal import SignalSource


class RandomRoad(SignalSource):
    def __init__(
        self,
        component_id: str,
        *,
        amplitude: float,
        roughness: float,
        seed: int,
        vehicle_speed: float,
        dt: float,
        duration: float,
        name: str = "Random Road",
    ) -> None:
        super().__init__(component_id, name=name)
        self.parameters.update(
            {
                "amplitude": amplitude,
                "roughness": roughness,
                "seed": float(seed),
                "vehicle_speed": vehicle_speed,
                "dt": dt,
                "duration": duration,
            }
        )
        step_count = max(int(duration / dt) + 1, 2)
        self._time = [index * dt for index in range(step_count)]
        self._distance = [time * self.parameters["vehicle_speed"] for time in self._time]
        self._road = self._generate_profile()

    def _generate_profile(self):
        sample_count = len(self._distance)
        alpha = pow(2.718281828, -self.parameters["roughness"] * self.parameters["dt"])
        if np is not None and signal is not None:
            rng = np.random.default_rng(int(self.parameters["seed"]))
            noise = rng.standard_normal(sample_count)
            road = signal.lfilter([1.0 - alpha], [1.0, -alpha], noise)
            road *= self.parameters["amplitude"]
            return road.tolist()

        rng = random.Random(int(self.parameters["seed"]))
        road: list[float] = []
        filtered = 0.0
        for _ in range(sample_count):
            white = rng.gauss(0.0, 1.0)
            filtered = alpha * filtered + (1.0 - alpha) * white
            road.append(filtered * self.parameters["amplitude"])
        return road

    def spatial_profile(self, distance: float) -> float:
        if distance <= self._distance[0]:
            return float(self._road[0])
        if distance >= self._distance[-1]:
            return float(self._road[-1])
        for index in range(1, len(self._distance)):
            left = self._distance[index - 1]
            right = self._distance[index]
            if distance <= right:
                ratio = (distance - left) / max(right - left, 1e-12)
                return float(self._road[index - 1] * (1.0 - ratio) + self._road[index] * ratio)
        return float(self._road[-1])

    def displacement_output(self, time: float) -> float:
        return self.spatial_profile(self.parameters["vehicle_speed"] * time)

    def velocity_output(self, time: float) -> float:
        gradients: list[float] = []
        for index, value in enumerate(self._road):
            if index == 0:
                dv = self._road[1] - value
                dx = self._distance[1] - self._distance[0]
            elif index == len(self._road) - 1:
                dv = value - self._road[index - 1]
                dx = self._distance[index] - self._distance[index - 1]
            else:
                dv = self._road[index + 1] - self._road[index - 1]
                dx = self._distance[index + 1] - self._distance[index - 1]
            gradients.append(dv / max(dx, 1e-12))
        target_distance = self.parameters["vehicle_speed"] * time
        if target_distance <= self._distance[0]:
            return gradients[0] * self.parameters["vehicle_speed"]
        if target_distance >= self._distance[-1]:
            return gradients[-1] * self.parameters["vehicle_speed"]
        for index in range(1, len(self._distance)):
            left = self._distance[index - 1]
            right = self._distance[index]
            if target_distance <= right:
                ratio = (target_distance - left) / max(right - left, 1e-12)
                value = gradients[index - 1] * (1.0 - ratio) + gradients[index] * ratio
                return value * self.parameters["vehicle_speed"]
        return gradients[-1] * self.parameters["vehicle_speed"]

    def constitutive_equations(self) -> list[str]:
        return [
            f"r_{self.id}(t) = filtered_white_noise(seed={int(self.parameters['seed'])})",
            f"dr_{self.id}/dt = road_velocity({self.id}, t)",
        ]

    # ------------------------------------------------------------------
    # Wave 1 polymorphic interface
    # ------------------------------------------------------------------

    def get_source_descriptor(self) -> SourceDescriptor:
        """RandomRoad injects a stochastic displacement profile at its output port.

        Displacement-source semantics: the InputRouter will route this into
        the constraint/input vector as a kinematic excitation rather than a
        force injection.
        """
        from app.core.base.source_descriptor import SourceDescriptor
        return SourceDescriptor(
            kind="displacement",
            driven_port_name="port",
            reference_port_name="reference_port",
            input_variable_name=f"u_{self.id}",
            amplitude_parameter="amplitude",
        )
