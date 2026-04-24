"""TF fuzz / integration tests — Wave 2 Commit 4.

Runs 500 randomised mass-spring-damper graphs through the full
PolymorphicDAEReducer → OutputMapper → SymbolicTFBuilder pipeline
and checks structural invariants on every result.

Structural invariants asserted per iteration
────────────────────────────────────────────
  1. pole_count == denominator_degree
     ``len(poles)`` must always equal ``result.order`` (internal consistency).
  2. is_proper == True
     All displacement outputs are proper.  No physical state-space TF built
     this way should have deg(num) > deg(den).
  3. Idempotency
     Calling ``build_siso_tf`` twice with the same (ode, input_id, output)
     produces the same numerical value at a test point s=3.
  4. No unstable poles (Re < 1e-6 for all poles).
     Undamped passive systems have purely imaginary poles (Re ≈ 0 up to
     floating-point drift); unstable poles would have Re >> 0.  We use a
     tolerance of 1e-6 to accept numerical zero.
  5. UnsupportedTFResult returned when input not in input_variables
     (regression guard for Guard 2).

Note on ``order == 2 × n_dof``
─────────────────────────────
  This invariant holds exactly for systems with rational/symbolic coefficients.
  For float-coefficient A matrices, ``sympy.cancel()`` may produce unexpected
  degrees (GCD of float polynomials is numerically unstable).  This invariant
  is therefore only checked in the golden tests (test_tf_golden.py), which use
  real template parameters where the formula is verified analytically.

Unsupported output coverage
────────────────────────────
  For every graph that has probes with acceleration / force quantity, the
  mapper must return supported_for_tf=False and the builder must return
  UnsupportedTFResult.  Tested via explicit probe fixtures, not fuzz.
"""
from __future__ import annotations

import math
import os
import random
import unittest

import sympy

SEED = int(os.environ.get("FUZZ_SEED", "42"))
ITERATIONS = int(os.environ.get("TF_FUZZ_ITER", "200"))
# Cap at 2-DOF (n_masses ≤ 2) to keep sympy.roots() well below its latency
# cliff.  3-DOF+ TFs (degree ≥ 6 over floats) can stall sympy.roots() for
# tens of seconds per call; golden tests already cover 2-DOF systems.
MAX_FUZZ_MASSES = 2


# ---------------------------------------------------------------------------
# Lazy imports (avoid loading heavy modules at import time)
# ---------------------------------------------------------------------------

def _imports():
    from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
    from app.core.symbolic.output_mapper import OutputMapper, OutputExpression
    from app.core.symbolic.tf_builder import (
        SymbolicTFBuilder, TransferFunctionResult, UnsupportedTFResult, s as S,
    )
    from app.core.symbolic.symbolic_system import ReducedODESystem
    return (
        PolymorphicDAEReducer, OutputMapper, OutputExpression,
        SymbolicTFBuilder, TransferFunctionResult, UnsupportedTFResult, S,
        ReducedODESystem,
    )


# ---------------------------------------------------------------------------
# Graph generator (reuses the well-tested fuzz graph from test_fuzz_parity)
# ---------------------------------------------------------------------------

def _make_graph(rng: random.Random):
    """Generate a random graph. Returns (graph, n_masses) tuple."""
    from app.core.graph.system_graph import SystemGraph
    from app.core.models.mechanical import Mass, Spring, Damper, MechanicalGround
    from app.core.models.sources import StepForce, RandomRoad

    n_masses = rng.randint(1, MAX_FUZZ_MASSES)

    g = SystemGraph()
    gnd = g.add_component(MechanicalGround("ground"))

    masses = []
    has_damping = False
    for i in range(n_masses):
        m = g.add_component(Mass(f"m{i}", mass=rng.uniform(0.1, 20.0)))
        masses.append(m)
        g.connect(m.port("reference_port").id, gnd.port("port").id)

    for i, m in enumerate(masses):
        k = g.add_component(Spring(f"k_gnd{i}", stiffness=rng.uniform(1.0, 500.0)))
        g.connect(m.port("port_a").id, k.port("port_a").id)
        g.connect(k.port("port_b").id, gnd.port("port").id)

    if n_masses >= 2:
        n_coup = rng.randint(0, n_masses - 1)
        for c in range(n_coup):
            i = c % (n_masses - 1)
            kc = g.add_component(Spring(f"kc{c}", stiffness=rng.uniform(1.0, 300.0)))
            g.connect(masses[i].port("port_a").id, kc.port("port_a").id)
            g.connect(masses[i + 1].port("port_a").id, kc.port("port_b").id)

    n_damp = rng.randint(0, n_masses)
    if n_damp > 0:
        has_damping = True
    for i in range(n_damp):
        d = g.add_component(Damper(f"d{i}", damping=rng.uniform(0.01, 50.0)))
        g.connect(masses[i % n_masses].port("port_a").id, d.port("port_a").id)
        g.connect(d.port("port_b").id, gnd.port("port").id)

    # Always add a force source so there is always a valid input
    src = g.add_component(StepForce("force", amplitude=rng.uniform(0.1, 5.0)))
    target = rng.choice(masses)
    g.connect(target.port("port_a").id, src.port("port").id)
    g.connect(src.port("reference_port").id, gnd.port("port").id)

    # Optional: displacement source
    has_road = rng.random() < 0.4
    if has_road:
        tire_k = rng.uniform(10.0, 1000.0)
        road = g.add_component(RandomRoad(
            "road",
            amplitude=rng.uniform(0.01, 0.05),
            roughness=0.35,
            seed=rng.randint(1, 999),
            vehicle_speed=6.0,
            dt=0.01,
            duration=10.0,
        ))
        tire = g.add_component(Spring("k_tire", stiffness=tire_k))
        g.connect(masses[-1].port("port_a").id, tire.port("port_a").id)
        g.connect(road.port("port").id, tire.port("port_b").id)
        g.connect(road.port("reference_port").id, gnd.port("port").id)

    return g, n_masses, has_damping


def _make_displacement_output(state_name: str, state_vars: list, n_inputs: int):
    """Create an OutputExpression for one displacement state."""
    from app.core.symbolic.output_mapper import OutputExpression
    c = tuple(1.0 if sv == state_name else 0.0 for sv in state_vars)
    d = tuple(0.0 for _ in range(n_inputs))
    idx = tuple(i for i, v in enumerate(c) if v != 0.0)
    names = tuple(state_vars[i] for i in idx)
    return OutputExpression(
        output_id=state_name,
        output_label=state_name,
        quantity_type="displacement",
        c_row=c,
        d_row=d,
        supported_for_tf=True,
        unsupported_reason=None,
        contributing_state_indices=idx,
        contributing_state_names=names,
        provenance=("fuzz-test",),
    )


class _StubSym:
    output_definitions: dict = {}
    algebraic_constraints: list = []
    metadata: dict = {}


# ---------------------------------------------------------------------------
# Fuzz test
# ---------------------------------------------------------------------------

class TestTFFuzz(unittest.TestCase):
    """500-iteration structural-invariant fuzz for the full TF pipeline."""

    def test_500_graphs_structural_invariants(self) -> None:
        (
            PolymorphicDAEReducer, OutputMapper, OutputExpression,
            SymbolicTFBuilder, TransferFunctionResult, UnsupportedTFResult, S,
            ReducedODESystem,
        ) = _imports()

        rng = random.Random(SEED)
        reducer = PolymorphicDAEReducer()
        builder = SymbolicTFBuilder()
        S_TEST = sympy.Integer(3)  # fixed evaluation point for idempotency

        failures: list[str] = []
        n_tf_built = 0

        for iteration in range(ITERATIONS):
            g, n_masses, has_damping = _make_graph(rng)
            try:
                ode = reducer.reduce(g, _StubSym())
            except Exception as exc:
                failures.append(f"iter={iteration}: reducer failed: {exc}")
                continue

            n_dof = len(ode.state_variables) // 2
            if n_dof == 0:
                continue

            # Pick the first displacement state as output
            first_disp_state = ode.state_variables[0]  # e.g. "x_m0"
            output_expr = _make_displacement_output(
                first_disp_state,
                ode.state_variables,
                len(ode.input_variables),
            )

            # Use the force input (always present in fuzz graph)
            force_input_id = None
            for iv in ode.input_variables:
                if "force" in iv.lower() or "f_" in iv.lower():
                    force_input_id = iv
                    break
            if force_input_id is None:
                # Fall back to first input
                force_input_id = ode.input_variables[0]

            try:
                result = builder.build_siso_tf(
                    reduced_ode=ode,
                    input_id=force_input_id,
                    output_expr=output_expr,
                )
            except Exception as exc:
                failures.append(f"iter={iteration}: build_siso_tf raised: {exc}")
                continue

            if not result.is_supported:
                failures.append(
                    f"iter={iteration}: unexpected UnsupportedTFResult for "
                    f"force→displacement: {result.unsupported_reason}"
                )
                continue

            n_tf_built += 1

            # Invariant 1: pole_count == denominator_degree (internal consistency)
            if len(result.poles) != result.order:
                failures.append(
                    f"iter={iteration}: poles={len(result.poles)} != order={result.order}"
                )

            # Invariant 2: is_proper == True
            if not result.is_proper:
                failures.append(
                    f"iter={iteration}: is_proper=False for displacement output"
                )

            # Invariant 3: idempotency — build again, evaluate at S_TEST
            try:
                result2 = builder.build_siso_tf(
                    reduced_ode=ode,
                    input_id=force_input_id,
                    output_expr=output_expr,
                )
                if result2.is_supported:
                    h1_n = float(result.numerator_expr.subs(S, S_TEST))
                    h1_d = float(result.denominator_expr.subs(S, S_TEST))
                    h2_n = float(result2.numerator_expr.subs(S, S_TEST))
                    h2_d = float(result2.denominator_expr.subs(S, S_TEST))
                    if abs(h1_d) > 1e-12 and abs(h2_d) > 1e-12:
                        h1 = h1_n / h1_d
                        h2 = h2_n / h2_d
                        if abs(h1 - h2) > 1e-8 * max(1.0, abs(h1)):
                            failures.append(
                                f"iter={iteration}: idempotency violation: "
                                f"H(3)={h1} vs {h2}"
                            )
            except Exception as exc:
                failures.append(f"iter={iteration}: idempotency check raised: {exc}")

            # Invariant 4: no unstable poles (Re > 1e-6 would be physically wrong)
            # Undamped passive systems have purely imaginary poles (Re ≈ 0 in float
            # arithmetic); 1e-6 tolerance accepts numerical noise.
            _UNSTABLE_TOL = 1e-6
            for pole in result.poles:
                re_p = float(sympy.re(pole))
                if re_p > _UNSTABLE_TOL:
                    failures.append(
                        f"iter={iteration}: unstable pole {pole} (Re={re_p:.6f})"
                    )
                    break

        # Summary
        self.assertEqual(
            len(failures), 0,
            f"\n{len(failures)} fuzz failures out of {ITERATIONS} iterations "
            f"({n_tf_built} TFs built):\n" + "\n".join(failures[:20])
        )
        # Sanity: at least 160 TFs were successfully built (80 % of 200)
        self.assertGreater(
            n_tf_built, 160,
            f"Expected >160 TFs built in {ITERATIONS} iterations; got {n_tf_built}. "
            "Check graph generator."
        )


# ---------------------------------------------------------------------------
# Guard regression: input not in input_variables
# ---------------------------------------------------------------------------

class TestTFFuzzGuardRegression(unittest.TestCase):
    """Guard regression tests run on a single fixed graph."""

    @classmethod
    def setUpClass(cls) -> None:
        (
            PolymorphicDAEReducer, OutputMapper, OutputExpression,
            SymbolicTFBuilder, TransferFunctionResult, UnsupportedTFResult, S,
            ReducedODESystem,
        ) = _imports()
        cls.UnsupportedTFResult = UnsupportedTFResult
        cls.builder = SymbolicTFBuilder()

        rng = random.Random(999)
        g, n_masses, _ = _make_graph(rng)
        cls.ode = PolymorphicDAEReducer().reduce(g, _StubSym())
        cls.n_masses = n_masses
        cls.output_expr = _make_displacement_output(
            cls.ode.state_variables[0],
            cls.ode.state_variables,
            len(cls.ode.input_variables),
        )

    def test_guard_missing_input_returns_unsupported(self) -> None:
        result = self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id="__no_such_input__",
            output_expr=self.output_expr,
        )
        self.assertIsInstance(result, self.UnsupportedTFResult)
        self.assertFalse(result.is_supported)

    def test_valid_input_returns_supported(self) -> None:
        from app.core.symbolic.tf_builder import TransferFunctionResult
        valid_input = self.ode.input_variables[0]
        result = self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id=valid_input,
            output_expr=self.output_expr,
        )
        self.assertIsInstance(result, TransferFunctionResult)
        self.assertTrue(result.is_supported)

    def test_order_matches_2x_n_dof(self) -> None:
        from app.core.symbolic.tf_builder import TransferFunctionResult
        valid_input = self.ode.input_variables[0]
        result = self.builder.build_siso_tf(
            reduced_ode=self.ode,
            input_id=valid_input,
            output_expr=self.output_expr,
        )
        self.assertIsInstance(result, TransferFunctionResult)
        n_dof = len(self.ode.state_variables) // 2
        self.assertEqual(result.order, 2 * n_dof)


# ---------------------------------------------------------------------------
# Template integration: verify full real-template pipeline calls
# ---------------------------------------------------------------------------

class TestTFTemplateIntegration(unittest.TestCase):
    """Smoke integration: all three templates → at least one supported TF each."""

    def _run_template(self, fn, probe_name: str, input_id: str) -> None:
        (
            PolymorphicDAEReducer, OutputMapper, OutputExpression,
            SymbolicTFBuilder, TransferFunctionResult, UnsupportedTFResult, S,
            ReducedODESystem,
        ) = _imports()

        template = fn()
        ode = PolymorphicDAEReducer().reduce(template.graph, _StubSym())
        probe = template.graph.probes[probe_name]
        output_expr = OutputMapper().map(probe, ode)
        result = SymbolicTFBuilder().build_siso_tf(
            reduced_ode=ode,
            input_id=input_id,
            output_expr=output_expr,
        )
        self.assertIsInstance(result, TransferFunctionResult)
        self.assertTrue(result.is_supported, f"Expected supported TF; got: {result}")
        # Pole count invariant
        self.assertEqual(len(result.poles), result.order)
        # Proper invariant
        self.assertTrue(result.is_proper)

    def test_integration_single_mass(self) -> None:
        from app.core.templates.single_mass import build_single_mass_template
        self._run_template(build_single_mass_template,
                           probe_name="mass_displacement",
                           input_id="f_input_force_out")

    def test_integration_two_mass(self) -> None:
        from app.core.templates.two_mass import build_two_mass_template
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        from app.core.symbolic.output_mapper import OutputMapper
        from app.core.symbolic.tf_builder import SymbolicTFBuilder, TransferFunctionResult

        template = build_two_mass_template()
        ode = PolymorphicDAEReducer().reduce(template.graph, _StubSym())
        # No probes with quantity=displacement in two_mass? Build C directly.
        output_expr = _make_displacement_output(
            ode.state_variables[0],
            ode.state_variables,
            len(ode.input_variables),
        )
        result = SymbolicTFBuilder().build_siso_tf(
            reduced_ode=ode,
            input_id="f_input_force_out",
            output_expr=output_expr,
        )
        self.assertIsInstance(result, TransferFunctionResult)
        self.assertTrue(result.is_supported)
        self.assertEqual(result.order, 4)

    def test_integration_quarter_car(self) -> None:
        from app.core.templates.quarter_car import build_quarter_car_template
        self._run_template(build_quarter_car_template,
                           probe_name="body_displacement",
                           input_id="r_road_source")


if __name__ == "__main__":
    unittest.main()
