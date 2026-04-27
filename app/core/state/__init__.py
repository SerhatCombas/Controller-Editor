"""Application and simulation state models."""

from app.core.state.app_state import AppState, ControllerConfig, RoadProfileConfig, SignalSelection, SimulationConfig
from app.core.state.app_state_v2 import AnalysisConfig, AppStateV2, ControllerConfigV2

__all__ = [
    # Legacy (5MVP-6 deletion target)
    "AppState", "ControllerConfig", "RoadProfileConfig", "SignalSelection", "SimulationConfig",
    # V2 (generic, template-independent)
    "AppStateV2", "ControllerConfigV2", "AnalysisConfig",
]
