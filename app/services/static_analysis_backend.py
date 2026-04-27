"""GenericStaticBackend — Faz 5MVP-1.

Single facade that takes any SystemGraph and produces:
  1. StateSpaceModel  (A, B, C, D matrices)
  2. Transfer functions for every (input, output) pair
  3. Metadata for UI panels (stability, pole locations, etc.)

Pipeline:
  SystemGraph
    → PolymorphicDAEReducer  → ReducedODESystem (M, D, K, A, B)
    → StateSpaceBuilder      → StateSpaceModel  (+ C, D from probes)
    → SymbolicTFBuilder      → TransferFunctionResult per (input, output)

This backend does NOT run time-domain simulations. It computes the
linear state-space representation and symbolic transfer functions —
everything needed for step response, Bode plot, pole-zero map, and
controllability/observability analysis can be derived from these.

Usage::

    backend = GenericStaticBackend()
    result = backend.analyze(graph)

    # State-space matrices
    result.state_space.a_matrix  # list[list[float]]
    result.state_space.b_matrix  # ...

    # Transfer functions
    for tf in result.transfer_functions:
        print(tf.input_id, "→", tf.output_id, "order:", tf.order)

    # Stability
    result.is_stable       # bool — all poles have Re < 0
    result.n_states        # int
    result.n_inputs        # int
    result.n_outputs       # int
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.core.symbolic.output_mapper import OutputExpression, OutputMapper
from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
from app.core.symbolic.state_space_builder import StateSpaceBuilder
from app.core.symbolic.symbolic_system import (
    ReducedODESystem,
    StateSpaceModel,
    SymbolicSystem,
)
from app.core.symbolic.tf_builder import (
    SimplificationMode,
    SymbolicTFBuilder,
    TransferFunctionResult,
    UnsupportedTFResult,
)

if TYPE_CHECKING:
    from app.core.graph.system_graph import SystemGraph


# ---------------------------------------------------------------------------
# Minimal SymbolicSystem stub — PolymorphicDAEReducer only reads
# output_definitions, algebraic_constraints, and metadata from it.
# The reducer does all the real work via the component polymorphic interface.
# ---------------------------------------------------------------------------

class _MinimalSymbolicSystem:
    """Lightweight stand-in for EquationBuilder output.

    The PolymorphicDAEReducer accesses exactly three fields:
      - output_definitions (dict)
      - algebraic_constraints (list)
      - metadata (dict)
    Everything else is derived from the graph's components directly.
    """
    output_definitions: dict = {}
    algebraic_constraints: list = []
    metadata: dict = {}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class StaticAnalysisResult:
    """Complete static analysis of a linear system.

    Produced by ``GenericStaticBackend.analyze()``. Contains everything
    the UI needs to render step response, Bode, pole-zero, and stability
    indicators.
    """
    # Core state-space model (A, B, C, D + variable names)
    state_space: StateSpaceModel

    # Intermediate products (available for advanced inspection)
    reduced_ode: ReducedODESystem

    # Transfer functions — one per (input, supported_output) pair
    transfer_functions: tuple[TransferFunctionResult, ...] = ()

    # Unsupported TF results (for UI feedback — "this probe can't be TF'd")
    unsupported_outputs: tuple[UnsupportedTFResult, ...] = ()

    # Output expressions from OutputMapper (C/D rows per probe)
    output_expressions: tuple[OutputExpression, ...] = ()

    # Convenience properties
    @property
    def n_states(self) -> int:
        return len(self.state_space.state_variables)

    @property
    def n_inputs(self) -> int:
        return len(self.state_space.input_variables)

    @property
    def n_outputs(self) -> int:
        return len(self.state_space.output_variables)

    @property
    def is_stable(self) -> bool:
        """True if ALL transfer functions have poles with Re < 0."""
        import sympy
        for tf in self.transfer_functions:
            for pole in tf.poles:
                if float(sympy.re(pole)) >= 0.0:
                    return False
        return len(self.transfer_functions) > 0

    @property
    def poles(self) -> tuple:
        """Union of all poles across all transfer functions (deduplicated)."""
        seen: set = set()
        result: list = []
        for tf in self.transfer_functions:
            for pole in tf.poles:
                key = complex(pole)
                if key not in seen:
                    seen.add(key)
                    result.append(pole)
        return tuple(result)


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------

class GenericStaticBackend:
    """Domain-agnostic static analysis backend.

    Accepts any well-formed SystemGraph (mechanical, electrical, or mixed)
    and produces a StaticAnalysisResult containing:
      - State-space matrices
      - Symbolic transfer functions
      - Stability metadata

    Thread-safety: instances are stateless — ``analyze()`` can be called
    concurrently on different graphs.
    """

    def __init__(
        self,
        *,
        simplification_mode: SimplificationMode = "raw",
    ) -> None:
        self._simplification_mode = simplification_mode

    def analyze(
        self,
        graph: SystemGraph,
        *,
        build_transfer_functions: bool = True,
        selected_input_id: str | None = None,
        selected_output_id: str | None = None,
    ) -> StaticAnalysisResult:
        """Run the full static analysis pipeline on the given graph.

        Args:
            graph: A connected SystemGraph with components and probes.
            build_transfer_functions: If False, skip TF computation
                (useful when only state-space is needed).
            selected_input_id: If provided, only build TFs for this input.
                If None, uses graph.selected_input_id (falls back to all
                inputs if that is also None).
            selected_output_id: If provided, only build TF for this output.
                If None, builds TFs for all probes.

        Returns:
            StaticAnalysisResult with state-space and TF data.

        Raises:
            AnalysisError: If the graph has no inertial DOFs or the
                pipeline encounters an unrecoverable error.
        """
        # Step 1: Reduce DAE to first-order ODE (M, D, K → A, B)
        reducer = PolymorphicDAEReducer()
        stub = _MinimalSymbolicSystem()
        reduced_ode = reducer.reduce(graph, stub)

        if not reduced_ode.state_variables:
            raise AnalysisError(
                "No state variables found. The graph has no inertial or "
                "energy-storing components (mass, inductor, capacitor, etc.)."
            )

        # Step 2: Build state-space model (add C, D from probes)
        ss_builder = StateSpaceBuilder()
        state_space = ss_builder.build(graph, reduced_ode)

        # Step 3: Build transfer functions (optional)
        tfs: list[TransferFunctionResult] = []
        unsupported: list[UnsupportedTFResult] = []
        output_exprs: list[OutputExpression] = []

        if build_transfer_functions and graph.probes:
            mapper = OutputMapper()
            tf_builder = SymbolicTFBuilder()

            # Determine which inputs to use
            input_ids = self._resolve_input_ids(
                reduced_ode, graph, selected_input_id,
            )

            # Determine which probes to use
            probes = self._resolve_probes(graph, selected_output_id)

            for probe_id, probe in probes.items():
                expr = mapper.map(probe, reduced_ode, graph=graph)
                output_exprs.append(expr)

                if not expr.supported_for_tf:
                    unsupported.append(UnsupportedTFResult(
                        input_id="*",
                        output_id=probe_id,
                        input_label="*",
                        output_label=getattr(probe, "name", probe_id),
                        is_supported=False,
                        unsupported_reason=expr.unsupported_reason or "Unsupported output",
                        laplace_symbol_name="s",
                        source_path="static_analysis_backend",
                        provenance=("GenericStaticBackend.analyze",),
                    ))
                    continue

                for input_id in input_ids:
                    result = tf_builder.build_siso_tf(
                        reduced_ode=reduced_ode,
                        input_id=input_id,
                        output_expr=expr,
                        mode=self._simplification_mode,
                    )
                    if isinstance(result, TransferFunctionResult):
                        tfs.append(result)
                    else:
                        unsupported.append(result)

        return StaticAnalysisResult(
            state_space=state_space,
            reduced_ode=reduced_ode,
            transfer_functions=tuple(tfs),
            unsupported_outputs=tuple(unsupported),
            output_expressions=tuple(output_exprs),
        )

    # ------------------------------------------------------------------
    # Convenience: analyze a single SISO path
    # ------------------------------------------------------------------

    def analyze_siso(
        self,
        graph: SystemGraph,
        input_id: str,
        output_probe_id: str,
    ) -> TransferFunctionResult | UnsupportedTFResult:
        """Shorthand for a single input→output transfer function.

        Returns the TF result directly (no StaticAnalysisResult wrapper).
        """
        result = self.analyze(
            graph,
            selected_input_id=input_id,
            selected_output_id=output_probe_id,
        )
        if result.transfer_functions:
            return result.transfer_functions[0]
        if result.unsupported_outputs:
            return result.unsupported_outputs[0]
        raise AnalysisError(
            f"No TF produced for {input_id} → {output_probe_id}."
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_input_ids(
        reduced_ode: ReducedODESystem,
        graph: SystemGraph,
        selected: str | None,
    ) -> list[str]:
        """Determine which input column(s) to use for TF construction."""
        if selected is not None:
            # Caller explicitly chose an input — verify it exists
            if selected not in reduced_ode.input_variables:
                # Try with r_ prefix (displacement sources get r_<id> in the reducer)
                prefixed = f"r_{selected}"
                if prefixed in reduced_ode.input_variables:
                    return [prefixed]
                f_prefixed = f"f_{selected}_out"
                if f_prefixed in reduced_ode.input_variables:
                    return [f_prefixed]
                raise AnalysisError(
                    f"Input '{selected}' not found in reduced system. "
                    f"Available: {reduced_ode.input_variables}"
                )
            return [selected]

        # Use graph's selected input if available
        if hasattr(graph, "selected_input_id") and graph.selected_input_id:
            sid = graph.selected_input_id
            # Try exact match, then prefixed variants
            for candidate in [sid, f"r_{sid}", f"f_{sid}_out"]:
                if candidate in reduced_ode.input_variables:
                    return [candidate]

        # Fall back to all inputs
        return list(reduced_ode.input_variables)

    @staticmethod
    def _resolve_probes(
        graph: SystemGraph,
        selected: str | None,
    ) -> dict:
        """Determine which probes to map to outputs."""
        if selected is not None:
            probe = graph.probes.get(selected)
            if probe is None:
                raise AnalysisError(
                    f"Probe '{selected}' not found. "
                    f"Available: {list(graph.probes.keys())}"
                )
            return {selected: probe}
        return dict(graph.probes)


class AnalysisError(Exception):
    """Raised when the static analysis pipeline cannot produce a result."""
