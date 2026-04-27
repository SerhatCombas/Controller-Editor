"""Faz 5MVP-3 — CompileAnalyzeService tests.

Tests the compile → analyze pipeline without PySide6.
Uses analyze_graph() to bypass CanvasCompiler (which needs
CanvasVisualComponent objects that are PySide6-dependent).
"""
from __future__ import annotations

import unittest

from app.core.state.app_state_v2 import AnalysisConfig, AppStateV2
from app.services.compile_analyze_service import CompileAnalyzeService
from app.services.static_analysis_backend import GenericStaticBackend
from tests.fixtures.graph_factories import (
    build_single_mass_graph,
    build_two_mass_graph,
    build_rlc_circuit_graph,
)
from tests.fixtures.minimal_wheel_road import build_wheel_road_graph


class TestAnalyzeGraphWorkflow(unittest.TestCase):
    """Test analyze_graph() — bypasses canvas compilation."""

    def setUp(self):
        self.state = AppStateV2()
        self.service = CompileAnalyzeService(self.state)

    def test_single_mass_succeeds(self):
        ok = self.service.analyze_graph(build_single_mass_graph())
        self.assertTrue(ok)
        self.assertTrue(self.state.is_compiled)
        self.assertTrue(self.state.is_analyzed)
        self.assertEqual(self.state.n_states, 2)

    def test_two_mass_succeeds(self):
        ok = self.service.analyze_graph(build_two_mass_graph())
        self.assertTrue(ok)
        self.assertEqual(self.state.n_states, 4)
        self.assertTrue(self.state.is_stable)

    def test_wheel_road_succeeds(self):
        ok = self.service.analyze_graph(build_wheel_road_graph())
        self.assertTrue(ok)
        self.assertEqual(self.state.n_states, 4)

    def test_rlc_produces_states_but_trivial_tfs(self):
        """RLC: reducer produces states but no useful TFs (known limitation)."""
        ok = self.service.analyze_graph(build_rlc_circuit_graph())
        self.assertTrue(ok)
        self.assertEqual(self.state.n_states, 2)
        # is_stable is False because TF list is empty (no poles to check)
        self.assertFalse(self.state.is_stable)


class TestAnalyzeCurrentRerun(unittest.TestCase):
    """Test analyze_current() — re-analyze with different selection."""

    def setUp(self):
        self.state = AppStateV2()
        self.service = CompileAnalyzeService(self.state)

    def test_analyze_current_without_graph_fails(self):
        ok = self.service.analyze_current()
        self.assertFalse(ok)
        self.assertIsNotNone(self.state.analysis_error)

    def test_analyze_current_reruns(self):
        self.service.analyze_graph(build_single_mass_graph())
        self.assertTrue(self.state.is_analyzed)

        # Change selection and re-analyze
        self.state.analysis_config = AnalysisConfig(
            selected_input_id="input_force",
            selected_output_id="mass_displacement",
        )
        ok = self.service.analyze_current()
        self.assertTrue(ok)
        self.assertTrue(self.state.is_analyzed)

    def test_invalid_selection_sets_analysis_error(self):
        self.service.analyze_graph(build_single_mass_graph())

        # Set an invalid input ID
        self.state.analysis_config = AnalysisConfig(
            selected_input_id="nonexistent",
        )
        ok = self.service.analyze_current()
        self.assertFalse(ok)
        self.assertIsNotNone(self.state.analysis_error)
        self.assertIn("nonexistent", self.state.analysis_error)


class TestStateTransitionsOnErrors(unittest.TestCase):
    """Error states are tracked correctly."""

    def setUp(self):
        self.state = AppStateV2()
        self.service = CompileAnalyzeService(self.state)

    def test_empty_graph_sets_analysis_error(self):
        """Graph with no inertial components → AnalysisError → state tracks it."""
        from app.core.graph.system_graph import SystemGraph
        from app.core.models.mechanical import MechanicalGround, Spring

        g = SystemGraph()
        gnd = g.add_component(MechanicalGround("g"))
        s = g.add_component(Spring("s", stiffness=10.0))
        g.connect("s.port_a", "g.port")
        g.connect("s.port_b", "g.port")

        ok = self.service.analyze_graph(g)
        self.assertFalse(ok)
        self.assertTrue(self.state.is_compiled)  # Graph is valid
        self.assertFalse(self.state.is_analyzed)
        self.assertIn("No state variables", self.state.analysis_error)

    def test_recompile_clears_old_analysis(self):
        """Compiling a new graph clears the old analysis result."""
        self.service.analyze_graph(build_single_mass_graph())
        self.assertTrue(self.state.is_analyzed)
        old_result = self.state.analysis_result

        # Recompile with a different graph
        self.service.analyze_graph(build_two_mass_graph())
        self.assertIsNot(self.state.analysis_result, old_result)
        self.assertEqual(self.state.n_states, 4)


class TestCompileOnlyPath(unittest.TestCase):
    """compile_only() doesn't run analysis."""

    def test_compile_only_sets_graph(self):
        """analyze_graph → compile_only would need canvas objects.
        Test via direct state manipulation instead."""
        state = AppStateV2()
        graph = build_single_mass_graph()
        state.set_compiled(graph)
        self.assertTrue(state.is_compiled)
        self.assertFalse(state.is_analyzed)


class TestCustomBackendInjection(unittest.TestCase):
    """Custom backend can be injected for testing."""

    def test_custom_backend(self):
        state = AppStateV2()
        backend = GenericStaticBackend(simplification_mode="raw")
        service = CompileAnalyzeService(state, backend=backend)
        ok = service.analyze_graph(build_single_mass_graph())
        self.assertTrue(ok)
        self.assertEqual(state.n_states, 2)


if __name__ == "__main__":
    unittest.main()
