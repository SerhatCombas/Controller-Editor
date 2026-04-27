"""CompileAnalyzeService — Faz 5MVP-3.

Non-UI service that orchestrates the canvas → compile → analyze pipeline.
Designed to be called from MainWindow_v2's "Compile" button handler.

Responsibilities:
  1. Accept canvas components + wires (from ModelCanvas)
  2. Run CanvasCompiler → SystemGraph
  3. Run GenericStaticBackend → StaticAnalysisResult
  4. Update AppStateV2 with results or errors

This service is fully testable without PySide6 — the only PySide6
dependency is in the type annotations for CanvasVisualComponent and
CanvasWireConnection, which are behind TYPE_CHECKING.

Usage::

    service = CompileAnalyzeService(state)

    # From UI: "Compile" button clicked
    service.compile_and_analyze(components, wires)

    # Check state
    if state.is_analyzed:
        print(state.n_states, "states")
        print("Stable:", state.is_stable)
    elif state.compile_error:
        show_error(state.compile_error)
    elif state.analysis_error:
        show_error(state.analysis_error)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.state.app_state_v2 import AppStateV2
from app.services.canvas_compiler import CanvasCompiler
from app.services.static_analysis_backend import (
    AnalysisError,
    GenericStaticBackend,
    StaticAnalysisResult,
)

if TYPE_CHECKING:
    from app.core.graph.system_graph import SystemGraph
    from app.ui.canvas.component_system import CanvasVisualComponent, CanvasWireConnection

logger = logging.getLogger(__name__)


class CompileAnalyzeService:
    """Orchestrates compile → analyze, updating AppStateV2.

    Thread-safety: NOT thread-safe — intended for single-threaded UI use.
    The compile and analyze steps are synchronous; for large systems, a
    future version may run analysis in a worker thread.
    """

    def __init__(
        self,
        state: AppStateV2,
        *,
        compiler: CanvasCompiler | None = None,
        backend: GenericStaticBackend | None = None,
    ) -> None:
        self.state = state
        self._compiler = compiler or CanvasCompiler()
        self._backend = backend or GenericStaticBackend()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compile_and_analyze(
        self,
        components: list[CanvasVisualComponent],
        wires: list[CanvasWireConnection],
    ) -> bool:
        """Run the full compile → analyze pipeline.

        Args:
            components: Canvas visual components (from ModelCanvas._components).
            wires: Canvas wire connections (from ModelCanvas._wires).

        Returns:
            True if both compile and analysis succeeded, False otherwise.
            Check ``self.state.compile_error`` or ``self.state.analysis_error``
            for details on failure.
        """
        # Step 1: Compile canvas → SystemGraph
        graph = self._compile(components, wires)
        if graph is None:
            return False

        # Step 2: Analyze graph → StaticAnalysisResult
        return self._analyze(graph)

    def compile_only(
        self,
        components: list[CanvasVisualComponent],
        wires: list[CanvasWireConnection],
    ) -> bool:
        """Compile canvas to SystemGraph without running analysis.

        Useful when user just wants to verify the graph structure.
        """
        graph = self._compile(components, wires)
        return graph is not None

    def analyze_current(self) -> bool:
        """Re-run analysis on the current graph (e.g. after changing selection).

        Returns False if no graph is compiled or analysis fails.
        """
        if self.state.graph is None:
            self.state.set_analysis_failed("No graph compiled yet.")
            return False
        return self._analyze(self.state.graph)

    def analyze_graph(self, graph: SystemGraph) -> bool:
        """Analyze an externally-provided graph (e.g. from test fixtures).

        Sets the graph on state and runs analysis.
        """
        self.state.set_compiled(graph)
        return self._analyze(graph)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _compile(
        self,
        components: list,
        wires: list,
    ) -> SystemGraph | None:
        """Compile canvas snapshot to SystemGraph."""
        try:
            graph = self._compiler.compile(components, wires)
        except Exception as exc:
            msg = f"Compilation failed: {exc}"
            logger.warning(msg)
            self.state.set_compile_failed(msg)
            return None

        if not graph.components:
            self.state.set_compile_failed(
                "Empty graph — add components to the canvas."
            )
            return None

        self.state.set_compiled(graph)
        logger.info(
            "Compiled: %d components, %d probes",
            len(graph.components), len(graph.probes),
        )
        return graph

    def _analyze(self, graph: SystemGraph) -> bool:
        """Run static analysis on a compiled graph."""
        try:
            result = self._backend.analyze(
                graph,
                selected_input_id=self.state.analysis_config.selected_input_id,
                selected_output_id=self.state.analysis_config.selected_output_id,
            )
        except AnalysisError as exc:
            msg = str(exc)
            logger.warning("Analysis failed: %s", msg)
            self.state.set_analysis_failed(msg)
            return False
        except Exception as exc:
            msg = f"Unexpected analysis error: {exc}"
            logger.error(msg, exc_info=True)
            self.state.set_analysis_failed(msg)
            return False

        self.state.set_analyzed(result)
        logger.info(
            "Analysis complete: %d states, %d TFs, stable=%s",
            result.n_states,
            len(result.transfer_functions),
            result.is_stable if result.transfer_functions else "N/A",
        )
        return True
