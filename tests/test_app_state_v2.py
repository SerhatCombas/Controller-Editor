"""Faz 5MVP-2 — AppStateV2 unit tests.

Tests the generic application state dataclass and its state transitions:
  - Default construction (blank workspace)
  - Compile → analyze lifecycle
  - Error state tracking
  - Reset behavior
  - Integration with GenericStaticBackend
"""
from __future__ import annotations

import unittest

from app.core.state.app_state_v2 import AnalysisConfig, AppStateV2, ControllerConfigV2
from app.services.static_analysis_backend import GenericStaticBackend, AnalysisError
from tests.fixtures.graph_factories import build_single_mass_graph, build_two_mass_graph


class TestAppStateV2Defaults(unittest.TestCase):
    """Fresh AppStateV2 represents a blank workspace."""

    def setUp(self):
        self.state = AppStateV2()

    def test_default_graph_is_none(self):
        self.assertIsNone(self.state.graph)

    def test_default_analysis_result_is_none(self):
        self.assertIsNone(self.state.analysis_result)

    def test_default_is_compiled_false(self):
        self.assertFalse(self.state.is_compiled)

    def test_default_is_analyzed_false(self):
        self.assertFalse(self.state.is_analyzed)

    def test_default_n_states_zero(self):
        self.assertEqual(self.state.n_states, 0)

    def test_default_n_inputs_zero(self):
        self.assertEqual(self.state.n_inputs, 0)

    def test_default_n_outputs_zero(self):
        self.assertEqual(self.state.n_outputs, 0)

    def test_default_is_stable_none(self):
        self.assertIsNone(self.state.is_stable)

    def test_default_compile_error_none(self):
        self.assertIsNone(self.state.compile_error)

    def test_default_analysis_error_none(self):
        self.assertIsNone(self.state.analysis_error)

    def test_default_controller_disabled(self):
        self.assertFalse(self.state.controller.enabled)
        self.assertEqual(self.state.controller.kp, 0.0)

    def test_default_analysis_config_empty(self):
        self.assertIsNone(self.state.analysis_config.selected_input_id)
        self.assertIsNone(self.state.analysis_config.selected_output_id)


class TestAppStateV2Lifecycle(unittest.TestCase):
    """Compile → analyze → reset lifecycle."""

    def setUp(self):
        self.state = AppStateV2()
        self.graph = build_single_mass_graph()

    def test_set_compiled_marks_is_compiled(self):
        self.state.set_compiled(self.graph)
        self.assertTrue(self.state.is_compiled)
        self.assertIsNotNone(self.state.graph)

    def test_set_compiled_clears_analysis(self):
        """A new compile invalidates previous analysis."""
        backend = GenericStaticBackend()
        result = backend.analyze(self.graph)
        self.state.set_analyzed(result)
        self.assertTrue(self.state.is_analyzed)

        # Re-compile with a different graph
        new_graph = build_two_mass_graph()
        self.state.set_compiled(new_graph)
        self.assertTrue(self.state.is_compiled)
        self.assertFalse(self.state.is_analyzed)  # Analysis cleared

    def test_set_compile_failed(self):
        self.state.set_compile_failed("No components on canvas")
        self.assertFalse(self.state.is_compiled)
        self.assertEqual(self.state.compile_error, "No components on canvas")
        self.assertIsNone(self.state.graph)

    def test_set_analyzed(self):
        self.state.set_compiled(self.graph)
        backend = GenericStaticBackend()
        result = backend.analyze(self.graph)
        self.state.set_analyzed(result)
        self.assertTrue(self.state.is_analyzed)
        self.assertEqual(self.state.n_states, 2)
        self.assertTrue(self.state.is_stable)

    def test_set_analysis_failed(self):
        self.state.set_compiled(self.graph)
        self.state.set_analysis_failed("No state variables")
        self.assertFalse(self.state.is_analyzed)
        self.assertEqual(self.state.analysis_error, "No state variables")

    def test_reset_clears_everything(self):
        self.state.set_compiled(self.graph)
        backend = GenericStaticBackend()
        self.state.set_analyzed(backend.analyze(self.graph))
        self.state.analysis_config.selected_input_id = "f_input_force_out"

        self.state.reset()

        self.assertFalse(self.state.is_compiled)
        self.assertFalse(self.state.is_analyzed)
        self.assertIsNone(self.state.graph)
        self.assertIsNone(self.state.analysis_result)
        self.assertIsNone(self.state.analysis_config.selected_input_id)


class TestAppStateV2Integration(unittest.TestCase):
    """Full compile → analyze → inspect workflow."""

    def test_single_mass_full_workflow(self):
        state = AppStateV2()
        graph = build_single_mass_graph()

        # Step 1: Compile
        state.set_compiled(graph)
        self.assertTrue(state.is_compiled)

        # Step 2: Analyze
        backend = GenericStaticBackend()
        result = backend.analyze(graph)
        state.set_analyzed(result)

        # Step 3: Inspect
        self.assertTrue(state.is_analyzed)
        self.assertEqual(state.n_states, 2)
        self.assertEqual(state.n_inputs, 1)
        self.assertGreater(state.n_outputs, 0)
        self.assertTrue(state.is_stable)

    def test_two_mass_full_workflow(self):
        state = AppStateV2()
        graph = build_two_mass_graph()

        state.set_compiled(graph)
        result = GenericStaticBackend().analyze(graph)
        state.set_analyzed(result)

        self.assertEqual(state.n_states, 4)
        self.assertTrue(state.is_stable)

    def test_analysis_config_selection(self):
        state = AppStateV2()
        graph = build_single_mass_graph()
        state.set_compiled(graph)

        state.analysis_config = AnalysisConfig(
            selected_input_id="input_force",
            selected_output_id="mass_displacement",
        )
        self.assertEqual(state.analysis_config.selected_input_id, "input_force")
        self.assertEqual(state.analysis_config.selected_output_id, "mass_displacement")


class TestControllerConfigV2(unittest.TestCase):
    """ControllerConfigV2 dataclass."""

    def test_default_values(self):
        cfg = ControllerConfigV2()
        self.assertEqual(cfg.kp, 0.0)
        self.assertEqual(cfg.ki, 0.0)
        self.assertEqual(cfg.kd, 0.0)
        self.assertFalse(cfg.enabled)

    def test_custom_values(self):
        cfg = ControllerConfigV2(kp=100.0, ki=10.0, kd=50.0, enabled=True)
        self.assertEqual(cfg.kp, 100.0)
        self.assertTrue(cfg.enabled)


if __name__ == "__main__":
    unittest.main()
