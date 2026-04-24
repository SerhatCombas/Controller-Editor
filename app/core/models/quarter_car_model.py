from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class QuarterCarParameters:
    body_mass: float = 300.0
    wheel_mass: float = 40.0
    suspension_spring: float = 15000.0
    suspension_damper: float = 1200.0
    tire_stiffness: float = 180000.0


@dataclass(slots=True)
class QuarterCarState:
    body_displacement: float = 0.0
    body_velocity: float = 0.0
    wheel_displacement: float = 0.0
    wheel_velocity: float = 0.0

    def as_vector(self) -> np.ndarray:
        return np.array(
            [
                self.body_displacement,
                self.body_velocity,
                self.wheel_displacement,
                self.wheel_velocity,
            ],
            dtype=float,
        )

    @classmethod
    def from_vector(cls, values: np.ndarray) -> "QuarterCarState":
        return cls(
            body_displacement=float(values[0]),
            body_velocity=float(values[1]),
            wheel_displacement=float(values[2]),
            wheel_velocity=float(values[3]),
        )


class QuarterCarModel:
    OUTPUT_LABELS = {
        "body_displacement": "Body displacement x_b(t)",
        "wheel_displacement": "Wheel displacement x_w(t)",
        "suspension_deflection": "Suspension deflection x_b(t) - x_w(t)",
        "body_acceleration": "Body acceleration x_b''(t)",
        "tire_deflection": "Tire deflection x_w(t) - r(t)",
    }

    INPUT_LABELS = {
        "body_force": "External body force F(t)",
        "road_displacement": "Road displacement r(t)",
    }

    def __init__(self, parameters: QuarterCarParameters | None = None) -> None:
        self.parameters = parameters or QuarterCarParameters()

    def derivatives(self, _time: float, state: np.ndarray, road_height: float, external_force: float) -> np.ndarray:
        p = self.parameters
        xb, xbd, xw, xwd = state

        suspension_force = p.suspension_spring * (xb - xw)
        damping_force = p.suspension_damper * (xbd - xwd)
        tire_force = p.tire_stiffness * (xw - road_height)

        body_acceleration = (-suspension_force - damping_force + external_force) / p.body_mass
        wheel_acceleration = (suspension_force + damping_force - tire_force - external_force) / p.wheel_mass
        return np.array([xbd, body_acceleration, xwd, wheel_acceleration], dtype=float)

    def state_space_matrices(self) -> tuple[np.ndarray, np.ndarray]:
        p = self.parameters
        a = np.array(
            [
                [0.0, 1.0, 0.0, 0.0],
                [-p.suspension_spring / p.body_mass, -p.suspension_damper / p.body_mass, p.suspension_spring / p.body_mass, p.suspension_damper / p.body_mass],
                [0.0, 0.0, 0.0, 1.0],
                [p.suspension_spring / p.wheel_mass, p.suspension_damper / p.wheel_mass, -(p.suspension_spring + p.tire_stiffness) / p.wheel_mass, -p.suspension_damper / p.wheel_mass],
            ],
            dtype=float,
        )
        b = np.array(
            [
                [0.0, 0.0],
                [1.0 / p.body_mass, 0.0],
                [0.0, 0.0],
                [-1.0 / p.wheel_mass, p.tire_stiffness / p.wheel_mass],
            ],
            dtype=float,
        )
        return a, b

    def output_matrices(self, output_signal: str) -> tuple[np.ndarray, np.ndarray]:
        p = self.parameters
        if output_signal == "body_displacement":
            c = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=float)
            d = np.array([[0.0, 0.0]], dtype=float)
        elif output_signal == "wheel_displacement":
            c = np.array([[0.0, 0.0, 1.0, 0.0]], dtype=float)
            d = np.array([[0.0, 0.0]], dtype=float)
        elif output_signal == "suspension_deflection":
            c = np.array([[1.0, 0.0, -1.0, 0.0]], dtype=float)
            d = np.array([[0.0, 0.0]], dtype=float)
        elif output_signal == "body_acceleration":
            c = np.array(
                [[-p.suspension_spring / p.body_mass, -p.suspension_damper / p.body_mass, p.suspension_spring / p.body_mass, p.suspension_damper / p.body_mass]],
                dtype=float,
            )
            d = np.array([[1.0 / p.body_mass, 0.0]], dtype=float)
        elif output_signal == "tire_deflection":
            c = np.array([[0.0, 0.0, 1.0, 0.0]], dtype=float)
            d = np.array([[0.0, -1.0]], dtype=float)
        else:
            raise KeyError(f"Unknown output signal: {output_signal}")
        return c, d

    def input_index(self, input_name: str) -> int:
        mapping = {"body_force": 0, "road_displacement": 1}
        return mapping[input_name]

    def output_values(self, state: QuarterCarState, *, road_height: float, external_force: float) -> dict[str, float]:
        p = self.parameters
        suspension_force = p.suspension_spring * (state.body_displacement - state.wheel_displacement)
        damping_force = p.suspension_damper * (state.body_velocity - state.wheel_velocity)
        body_acceleration = (-suspension_force - damping_force + external_force) / p.body_mass
        return {
            "body_displacement": state.body_displacement,
            "wheel_displacement": state.wheel_displacement,
            "suspension_deflection": state.body_displacement - state.wheel_displacement,
            "body_acceleration": body_acceleration,
            "tire_deflection": state.wheel_displacement - road_height,
        }
