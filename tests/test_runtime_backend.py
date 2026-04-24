from __future__ import annotations

import unittest
from unittest.mock import patch

try:
    from app.core.models.quarter_car_model import QuarterCarParameters
    from app.core.state.app_state import AppState
    from app.services.runtime_backend import (
        BackendCapabilities,
        QuarterCarNumericRuntimeBackend,
        RuntimeStepResult,
        SymbolicStateSpaceRuntimeBackend,
    )
    from app.services.simulation_service import SimulationService

    RUNTIME_DEPS_AVAILABLE = True
except ModuleNotFoundError:
    RUNTIME_DEPS_AVAILABLE = False


@unittest.skipUnless(RUNTIME_DEPS_AVAILABLE, "Runtime backend tests require numpy/scipy runtime dependencies")
class RuntimeBackendTests(unittest.TestCase):
    def test_symbolic_runtime_matches_numeric_over_short_horizon(self):
        parameters = QuarterCarParameters()
        numeric = QuarterCarNumericRuntimeBackend(parameters)
        symbolic = SymbolicStateSpaceRuntimeBackend(parameters)
        numeric.reset()
        symbolic.reset()

        road_inputs = [0.0, 0.002, -0.001, 0.003, 0.0, -0.002]
        force_inputs = [0.0, 25.0, 50.0, 0.0, -10.0, 0.0]
        dt = 0.02

        for road_height, external_force in zip(road_inputs, force_inputs):
            numeric_step = numeric.step(dt, road_height=road_height, external_force=external_force)
            symbolic_step = symbolic.step(dt, road_height=road_height, external_force=external_force)
            for key in [
                "body_displacement",
                "wheel_displacement",
                "suspension_deflection",
                "body_acceleration",
                "tire_deflection",
            ]:
                self.assertAlmostEqual(
                    numeric_step.outputs[key],
                    symbolic_step.outputs[key],
                    delta=5e-4,
                )

    def test_simulation_service_uses_selected_runtime_backend(self):
        app_state = AppState()
        app_state.simulation.runtime_backend = "symbolic"
        service = SimulationService(app_state)
        service.reset()
        self.assertEqual(service.active_runtime_backend_mode, "symbolic")
        snapshot = service.step(app_state.simulation.sample_time)
        self.assertEqual(snapshot.runtime_backend_mode, "symbolic")
        self.assertIn("body_displacement", snapshot.outputs)

    def test_simulation_service_exposes_runtime_diagnostics_and_capabilities(self):
        app_state = AppState()
        app_state.simulation.runtime_backend = "numeric"
        service = SimulationService(app_state)
        diagnostics = service.runtime_diagnostics()
        self.assertEqual(diagnostics["active_backend_mode"], "numeric")
        self.assertEqual(diagnostics["equation_source"], "Symbolic backend")
        self.assertEqual(diagnostics["analysis_source"], "Backend-neutral static analysis")
        self.assertIn("supports_live_runtime", diagnostics["runtime_capabilities"])
        self.assertIn("runtime_backend", diagnostics["source_summary"])
        self.assertIn("backend_options", diagnostics)
        self.assertIsInstance(diagnostics["recent_events"], list)

    def test_symbolic_runtime_failure_triggers_safe_numeric_fallback(self):
        class FailingSymbolicRuntime:
            mode_id = "symbolic"
            display_name = "Symbolic (experimental)"

            def __init__(self, _parameters):
                pass

            def reset(self, *, initial_state=None):
                return None

            def set_state(self, state):
                return None

            def step(self, dt, *, road_height, external_force):
                raise RuntimeError("simulated symbolic failure")

            def current_state(self):
                from app.core.models.quarter_car_model import QuarterCarState
                return QuarterCarState()

            def capabilities(self):
                return BackendCapabilities(
                    supports_live_runtime=True,
                    supports_equations=True,
                    supports_state_space=True,
                    supports_transfer_function=True,
                    supports_traceability=True,
                    supports_fallback=True,
                )

        app_state = AppState()
        app_state.simulation.runtime_backend = "symbolic"
        with patch("app.services.simulation_service.SymbolicStateSpaceRuntimeBackend", FailingSymbolicRuntime):
            service = SimulationService(app_state)
            self.assertEqual(service.active_runtime_backend_mode, "symbolic")
            service.reset()
            service.step(app_state.simulation.sample_time)
            diagnostics = service.runtime_diagnostics()
            self.assertTrue(diagnostics["fallback_occurred"])
            self.assertEqual(service.active_runtime_backend_mode, "numeric")
            self.assertIn("failed during step", diagnostics["last_fallback_reason"])
            self.assertTrue(any(event["event"] == "fallback_to_numeric" for event in diagnostics["recent_events"]))
            self.assertTrue(diagnostics["recovery_available"])

    def test_runtime_backend_switch_preserves_output_contract(self):
        parameters = QuarterCarParameters()
        numeric = QuarterCarNumericRuntimeBackend(parameters)
        symbolic = SymbolicStateSpaceRuntimeBackend(parameters)
        numeric_step = numeric.step(0.01, road_height=0.001, external_force=0.0)
        symbolic_step = symbolic.step(0.01, road_height=0.001, external_force=0.0)
        self.assertEqual(list(numeric_step.outputs.keys()), list(symbolic_step.outputs.keys()))

    def test_backend_selection_persists_across_reset(self):
        app_state = AppState()
        app_state.simulation.runtime_backend = "symbolic"
        service = SimulationService(app_state)
        service.reset()
        self.assertEqual(service.active_runtime_backend_mode, "symbolic")
        service.reset()
        self.assertEqual(service.active_runtime_backend_mode, "symbolic")

    def test_config_change_rebuilds_runtime_and_logs_reason(self):
        app_state = AppState()
        app_state.simulation.runtime_backend = "symbolic"
        service = SimulationService(app_state)
        service.reset()
        service.step(app_state.simulation.sample_time)
        app_state.parameters.suspension_damper = 1500.0
        service.sync_config()
        diagnostics = service.runtime_diagnostics()
        self.assertEqual(service.active_runtime_backend_mode, "symbolic")
        self.assertTrue(any("config_change" in (event["note"] or "") for event in diagnostics["recent_events"]))

    def test_symbolic_runtime_can_recover_after_fallback(self):
        class FailingSymbolicRuntime:
            mode_id = "symbolic"
            display_name = "Symbolic (experimental)"

            def __init__(self, _parameters):
                pass

            def reset(self, *, initial_state=None):
                return None

            def set_state(self, state):
                return None

            def step(self, dt, *, road_height, external_force):
                raise RuntimeError("temporary symbolic failure")

            def current_state(self):
                from app.core.models.quarter_car_model import QuarterCarState
                return QuarterCarState()

            def capabilities(self):
                return BackendCapabilities(
                    supports_live_runtime=True,
                    supports_equations=True,
                    supports_state_space=True,
                    supports_transfer_function=True,
                    supports_traceability=True,
                    supports_fallback=True,
                )

        app_state = AppState()
        app_state.simulation.runtime_backend = "symbolic"
        with patch("app.services.simulation_service.SymbolicStateSpaceRuntimeBackend", FailingSymbolicRuntime):
            service = SimulationService(app_state)
            service.reset()
            service.step(app_state.simulation.sample_time)
            self.assertEqual(service.active_runtime_backend_mode, "numeric")
        service.reset()
        diagnostics = service.runtime_diagnostics()
        self.assertEqual(service.active_runtime_backend_mode, "symbolic")
        self.assertFalse(diagnostics["fallback_occurred"])
        self.assertEqual(diagnostics["symbolic_status"], "OK")

    def test_backend_switch_and_reset_keep_requested_mode_in_sync(self):
        app_state = AppState()
        service = SimulationService(app_state)
        self.assertEqual(service.runtime_diagnostics()["requested_backend_mode"], "numeric")
        app_state.simulation.runtime_backend = "symbolic"
        service.sync_config()
        self.assertEqual(service.runtime_diagnostics()["requested_backend_mode"], "symbolic")
        service.reset()
        diagnostics = service.runtime_diagnostics()
        self.assertEqual(diagnostics["requested_backend_mode"], "symbolic")
        self.assertEqual(diagnostics["active_backend_mode"], "symbolic")

    def test_backend_option_summary_exposes_experimental_symbolic_mode(self):
        app_state = AppState()
        service = SimulationService(app_state)
        diagnostics = service.runtime_diagnostics()
        options = diagnostics["backend_options"]
        self.assertIn("numeric", options)
        self.assertIn("symbolic", options)
        self.assertFalse(options["numeric"]["experimental"])
        self.assertTrue(options["symbolic"]["experimental"])

    def test_diagnostics_contract_works_for_single_mass_template(self):
        app_state = AppState()
        app_state.simulation.model_template = "single_mass"
        service = SimulationService(app_state)
        diagnostics = service.runtime_diagnostics()
        self.assertEqual(diagnostics["template_id"], "single_mass")
        self.assertEqual(diagnostics["active_backend_mode"], "numeric")
        self.assertIn("rollout_readiness", diagnostics)
        self.assertTrue(diagnostics["rollout_readiness"]["diagnostics_ready"])
        self.assertEqual(diagnostics["rollout_readiness"]["current_rollout_status"], "numeric_runtime_enabled")
        self.assertTrue(diagnostics["backend_options"]["numeric"]["enabled"])
        self.assertFalse(diagnostics["backend_options"]["symbolic"]["enabled"])

    def test_diagnostics_contract_works_for_two_mass_template(self):
        app_state = AppState()
        app_state.simulation.model_template = "two_mass"
        service = SimulationService(app_state)
        diagnostics = service.runtime_diagnostics()
        self.assertEqual(diagnostics["template_id"], "two_mass")
        self.assertEqual(diagnostics["active_backend_mode"], "numeric")
        self.assertTrue(diagnostics["rollout_readiness"]["parity_ready"])
        self.assertTrue(diagnostics["rollout_readiness"]["runtime_ready"])

    def test_quarter_car_readiness_status_is_runtime_enabled(self):
        service = SimulationService(AppState())
        diagnostics = service.runtime_diagnostics()
        self.assertEqual(diagnostics["template_id"], "quarter_car")
        self.assertEqual(diagnostics["rollout_readiness"]["current_rollout_status"], "experimental_runtime_enabled")
        self.assertTrue(diagnostics["rollout_readiness"]["backend_selectable"])
        self.assertTrue(diagnostics["rollout_readiness"]["symbolic_equations_ready"])

    def test_backend_option_summary_is_deterministic_across_simple_templates(self):
        single_mass = AppState()
        single_mass.simulation.model_template = "single_mass"
        two_mass = AppState()
        two_mass.simulation.model_template = "two_mass"
        single_diag = SimulationService(single_mass).runtime_diagnostics()
        two_diag = SimulationService(two_mass).runtime_diagnostics()
        self.assertEqual(tuple(single_diag["backend_options"].keys()), tuple(two_diag["backend_options"].keys()))
        self.assertEqual(single_diag["backend_options"]["numeric"]["experimental"], two_diag["backend_options"]["numeric"]["experimental"])
        self.assertEqual(single_diag["backend_options"]["symbolic"]["experimental"], two_diag["backend_options"]["symbolic"]["experimental"])

    def test_lifecycle_and_event_model_survive_template_switch(self):
        app_state = AppState()
        service = SimulationService(app_state)
        app_state.simulation.model_template = "single_mass"
        service.sync_config()
        diagnostics = service.runtime_diagnostics()
        self.assertEqual(diagnostics["template_id"], "single_mass")
        self.assertEqual(diagnostics["active_backend_mode"], "numeric")
        self.assertTrue(any(event["event"] == "switched_to_numeric" for event in diagnostics["recent_events"]))

    def test_requested_vs_active_backend_semantics_remain_consistent_across_templates(self):
        app_state = AppState()
        app_state.simulation.model_template = "two_mass"
        app_state.simulation.runtime_backend = "symbolic"
        service = SimulationService(app_state)
        diagnostics = service.runtime_diagnostics()
        self.assertEqual(diagnostics["requested_backend_mode"], "symbolic")
        self.assertEqual(diagnostics["active_backend_mode"], "numeric")
        self.assertEqual(diagnostics["recent_events"][-1]["template_id"], "two_mass")
        self.assertTrue(diagnostics["fallback_occurred"])

    def test_numeric_runtime_message_is_consistent_across_templates(self):
        for template_id in ("single_mass", "two_mass"):
            app_state = AppState()
            app_state.simulation.model_template = template_id
            diagnostics = SimulationService(app_state).runtime_diagnostics()
            self.assertEqual(diagnostics["active_backend_label"], "Numeric (default)")
            self.assertIn("not enabled", diagnostics["backend_options"]["symbolic"]["reason"])

    def test_repeated_backend_switching_keeps_requested_and_active_modes_consistent(self):
        app_state = AppState()
        service = SimulationService(app_state)

        app_state.simulation.runtime_backend = "symbolic"
        service.sync_config()
        self.assertEqual(service.runtime_diagnostics()["active_backend_mode"], "symbolic")

        app_state.simulation.runtime_backend = "numeric"
        service.sync_config()
        diagnostics = service.runtime_diagnostics()
        self.assertEqual(diagnostics["requested_backend_mode"], "numeric")
        self.assertEqual(diagnostics["active_backend_mode"], "numeric")
        self.assertTrue(any(event["event"] == "switched_to_numeric" for event in diagnostics["recent_events"]))

    def test_repeated_fallback_and_recovery_cycles_keep_diagnostics_consistent(self):
        class FailingSymbolicRuntime:
            mode_id = "symbolic"
            display_name = "Symbolic (experimental)"

            def __init__(self, _parameters):
                pass

            def reset(self, *, initial_state=None):
                return None

            def set_state(self, state):
                return None

            def step(self, dt, *, road_height, external_force):
                raise RuntimeError("cyclic symbolic failure")

            def current_state(self):
                from app.core.models.quarter_car_model import QuarterCarState
                return QuarterCarState()

            def capabilities(self):
                return BackendCapabilities(
                    supports_live_runtime=True,
                    supports_equations=True,
                    supports_state_space=True,
                    supports_transfer_function=True,
                    supports_traceability=True,
                    supports_fallback=True,
                )

        app_state = AppState()
        app_state.simulation.runtime_backend = "symbolic"
        with patch("app.services.simulation_service.SymbolicStateSpaceRuntimeBackend", FailingSymbolicRuntime):
            service = SimulationService(app_state)
            service.reset()
            service.step(app_state.simulation.sample_time)
            first_diag = service.runtime_diagnostics()
            self.assertEqual(first_diag["active_backend_mode"], "numeric")
            self.assertTrue(first_diag["fallback_occurred"])

        service.reset()
        recovered = service.runtime_diagnostics()
        self.assertEqual(recovered["active_backend_mode"], "symbolic")
        self.assertFalse(recovered["fallback_occurred"])

        with patch("app.services.simulation_service.SymbolicStateSpaceRuntimeBackend", FailingSymbolicRuntime):
            service.reset()
            service.step(app_state.simulation.sample_time)
            second_diag = service.runtime_diagnostics()
            self.assertEqual(second_diag["active_backend_mode"], "numeric")
            self.assertTrue(any(event["event"] == "fallback_to_numeric" for event in second_diag["recent_events"]))


if __name__ == "__main__":
    unittest.main()
