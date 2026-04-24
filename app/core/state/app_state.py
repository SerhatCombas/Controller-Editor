from __future__ import annotations

from dataclasses import dataclass, field

from app.core.models.quarter_car_model import QuarterCarParameters, QuarterCarState


@dataclass(slots=True)
class RoadProfileConfig:
    road_type: str = "random"
    amplitude: float = 0.03
    roughness: float = 0.35
    cutoff_hz: float = 1.4
    seed: int = 7
    speed_mps: float = 6.0


@dataclass(slots=True)
class ControllerConfig:
    kp: float = 850.0
    ki: float = 45.0
    kd: float = 180.0
    enabled: bool = True


@dataclass(slots=True)
class SignalSelection:
    input_signals: tuple[str, ...] = ()
    input_component_ids: tuple[str, ...] = ()
    input_profile: str | None = None
    output_signals: tuple[str, ...] = ()
    output_component_ids: tuple[str, ...] = ()
    input_amplitude: float = 0.03
    input_frequency_hz: float = 1.5
    input_start_time: float = 0.5

    @property
    def output_signal(self) -> str | None:
        return self.output_signals[0] if self.output_signals else None

    @property
    def input_source(self) -> str | None:
        return self.input_signals[0] if self.input_signals else None

    @property
    def input_component_id(self) -> str | None:
        return self.input_component_ids[0] if self.input_component_ids else None


@dataclass(slots=True)
class SimulationConfig:
    duration: float = 12.0
    sample_time: float = 0.04
    runtime_backend: str = "numeric"
    model_template: str = "quarter_car"


@dataclass(slots=True)
class AppState:
    parameters: QuarterCarParameters = field(default_factory=QuarterCarParameters)
    road_profile: RoadProfileConfig = field(default_factory=RoadProfileConfig)
    controller: ControllerConfig = field(default_factory=ControllerConfig)
    selection: SignalSelection = field(default_factory=SignalSelection)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    state: QuarterCarState = field(default_factory=QuarterCarState)
