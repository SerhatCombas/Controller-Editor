from __future__ import annotations

from dataclasses import dataclass

from app.core.state.app_state import ControllerConfig


@dataclass(slots=True)
class ControllerState:
    integral_error: float = 0.0
    last_error: float = 0.0


class ControllerService:
    def __init__(self) -> None:
        self.state = ControllerState()

    def reset(self) -> None:
        self.state = ControllerState()

    def compute_force(self, config: ControllerConfig, body_displacement: float, body_velocity: float, dt: float) -> float:
        if not config.enabled:
            return 0.0

        error = -body_displacement
        self.state.integral_error += error * dt
        derivative = (error - self.state.last_error) / dt if dt > 0.0 else -body_velocity
        self.state.last_error = error

        force = (
            config.kp * error
            + config.ki * self.state.integral_error
            + config.kd * derivative
        )
        return max(min(force, 5000.0), -5000.0)
