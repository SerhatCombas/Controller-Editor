"""PRIMARY cutover verification — Wave 2 Commit 5.

Confirms that DEFAULT_FLAGS.parity_mode is ParityMode.PRIMARY and that
the ReducerParityHarness returns the polymorphic reducer's result under
the new default.

Gate checklist verified before cutover
───────────────────────────────────────
  Gate 1: Template parity (single_mass, two_mass, quarter_car) zero divergence
           → test_fuzz_parity.py::test_quarter_car_zero_divergence
  Gate 2: TF golden tests passing
           → test_tf_golden.py (36 tests)
  Gate 3: 200-iteration TF fuzz, zero structural anomalies
           → test_tf_fuzz.py::TestTFFuzz
  Gate 4: OutputMapper parity (55 unit tests)
           → test_output_mapper.py
  Gate 5: User-built topology parity (covered by fuzz parity)
           → test_fuzz_parity.py::test_1000_random_graphs_zero_divergence
  Gate 6: Unsupported outputs return UnsupportedTFResult, never wrong TF
           → test_tf_golden.py (QC_13–QC_16, SM_10–SM_12)
"""
from __future__ import annotations

import unittest
import dataclasses

from app.core.state.feature_flags import DEFAULT_FLAGS, FeatureFlags, ParityMode
from app.core.symbolic.reducer_parity_harness import ReducerParityHarness
from app.core.symbolic.symbolic_system import SymbolicSystem, ReducedODESystem
from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
from tests.fixtures.graph_factories import (
    build_single_mass_template_def,
    build_two_mass_template_def,
)
from tests.fixtures.minimal_wheel_road import build_wheel_road_graph
from app.core.templates.template_definition import TemplateDefinition


def _build_quarter_car_fixture():
    graph = build_wheel_road_graph()
    return TemplateDefinition(
        id="quarter_car", name="Quarter-Car Suspension", graph=graph,
        default_input_id="road_source", default_output_id="body_displacement",
    )


# ---------------------------------------------------------------------------
# Stub SymbolicSystem (bypasses EquationBuilder)
# ---------------------------------------------------------------------------

class _StubSym(SymbolicSystem):
    pass


# ---------------------------------------------------------------------------
# Flag-state tests
# ---------------------------------------------------------------------------

class TestDefaultFlagsPrimary(unittest.TestCase):
    """DEFAULT_FLAGS.parity_mode must be PRIMARY after Wave 2 cutover."""

    def test_default_parity_mode_is_primary(self) -> None:
        self.assertEqual(
            DEFAULT_FLAGS.parity_mode, ParityMode.PRIMARY,
            "Wave 2 cutover: DEFAULT_FLAGS.parity_mode must be PRIMARY. "
            "All 6 gate conditions have been confirmed before this assertion."
        )

    def test_default_flags_is_frozen(self) -> None:
        """Frozen dataclass — cannot accidentally mutate."""
        with self.assertRaises((TypeError, AttributeError)):
            DEFAULT_FLAGS.parity_mode = ParityMode.OFF  # type: ignore[misc]

    def test_replace_produces_different_instance(self) -> None:
        shadow = dataclasses.replace(DEFAULT_FLAGS, parity_mode=ParityMode.SHADOW)
        self.assertEqual(shadow.parity_mode, ParityMode.SHADOW)
        self.assertEqual(DEFAULT_FLAGS.parity_mode, ParityMode.PRIMARY)


# ---------------------------------------------------------------------------
# PRIMARY-mode harness behaviour
# ---------------------------------------------------------------------------

class TestHarnessPrimaryMode(unittest.TestCase):
    """Harness with PRIMARY flags returns the polymorphic reducer's result."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.template = build_single_mass_template_def()

        # Build the expected polymorphic result independently
        cls.poly_reducer = PolymorphicDAEReducer()
        cls.poly_expected = cls.poly_reducer.reduce(cls.template.graph, _StubSym())

        # Build using the harness in PRIMARY mode
        cls.harness = ReducerParityHarness(flags=DEFAULT_FLAGS)
        cls.ode, cls.report = cls.harness.reduce(
            cls.template.graph, _StubSym(), graph_id="cutover_single_mass"
        )

    def test_harness_uses_primary_mode(self) -> None:
        self.assertEqual(self.harness._flags.parity_mode, ParityMode.PRIMARY)

    def test_returns_ode_system(self) -> None:
        self.assertIsInstance(self.ode, ReducedODESystem)

    def test_ode_state_variables_match_polymorphic(self) -> None:
        self.assertEqual(self.ode.state_variables, self.poly_expected.state_variables)

    def test_ode_input_variables_match_polymorphic(self) -> None:
        self.assertEqual(self.ode.input_variables, self.poly_expected.input_variables)

    def test_ode_a_matrix_matches_polymorphic(self) -> None:
        for r_a, r_p in zip(self.ode.first_order_a, self.poly_expected.first_order_a):
            for va, vp in zip(r_a, r_p):
                self.assertAlmostEqual(va, vp, places=12,
                    msg="A matrix mismatch in PRIMARY mode result")

    def test_ode_b_matrix_matches_polymorphic(self) -> None:
        for r_a, r_p in zip(self.ode.first_order_b, self.poly_expected.first_order_b):
            for va, vp in zip(r_a, r_p):
                self.assertAlmostEqual(va, vp, places=12,
                    msg="B matrix mismatch in PRIMARY mode result")

    def test_report_is_returned(self) -> None:
        """PRIMARY mode always returns a report (may be degraded if legacy failed)."""
        self.assertIsNotNone(self.report)

    def test_report_parity_mode_is_primary(self) -> None:
        self.assertEqual(self.report.parity_mode, "primary")

    def test_report_poly_state_variables_correct(self) -> None:
        """Report captures the polymorphic reducer's state variables."""
        self.assertEqual(
            self.report.poly_state_variables,
            self.poly_expected.state_variables,
        )


# ---------------------------------------------------------------------------
# PRIMARY mode: degraded report when legacy fails
# ---------------------------------------------------------------------------

class TestHarnessPrimaryModeDegradedReport(unittest.TestCase):
    """When legacy reducer raises, PRIMARY mode still returns poly result."""

    def test_primary_survives_legacy_failure(self) -> None:
        """Use a broken legacy reducer that always raises."""
        class _BrokenLegacy:
            def reduce(self, *args, **kwargs):
                raise RuntimeError("Simulated legacy reducer failure")

        template = build_single_mass_template_def()
        flags = FeatureFlags(parity_mode=ParityMode.PRIMARY)
        harness = ReducerParityHarness(
            flags=flags,
            legacy_reducer=_BrokenLegacy(),
        )
        ode, report = harness.reduce(template.graph, _StubSym(), graph_id="degraded")

        # Should still return the polymorphic result
        self.assertIsInstance(ode, ReducedODESystem)
        self.assertGreater(len(ode.state_variables), 0)

        # Report should indicate degradation
        self.assertIsNotNone(report)
        self.assertTrue(
            any("Legacy reducer unavailable" in issue for issue in report.issues),
            f"Expected degraded report; got issues: {report.issues}"
        )
        self.assertTrue(report.metadata.get("primary_degraded", False))


# ---------------------------------------------------------------------------
# DEFAULT_FLAGS end-to-end: verify full pipeline uses polymorphic result
# ---------------------------------------------------------------------------

class TestDefaultFlagsEndToEnd(unittest.TestCase):
    """End-to-end: default harness on all three templates, PRIMARY result correct."""

    def _run_template(self, fn, expected_n_dof: int) -> None:
        template = fn()
        harness = ReducerParityHarness()  # uses DEFAULT_FLAGS = PRIMARY
        ode, report = harness.reduce(template.graph, _StubSym())

        # Verify we got the polymorphic result (correct DOF count)
        self.assertIsInstance(ode, ReducedODESystem)
        n_dof = len(ode.state_variables) // 2
        self.assertEqual(n_dof, expected_n_dof,
                         f"Expected {expected_n_dof} DOFs, got {n_dof} "
                         f"(state_vars={ode.state_variables})")
        self.assertIsNotNone(report)

    def test_single_mass_1dof(self) -> None:
        self._run_template(build_single_mass_template_def, expected_n_dof=1)

    def test_two_mass_2dof(self) -> None:
        self._run_template(build_two_mass_template_def, expected_n_dof=2)

    def test_quarter_car_2dof(self) -> None:
        self._run_template(_build_quarter_car_fixture, expected_n_dof=2)


if __name__ == "__main__":
    unittest.main()
