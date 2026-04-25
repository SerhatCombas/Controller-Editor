"""Faz 4d-2c — DAE reducer polymorphic state classification tests.

Validates that DAEReducer's state-bearing classification is now driven by
each component's get_state_contribution() / dof_count rather than a
hard-coded class-name check.

Properties under test:
  * Component records carry a `state_contribution` snapshot field.
  * dae_reducer counts a Wheel(mass=40) as a state-bearing DoF (parity).
  * dae_reducer does NOT count a Wheel(mass=0) (transducer mode).
  * dae_reducer still counts a plain Mass (legacy behavior preserved).
  * Spring (potential energy) is NOT counted as an inertial DoF.
  * The legacy string-based fallback still works for records that omit the
    new state_contribution field (Faz 4j cleanup will remove it).
"""
import unittest

from app.core.graph.system_graph import SystemGraph
from app.core.models.mechanical import (
    Damper,
    Mass,
    MechanicalGround,
    Spring,
    Wheel,
)
from app.core.symbolic.dae_reducer import DAEReducer
from app.core.symbolic.equation_builder import EquationBuilder


def _build_minimal_graph(wheel_mass: float) -> SystemGraph:
    """Build the smallest graph that exercises the reducer:
    body --susp_spring-- wheel, both grounded via reference_ports.
    """
    g = SystemGraph()
    g.add_component(Mass("body_mass", mass=240.0))
    g.add_component(Wheel("wheel_mass", mass=wheel_mass))
    g.add_component(Spring("susp", stiffness=16000.0))
    g.add_component(MechanicalGround("ground"))
    g.connect("body_mass.port_a", "susp.port_a")
    g.connect("susp.port_b", "wheel_mass.port_a")
    g.connect("body_mass.reference_port", "ground.port")
    g.connect("wheel_mass.reference_port", "ground.port")
    return g


def _reduce(graph: SystemGraph):
    builder = EquationBuilder()
    sym_sys = builder.build(graph)
    reducer = DAEReducer()
    return sym_sys, reducer.reduce(graph, sym_sys)


class TestComponentRecordsCarryStateContribution(unittest.TestCase):
    """The equation builder snapshots get_state_contribution() into each record."""

    def test_mass_record_has_inertial_state_contribution(self):
        graph = _build_minimal_graph(wheel_mass=40.0)
        sym_sys, _ = _reduce(graph)
        records = sym_sys.metadata["component_records"]
        sc = records["body_mass"]["state_contribution"]
        self.assertEqual(sc["dof_count"], 1)
        self.assertEqual(sc["state_kind"], "inertial")
        self.assertTrue(sc["stores_inertial_energy"])

    def test_wheel_normal_record_matches_mass(self):
        """A mass>0 Wheel reports inertial state contribution just like Mass."""
        graph = _build_minimal_graph(wheel_mass=40.0)
        sym_sys, _ = _reduce(graph)
        records = sym_sys.metadata["component_records"]
        sc = records["wheel_mass"]["state_contribution"]
        self.assertEqual(sc["dof_count"], 1)
        self.assertEqual(sc["state_kind"], "inertial")
        self.assertTrue(sc["stores_inertial_energy"])

    def test_wheel_transducer_record_has_zero_dof(self):
        """A mass=0 Wheel reports dof_count=0, state_kind='transducer'."""
        graph = _build_minimal_graph(wheel_mass=0.0)
        sym_sys, _ = _reduce(graph)
        records = sym_sys.metadata["component_records"]
        sc = records["wheel_mass"]["state_contribution"]
        self.assertEqual(sc["dof_count"], 0)
        self.assertEqual(sc["state_kind"], "transducer")
        self.assertFalse(sc["stores_inertial_energy"])

    def test_dissipative_components_record_no_state(self):
        """Damper and Ground report dof_count=0 (state_contribution=None on
        the component side becomes a zero record in the snapshot)."""
        g = SystemGraph()
        g.add_component(Mass("m", mass=10.0))
        g.add_component(Damper("d", damping=100.0))
        g.add_component(MechanicalGround("ground"))
        g.connect("m.port_a", "d.port_a")
        g.connect("d.port_b", "ground.port")
        g.connect("m.reference_port", "ground.port")
        sym_sys, _ = _reduce(g)
        records = sym_sys.metadata["component_records"]
        for cid in ("d", "ground"):
            sc = records[cid]["state_contribution"]
            self.assertEqual(sc["dof_count"], 0,
                msg=f"{cid} should have dof_count=0, got {sc['dof_count']}")


class TestDAEReducerPolymorphicClassification(unittest.TestCase):
    """The reducer counts inertial DoFs via state_contribution.dof_count."""

    def test_normal_wheel_counted_as_state_bearing(self):
        """Faz 4d-2c parity: a mass=40 Wheel still produces wheel state vars."""
        graph = _build_minimal_graph(wheel_mass=40.0)
        _, reduced = _reduce(graph)
        # Both body_mass and wheel_mass should appear in the state list.
        self.assertIn("x_body_mass", reduced.state_variables)
        self.assertIn("x_wheel_mass", reduced.state_variables)
        self.assertIn("v_body_mass", reduced.state_variables)
        self.assertIn("v_wheel_mass", reduced.state_variables)

    def test_transducer_wheel_not_counted_as_state_bearing(self):
        """The headline 4d-2c behavior: a mass=0 Wheel must NOT appear in
        the reduced state list. Its DoF was 0, so the reducer skips it."""
        graph = _build_minimal_graph(wheel_mass=0.0)
        _, reduced = _reduce(graph)
        self.assertIn("x_body_mass", reduced.state_variables)
        self.assertNotIn("x_wheel_mass", reduced.state_variables)
        self.assertNotIn("v_wheel_mass", reduced.state_variables)

    def test_state_count_drops_when_wheel_becomes_transducer(self):
        """The state count for the same topology must be smaller when the
        wheel goes transducer (one DoF removed)."""
        _, normal = _reduce(_build_minimal_graph(wheel_mass=40.0))
        _, transducer = _reduce(_build_minimal_graph(wheel_mass=0.0))
        self.assertGreater(len(normal.state_variables),
                            len(transducer.state_variables))


class TestLegacyStringFallback(unittest.TestCase):
    """Records lacking the new state_contribution field still work via the
    legacy class-name check. This bridge will be removed in Faz 4j."""

    def test_legacy_record_without_state_contribution_still_classified(self):
        """Build component_records by hand, omit state_contribution, and
        verify that the reducer still treats Mass/Wheel as state-bearing
        via the string fallback path."""
        graph = _build_minimal_graph(wheel_mass=40.0)
        sym_sys, _ = _reduce(graph)

        # Strip the new field from records, simulating an older caller.
        records = sym_sys.metadata["component_records"]
        for record in records.values():
            record.pop("state_contribution", None)

        # Re-run the reducer against the stripped metadata. It must still
        # find both Mass and Wheel by class name.
        reducer = DAEReducer()
        legacy_reduced = reducer.reduce(graph, sym_sys)
        self.assertIn("x_body_mass", legacy_reduced.state_variables)
        self.assertIn("x_wheel_mass", legacy_reduced.state_variables)


if __name__ == "__main__":
    unittest.main()
