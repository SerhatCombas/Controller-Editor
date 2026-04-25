"""Faz 4f-1 — Wheel road-contact contribution tests.

When a Wheel's road_contact_port is wired up:
  * The wheel emits a 3-state constitutive description:
      x_<id>            (absolute position, inertial state from Mass)
      v_<id>            (absolute velocity, inertial state from Mass)
      x_rel_<id>_road   (road-relative displacement, potential-energy state
                         tracking the contact deformation)
    Plus a contact-force law f_<id>_road = k * x_rel + c * (v_road - v).
  * The DAE reducer accumulates the wheel's contact_stiffness into the
    K matrix and contact_damping into the C matrix, treating the wheel
    as a Spring-like branch between port_a and road_contact_port.

When road_contact_port is unconnected:
  * The wheel falls back to its pre-4f-1 Mass-equivalent behavior
    (2 states, no contact law, no K/C contribution).

Bit-for-bit parity: the legacy quarter-car (with tire_stiffness Spring +
RandomRoad coupling) produces the exact same reduced ODE matrices as a
quarter-car using Wheel's road_contact_port directly with
contact_stiffness=180000 / contact_damping=0.
"""
import unittest

import sympy

from app.core.graph.system_graph import SystemGraph
from app.core.models.mechanical import (
    Damper,
    Mass,
    MechanicalGround,
    Spring,
    Wheel,
)
from app.core.models.sources import RandomRoad
from app.core.symbolic.dae_reducer import DAEReducer
from app.core.symbolic.equation_builder import EquationBuilder


class TestWheelStatesWithRoadContact(unittest.TestCase):
    """Wheel.get_states() reflects whether the road_contact_port is wired."""

    def test_unconnected_road_contact_yields_two_states(self):
        """Pre-4f-1 behavior: free wheel reports the Mass-equivalent
        position+velocity pair, nothing else."""
        w = Wheel("w", mass=40.0)
        self.assertEqual(w.get_states(), ["x_w", "v_w"])

    def test_connected_road_contact_yields_three_states(self):
        """4f-1: a wired road_contact_port adds a road-relative
        displacement state x_rel_<id>_road that tracks tire deformation."""
        w = Wheel("w", mass=40.0)
        w.port("road_contact_port").connect_to("road_node")
        self.assertEqual(w.get_states(), ["x_w", "v_w", "x_rel_w_road"])


class TestWheelConstitutiveEquationsWithRoadContact(unittest.TestCase):
    """Wheel.constitutive_equations() emits the contact-force law."""

    def test_unconnected_keeps_legacy_equation_set(self):
        """Without an active road_contact_port the wheel emits the same
        three equations Mass produced before 4f-1."""
        w = Wheel("w", mass=40.0)
        eqs = w.constitutive_equations()
        self.assertEqual(eqs, [
            "d/dt x_w = v_w",
            "v_w = v_w_a - v_w_ref",
            "40.0 * d/dt v_w = f_w_a - f_w_ref",
        ])

    def test_connected_emits_relative_integrator_and_contact_law(self):
        """With road_contact_port wired:
        - Newton picks up f_<id>_road on the RHS.
        - A new differential equation integrates v_road - v_wheel into
          x_rel_<id>_road.
        - A contact-force law expresses f_<id>_road as
          k*x_rel + c*(v_road - v_wheel).
        """
        w = Wheel("w", mass=40.0,
                   contact_stiffness=180000.0, contact_damping=500.0)
        w.port("road_contact_port").connect_to("road_node")
        eqs = w.constitutive_equations()
        self.assertEqual(eqs, [
            "d/dt x_w = v_w",
            "v_w = v_w_a - v_w_ref",
            "d/dt x_rel_w_road = v_w_road - v_w",
            "40.0 * d/dt v_w = f_w_a - f_w_ref + f_w_road",
            "f_w_road = 180000.0 * x_rel_w_road + 500.0 * (v_w_road - v_w)",
        ])


def _build_legacy_quarter_car() -> SystemGraph:
    """Pre-4e quarter car: tire_stiffness Spring couples wheel to road."""
    g = SystemGraph()
    g.add_component(Mass("body_mass", mass=300.0))
    g.add_component(Wheel("wheel_mass", mass=40.0))
    g.add_component(Spring("suspension_spring", stiffness=15000.0))
    g.add_component(Damper("suspension_damper", damping=1200.0))
    g.add_component(Spring("tire_stiffness", stiffness=180000.0))
    g.add_component(MechanicalGround("ground"))
    g.add_component(RandomRoad(
        "road_source", amplitude=0.03, roughness=0.35,
        seed=7, vehicle_speed=6.0, dt=0.01, duration=2.0,
    ))
    g.connect("body_mass.port_a", "suspension_spring.port_a")
    g.connect("body_mass.port_a", "suspension_damper.port_a")
    g.connect("suspension_spring.port_b", "wheel_mass.port_a")
    g.connect("suspension_damper.port_b", "wheel_mass.port_a")
    g.connect("wheel_mass.port_a", "tire_stiffness.port_a")
    g.connect("tire_stiffness.port_b", "road_source.port")
    g.connect("body_mass.reference_port", "ground.port")
    g.connect("wheel_mass.reference_port", "ground.port")
    g.connect("road_source.reference_port", "ground.port")
    return g


def _build_road_contact_quarter_car() -> SystemGraph:
    """Post-4e equivalent: Wheel.road_contact_port replaces tire_stiffness.
    Wheel's contact_stiffness/contact_damping match the deleted Spring.
    """
    g = SystemGraph()
    g.add_component(Mass("body_mass", mass=300.0))
    g.add_component(Wheel("wheel_mass", mass=40.0,
                          contact_stiffness=180000.0,
                          contact_damping=0.0))
    g.add_component(Spring("suspension_spring", stiffness=15000.0))
    g.add_component(Damper("suspension_damper", damping=1200.0))
    g.add_component(MechanicalGround("ground"))
    g.add_component(RandomRoad(
        "road_source", amplitude=0.03, roughness=0.35,
        seed=7, vehicle_speed=6.0, dt=0.01, duration=2.0,
    ))
    g.connect("body_mass.port_a", "suspension_spring.port_a")
    g.connect("body_mass.port_a", "suspension_damper.port_a")
    g.connect("suspension_spring.port_b", "wheel_mass.port_a")
    g.connect("suspension_damper.port_b", "wheel_mass.port_a")
    g.connect("wheel_mass.road_contact_port", "road_source.port")
    g.connect("body_mass.reference_port", "ground.port")
    g.connect("wheel_mass.reference_port", "ground.port")
    g.connect("road_source.reference_port", "ground.port")
    return g


def _reduce(graph: SystemGraph):
    builder = EquationBuilder()
    sym_sys = builder.build(graph)
    reducer = DAEReducer()
    return reducer.reduce(graph, sym_sys)


class TestDAEReducerWheelBranch(unittest.TestCase):
    """The reducer adds the wheel's contact_stiffness/damping to the
    K and C matrices when road_contact_port is wired up."""

    def test_unconnected_wheel_contributes_nothing_to_k(self):
        """Mass-only wheel — the K matrix should reflect only the
        suspension spring (15000), not the contact_stiffness default."""
        g = SystemGraph()
        g.add_component(Mass("body", mass=300.0))
        g.add_component(Wheel("w", mass=40.0))  # default contact_stiffness=200000
        g.add_component(Spring("susp", stiffness=15000.0))
        g.add_component(MechanicalGround("ground"))
        g.connect("body.port_a", "susp.port_a")
        g.connect("susp.port_b", "w.port_a")
        g.connect("body.reference_port", "ground.port")
        g.connect("w.reference_port", "ground.port")

        red = _reduce(g)
        K = sympy.Matrix(red.stiffness_matrix)
        # Two-DOF system (body + wheel). Suspension spring lives between
        # body and wheel, so K[0,0] = K[1,1] = 15000, K[0,1] = K[1,0] =
        # -15000. Wheel's default contact_stiffness=200000 should NOT
        # appear because road_contact_port is unconnected.
        self.assertEqual(float(K[1, 1]), 15000.0,
            msg="Unconnected road_contact_port must not add contact_stiffness "
                f"to K[wheel,wheel]; got {K[1,1]}")

    def test_connected_wheel_adds_contact_stiffness_to_k(self):
        """A wired road_contact_port turns on the K-matrix branch:
        K[wheel,wheel] picks up contact_stiffness on top of the
        suspension contribution."""
        red = _reduce(_build_road_contact_quarter_car())
        K = sympy.Matrix(red.stiffness_matrix)
        # With contact_stiffness=180000 and suspension=15000, the diagonal
        # entry on the wheel side should sum to 195000 (matching the
        # legacy tire_stiffness Spring).
        self.assertEqual(float(K[1, 1]), 195000.0)

    def test_connected_wheel_adds_contact_damping_to_c(self):
        """contact_damping populates the C matrix the same way."""
        g = _build_road_contact_quarter_car()
        # Override the default contact_damping=0 with a positive value
        # to test the C-matrix branch.
        g.components["wheel_mass"].parameters["contact_damping"] = 250.0
        red = _reduce(g)
        C = sympy.Matrix(red.damping_matrix)
        # Suspension damping = 1200 -> C[0,0] = C[1,1] = 1200, C[0,1] =
        # C[1,0] = -1200. Add contact_damping=250 -> C[1,1] = 1450.
        self.assertEqual(float(C[1, 1]), 1450.0)


class TestQuarterCarTopologyParity(unittest.TestCase):
    """Bit-for-bit parity between the legacy tire_stiffness topology and
    the new road_contact_port topology, given matched parameters."""

    def test_state_variables_match(self):
        old = _reduce(_build_legacy_quarter_car())
        new = _reduce(_build_road_contact_quarter_car())
        self.assertEqual(old.state_variables, new.state_variables)

    def test_mass_matrix_matches(self):
        old = _reduce(_build_legacy_quarter_car())
        new = _reduce(_build_road_contact_quarter_car())
        self.assertEqual(
            sympy.Matrix(old.mass_matrix),
            sympy.Matrix(new.mass_matrix),
        )

    def test_stiffness_matrix_matches(self):
        """The headline parity check: replacing tire_stiffness Spring with
        Wheel.road_contact_port (contact_stiffness=180000) must yield an
        identical K matrix. Without the dae_reducer Wheel branch this
        test fails — K[wheel,wheel] would be 15000 instead of 195000."""
        old = _reduce(_build_legacy_quarter_car())
        new = _reduce(_build_road_contact_quarter_car())
        self.assertEqual(
            sympy.Matrix(old.stiffness_matrix),
            sympy.Matrix(new.stiffness_matrix),
        )

    def test_damping_matrix_matches(self):
        old = _reduce(_build_legacy_quarter_car())
        new = _reduce(_build_road_contact_quarter_car())
        self.assertEqual(
            sympy.Matrix(old.damping_matrix),
            sympy.Matrix(new.damping_matrix),
        )

    def test_input_matrix_matches(self):
        """The road input drives both systems through equivalent paths;
        the reduced B matrix must match coefficient-for-coefficient."""
        old = _reduce(_build_legacy_quarter_car())
        new = _reduce(_build_road_contact_quarter_car())
        self.assertEqual(
            sympy.Matrix(old.input_matrix),
            sympy.Matrix(new.input_matrix),
        )

    def test_state_space_a_matrix_matches(self):
        """The first-order A matrix is the ultimate parity gate — if M,
        K, C, B all match then A must too, but we assert it directly so
        a regression in _to_first_order is caught here."""
        old = _reduce(_build_legacy_quarter_car())
        new = _reduce(_build_road_contact_quarter_car())
        self.assertEqual(
            sympy.Matrix(old.first_order_a),
            sympy.Matrix(new.first_order_a),
        )

    def test_state_space_b_matrix_matches(self):
        old = _reduce(_build_legacy_quarter_car())
        new = _reduce(_build_road_contact_quarter_car())
        self.assertEqual(
            sympy.Matrix(old.first_order_b),
            sympy.Matrix(new.first_order_b),
        )


if __name__ == "__main__":
    unittest.main()
