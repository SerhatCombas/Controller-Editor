"""AppStateV2 — Generic, template-independent application state.

Faz 5MVP-2: Replaces the old AppState that was hardcoded to
QuarterCarParameters/QuarterCarState. AppStateV2 stores:

  1. A compiled SystemGraph (the model) — or None before first compile
  2. A StaticAnalysisResult (from GenericStaticBackend) — or None
  3. Controller config (PID parameters for future closed-loop)
  4. Signal selection (which input/output to display in analysis plots)

Lifecycle::

    state = AppStateV2()

    # User builds a circuit on canvas → "Compile" button
    state.graph = canvas_compiler.compile(...)

    # Controller/backend analyzes the graph
    result = GenericStaticBackend().analyze(state.graph)
    state.analysis_result = result

    # User selects an input/output pair → SISO view
    state.selected_input_id = "input_force"
    state.selected_output_id = "mass_displacement"

The old AppState (app_state.py) remains untouched as a compatibility
layer — MainWindow (legacy) still imports it. MainWindow_v2 (5MVP-3)
will use AppStateV2 exclusively.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.graph.system_graph import SystemGraph
    from app.services.static_analysis_backend import StaticAnalysisResult


@dataclass(slots=True)
class ControllerConfigV2:
    """PID controller parameters.

    Same fields as the old ControllerConfig but decoupled from the
    legacy app_state module. Kept as a separate dataclass so that
    controller_service.py can consume it without importing AppStateV2.
    """
    kp: float = 0.0
    ki: float = 0.0
    kd: float = 0.0
    enabled: bool = False


@dataclass(slots=True)
class AnalysisConfig:
    """Configuration for static analysis display.

    Controls which input/output pair the UI shows in step response,
    Bode, and pole-zero plots.
    """
    selected_input_id: str | None = None
    selected_output_id: str | None = None


@dataclass(slots=True)
class AppStateV2:
    """Generic application state — no template or model-specific types.

    All model information comes from the SystemGraph and its probes.
    Parameter values live inside the graph's components (e.g.
    ``graph.components["mass"].mass``), not in a separate dataclass.

    Attributes:
        graph: The compiled SystemGraph from the canvas, or None before
            the first compile.
        analysis_result: The latest StaticAnalysisResult from
            GenericStaticBackend.analyze(), or None.
        controller: PID controller parameters (for future closed-loop).
        analysis_config: Which input/output pair to display.
        is_compiled: Convenience flag — True after a successful compile.
        compile_error: Human-readable error from the last failed compile,
            or None if the last compile succeeded.
        analysis_error: Human-readable error from the last failed
            analysis, or None if the last analysis succeeded.
    """
    # Core model data
    graph: SystemGraph | None = None
    analysis_result: StaticAnalysisResult | None = None

    # Configuration
    controller: ControllerConfigV2 = field(default_factory=ControllerConfigV2)
    analysis_config: AnalysisConfig = field(default_factory=AnalysisConfig)

    # Status tracking
    compile_error: str | None = None
    analysis_error: str | None = None

    @property
    def is_compiled(self) -> bool:
        """True if a graph has been successfully compiled."""
        return self.graph is not None and self.compile_error is None

    @property
    def is_analyzed(self) -> bool:
        """True if analysis has been run successfully."""
        return self.analysis_result is not None and self.analysis_error is None

    @property
    def n_states(self) -> int:
        """Number of state variables in the analyzed system, or 0."""
        if self.analysis_result is None:
            return 0
        return self.analysis_result.n_states

    @property
    def n_inputs(self) -> int:
        """Number of inputs in the analyzed system, or 0."""
        if self.analysis_result is None:
            return 0
        return self.analysis_result.n_inputs

    @property
    def n_outputs(self) -> int:
        """Number of outputs in the analyzed system, or 0."""
        if self.analysis_result is None:
            return 0
        return self.analysis_result.n_outputs

    @property
    def is_stable(self) -> bool | None:
        """System stability, or None if not yet analyzed."""
        if self.analysis_result is None:
            return None
        return self.analysis_result.is_stable

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def set_compiled(
        self,
        graph: SystemGraph,
    ) -> None:
        """Record a successful compile. Clears previous analysis."""
        self.graph = graph
        self.compile_error = None
        # Analysis is stale after a new compile
        self.analysis_result = None
        self.analysis_error = None

    def set_compile_failed(self, error: str) -> None:
        """Record a failed compile."""
        self.graph = None
        self.compile_error = error
        self.analysis_result = None
        self.analysis_error = None

    def set_analyzed(self, result: StaticAnalysisResult) -> None:
        """Record a successful analysis."""
        self.analysis_result = result
        self.analysis_error = None

    def set_analysis_failed(self, error: str) -> None:
        """Record a failed analysis."""
        self.analysis_result = None
        self.analysis_error = error

    def reset(self) -> None:
        """Clear all state — back to initial blank workspace."""
        self.graph = None
        self.analysis_result = None
        self.compile_error = None
        self.analysis_error = None
        self.analysis_config = AnalysisConfig()
