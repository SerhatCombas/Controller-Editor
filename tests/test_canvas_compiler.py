"""Tests for CanvasCompiler — canvas drawing → SystemGraph.

All tests run without PySide6 by using lightweight duck-typed stand-ins
for CanvasVisualComponent and CanvasWireConnection.  The compiler only reads:
  • component.spec.type_key (str)
  • component.component_id (str)
  • component.assigned_io_roles (iterable of ComponentIoRole-like values)
  • wire.source_component_id / source_connector_name (str)
  • wire.target_component_id / target_connector_name (str)
"""
from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Minimal stand-ins (no PySide6 required)
# ---------------------------------------------------------------------------

class _IoRole(Enum):
    INPUT  = "input"
    OUTPUT = "output"


@dataclass
class _Spec:
    type_key: str


@dataclass
class _Component:
    component_id: str
    type_key: str
    assigned_io_roles: tuple = field(default_factory=tuple)

    @property
    def spec(self) -> _Spec:
        return _Spec(self.type_key)


@dataclass
class _Wire:
    source_component_id: str
    source_connector_name: str
    target_component_id: str
    target_connector_name: str


# Patch ComponentIoRole so the compiler's import works
import app.services.canvas_compiler as _module


class _FakeIoRole:
    INPUT  = _IoRole.INPUT
    OUTPUT = _IoRole.OUTPUT


# Monkeypatch at test load time — compiler does `from app.ui.canvas...` only inside
# compile() when checking assigned_io_roles; we inject compatible constants.
_module_ComponentIoRole_orig = None


def _install_role_shim() -> None:
    """Make ComponentIoRole and COMPONENT_CATALOG available without PySide6."""
    import sys
    import types

    if "app.ui.canvas.component_system" not in sys.modules:
        fake_mod = types.ModuleType("app.ui.canvas.component_system")

        class _FakeComponentIoRole(Enum):
            INPUT  = "input"
            OUTPUT = "output"

        fake_mod.ComponentIoRole = _FakeComponentIoRole

        from dataclasses import dataclass as _dataclass
        from collections.abc import Callable as _Callable
        from typing import Any as _Any

        @_dataclass(frozen=True)
        class _FakeVisualSpec:
            type_key: str
            core_factory: _Callable[[str], _Any] | None = None

        from app.core.models.mechanical import Damper, Mass, MechanicalGround, Spring, Wheel
        from app.core.models.sources import RandomRoad, StepForce

        fake_mod.COMPONENT_CATALOG = {
            "mass":                        _FakeVisualSpec("mass",                        lambda cid: Mass(cid, mass=1.0)),
            "wheel":                       _FakeVisualSpec("wheel",                       lambda cid: Wheel(cid, mass=1.0)),
            "translational_spring":        _FakeVisualSpec("translational_spring",        lambda cid: Spring(cid, stiffness=1.0)),
            "translational_damper":        _FakeVisualSpec("translational_damper",        lambda cid: Damper(cid, damping=1.0)),
            "tire_stiffness":              _FakeVisualSpec("tire_stiffness",              lambda cid: Spring(cid, stiffness=1.0)),
            "mechanical_reference":        _FakeVisualSpec("mechanical_reference",        lambda cid: MechanicalGround(cid)),
            "mechanical_random_reference": _FakeVisualSpec("mechanical_random_reference", lambda cid: RandomRoad(cid, amplitude=0.03, roughness=0.35, seed=7, vehicle_speed=6.0, dt=0.01, duration=15.0)),
            "ideal_force_source":          _FakeVisualSpec("ideal_force_source",          lambda cid: StepForce(cid, amplitude=1.0)),
        }

        sys.modules["app.ui.canvas.component_system"] = fake_mod

    # Ensure our _Component uses the same enum as the compiler
    global _IoRole
    from app.ui.canvas.component_system import ComponentIoRole
    _IoRole = ComponentIoRole


_install_role_shim()


from app.services.canvas_compiler import CanvasCompiler


def _component(comp_id: str, type_key: str, role: str | None = None):
    from app.ui.canvas.component_system import ComponentIoRole
    roles: tuple = ()
    if role == "input":
        roles = (ComponentIoRole.INPUT,)
    elif role == "output":
        roles = (ComponentIoRole.OUTPUT,)
    return _Component(comp_id, type_key, roles)


def _wire(src_id: str, src_conn: str, tgt_id: str, tgt_conn: str) -> _Wire:
    return _Wire(src_id, src_conn, tgt_id, tgt_conn)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestCanvasCompilerSingleMass(unittest.TestCase):
    """Mirrors the single_mass canvas layout in model_canvas.py."""

    def _build(self):
        components = [
            _component("input_force", "mechanical_random_reference", role="input"),
            _component("mass",        "mass",                        role="output"),
            _component("spring",      "translational_spring"),
            _component("damper",      "translational_damper"),
            _component("ground",      "mechanical_reference"),
        ]
        wires = [
            _wire("input_force", "output", "mass",   "top"),
            _wire("mass",        "bottom", "spring",  "R"),
            _wire("mass",        "bottom", "damper",  "R"),
            _wire("spring",      "C",      "ground",  "ref"),
            _wire("damper",      "C",      "ground",  "ref"),
        ]
        return CanvasCompiler().compile(components, wires)

    def test_all_components_present(self):
        graph = self._build()
        self.assertIn("mass",        graph.components)
        self.assertIn("spring",      graph.components)
        self.assertIn("damper",      graph.components)
        self.assertIn("ground",      graph.components)
        self.assertIn("input_force", graph.components)

    def test_mass_dof_node_shared(self):
        """mass.port_a, spring.port_a, damper.port_a, input_force.port must share a node."""
        graph = self._build()
        mass_node    = graph.get_port("mass.port_a").node_id
        spring_top   = graph.get_port("spring.port_a").node_id
        damper_top   = graph.get_port("damper.port_a").node_id
        force_port   = graph.get_port("input_force.port").node_id

        self.assertIsNotNone(mass_node)
        self.assertEqual(mass_node, spring_top,  "spring.port_a should share mass DOF node")
        self.assertEqual(mass_node, damper_top,  "damper.port_a should share mass DOF node")
        self.assertEqual(mass_node, force_port,  "input_force.port should share mass DOF node")

    def test_ground_node_shared(self):
        """spring.port_b, damper.port_b, ground.port, mass.reference_port must share ground node."""
        graph = self._build()
        gnd          = graph.get_port("ground.port").node_id
        spring_bot   = graph.get_port("spring.port_b").node_id
        damper_bot   = graph.get_port("damper.port_b").node_id
        mass_ref     = graph.get_port("mass.reference_port").node_id

        self.assertIsNotNone(gnd)
        self.assertEqual(gnd, spring_bot, "spring.port_b should be on ground node")
        self.assertEqual(gnd, damper_bot, "damper.port_b should be on ground node")
        self.assertEqual(gnd, mass_ref,   "mass.reference_port should be on ground node (implicit)")

    def test_exactly_two_nodes(self):
        """Single-mass system has exactly two distinct nodes (DOF + ground)."""
        graph = self._build()
        node_ids = {port.node_id for comp in graph.components.values()
                    for port in comp.ports if port.node_id is not None}
        self.assertEqual(len(node_ids), 2, f"Expected 2 nodes, got {sorted(node_ids)}")

    def test_selected_input_output(self):
        graph = self._build()
        self.assertEqual(graph.selected_input_id, "input_force")
        self.assertIsNotNone(graph.selected_output_id)
        self.assertIn(graph.selected_output_id, graph.probes)

    def test_probe_on_mass(self):
        graph = self._build()
        probe = graph.probes[graph.selected_output_id]
        self.assertEqual(probe.target_component_id, "mass")
        self.assertEqual(probe.quantity, "displacement")

    def test_connection_count(self):
        """Five explicit wires → five Connection records."""
        graph = self._build()
        self.assertEqual(len(graph.connections), 5)


class TestCanvasCompilerTwoMass(unittest.TestCase):
    """Mirrors the two_mass canvas layout (mass_1 → coupling → mass_2 → ground)."""

    def _build(self):
        components = [
            _component("input_force",     "mechanical_random_reference", role="input"),
            _component("mass_1",           "mass",                        role="output"),
            _component("mass_2",           "mass",                        role="output"),
            _component("spring_coupling",  "translational_spring"),
            _component("damper_coupling",  "translational_damper"),
            _component("spring_ground",    "translational_spring"),
            _component("damper_ground",    "translational_damper"),
            _component("ground",           "mechanical_reference"),
        ]
        wires = [
            _wire("input_force",    "output", "mass_1",          "top"),
            _wire("mass_1",         "bottom", "spring_coupling",  "R"),
            _wire("mass_1",         "bottom", "damper_coupling",  "R"),
            _wire("spring_coupling","C",      "mass_2",           "top"),
            _wire("damper_coupling","C",      "mass_2",           "top"),
            _wire("mass_2",         "bottom", "spring_ground",    "R"),
            _wire("mass_2",         "bottom", "damper_ground",    "R"),
            _wire("spring_ground",  "C",      "ground",           "ref"),
            _wire("damper_ground",  "C",      "ground",           "ref"),
        ]
        return CanvasCompiler().compile(components, wires)

    def test_three_distinct_nodes(self):
        """Two-mass canvas: DOF-mass1, DOF-mass2, ground → exactly 3 nodes."""
        graph = self._build()
        node_ids = {port.node_id for comp in graph.components.values()
                    for port in comp.ports if port.node_id is not None}
        self.assertEqual(len(node_ids), 3, f"Expected 3 nodes, got {sorted(node_ids)}")

    def test_mass1_dof_node(self):
        """mass_1.port_a shares a node with spring_coupling.port_a,
        damper_coupling.port_a, and input_force.port."""
        graph = self._build()
        n = graph.get_port("mass_1.port_a").node_id
        self.assertEqual(n, graph.get_port("spring_coupling.port_a").node_id)
        self.assertEqual(n, graph.get_port("damper_coupling.port_a").node_id)
        self.assertEqual(n, graph.get_port("input_force.port").node_id)

    def test_mass2_dof_node(self):
        """mass_2.port_a shares a node with spring_coupling.port_b,
        damper_coupling.port_b, spring_ground.port_a, damper_ground.port_a."""
        graph = self._build()
        n = graph.get_port("mass_2.port_a").node_id
        self.assertEqual(n, graph.get_port("spring_coupling.port_b").node_id)
        self.assertEqual(n, graph.get_port("damper_coupling.port_b").node_id)
        self.assertEqual(n, graph.get_port("spring_ground.port_a").node_id)
        self.assertEqual(n, graph.get_port("damper_ground.port_a").node_id)

    def test_ground_node(self):
        graph = self._build()
        gnd = graph.get_port("ground.port").node_id
        self.assertEqual(gnd, graph.get_port("spring_ground.port_b").node_id)
        self.assertEqual(gnd, graph.get_port("damper_ground.port_b").node_id)
        self.assertEqual(gnd, graph.get_port("mass_1.reference_port").node_id)
        self.assertEqual(gnd, graph.get_port("mass_2.reference_port").node_id)

    def test_two_probes_attached(self):
        graph = self._build()
        self.assertGreaterEqual(len(graph.probes), 2)
        probe_targets = {p.target_component_id for p in graph.probes.values()}
        self.assertIn("mass_1", probe_targets)
        self.assertIn("mass_2", probe_targets)


class TestCanvasCompilerQuarterCar(unittest.TestCase):
    """Mirrors the quarter_car canvas layout."""

    def _build(self):
        components = [
            _component("disturbance_source", "mechanical_random_reference", role="input"),
            _component("body_mass",           "mass",                        role="output"),
            _component("suspension_damper",   "translational_damper"),
            _component("suspension_spring",   "translational_spring"),
            _component("wheel",               "wheel"),
            _component("tire_stiffness",      "tire_stiffness"),
        ]
        wires = [
            _wire("body_mass",           "bottom", "suspension_damper", "R"),
            _wire("body_mass",           "bottom", "suspension_spring", "R"),
            _wire("suspension_damper",   "C",      "wheel",             "top"),
            _wire("suspension_spring",   "C",      "wheel",             "top"),
            _wire("wheel",               "bottom", "tire_stiffness",    "R"),
            _wire("disturbance_source",  "output", "tire_stiffness",    "C"),
        ]
        return CanvasCompiler().compile(components, wires)

    def test_implicit_ground_created(self):
        """Quarter-car has no explicit mechanical_reference → compiler creates one."""
        graph = self._build()
        self.assertIn("_implicit_ground", graph.components)

    def test_body_dof_node(self):
        """body_mass.port_a, suspension_spring.port_a, suspension_damper.port_a
        must all share one DOF node."""
        graph = self._build()
        n = graph.get_port("body_mass.port_a").node_id
        self.assertEqual(n, graph.get_port("suspension_spring.port_a").node_id)
        self.assertEqual(n, graph.get_port("suspension_damper.port_a").node_id)

    def test_wheel_dof_node(self):
        """wheel.port_a (top→damper.C, top→spring.C, bottom→tire.R)
        must share one DOF node."""
        graph = self._build()
        n = graph.get_port("wheel.port_a").node_id
        self.assertEqual(n, graph.get_port("suspension_spring.port_b").node_id)
        self.assertEqual(n, graph.get_port("suspension_damper.port_b").node_id)
        self.assertEqual(n, graph.get_port("tire_stiffness.port_a").node_id)

    def test_road_node(self):
        """disturbance_source.port and tire_stiffness.port_b share the road node."""
        graph = self._build()
        n = graph.get_port("tire_stiffness.port_b").node_id
        self.assertEqual(n, graph.get_port("disturbance_source.port").node_id)

    def test_ground_node_implicit_refs(self):
        """body_mass, wheel, disturbance_source reference_ports all share ground."""
        graph = self._build()
        gnd = graph.get_port("_implicit_ground.port").node_id
        self.assertEqual(gnd, graph.get_port("body_mass.reference_port").node_id)
        self.assertEqual(gnd, graph.get_port("wheel.reference_port").node_id)
        self.assertEqual(gnd, graph.get_port("disturbance_source.reference_port").node_id)

    def test_four_distinct_nodes(self):
        """Quarter-car canvas: body DOF, wheel DOF, road/tire node, ground,
        plus the unconnected wheel.road_contact_port → 5 nodes total.

        The road_contact_port was added in Faz 4d-1 as preparation for the
        Wheel/RandomRoad refactor. It is unconnected in this template (the
        existing wire structure still uses port_a/tire_stiffness), so it
        sits on its own node. Faz 4e will rewire the template to connect
        road_contact_port directly to RandomRoad and drop tire_stiffness,
        at which point the node count returns to 4 (the road_contact node
        replaces the old road/tire node).
        """
        graph = self._build()
        node_ids = {port.node_id for comp in graph.components.values()
                    for port in comp.ports if port.node_id is not None}
        self.assertEqual(len(node_ids), 5, f"Expected 5 nodes, got {sorted(node_ids)}")

    def test_selected_input_output(self):
        graph = self._build()
        self.assertEqual(graph.selected_input_id, "disturbance_source")
        self.assertIsNotNone(graph.selected_output_id)


class TestCanvasCompilerEdgeCases(unittest.TestCase):

    def test_empty_canvas(self):
        """Empty canvas compiles without error."""
        graph = CanvasCompiler().compile([], [])
        # Only the implicit ground component
        self.assertIn("_implicit_ground", graph.components)
        self.assertEqual(len(graph.probes), 0)

    def test_unknown_type_key_skipped(self):
        """Components with unknown type_key are silently ignored."""
        components = [
            _component("mystery", "unknown_type_xyz"),
            _component("mass",    "mass"),
            _component("ground",  "mechanical_reference"),
        ]
        graph = CanvasCompiler().compile(components, [])
        self.assertNotIn("mystery", graph.components)
        self.assertIn("mass", graph.components)

    def test_no_io_roles_no_probe(self):
        """A mass with no IO role gets no probe."""
        components = [
            _component("mass",   "mass"),   # no role
            _component("ground", "mechanical_reference"),
        ]
        graph = CanvasCompiler().compile(components, [])
        self.assertEqual(len(graph.probes), 0)
        self.assertIsNone(graph.selected_input_id)
        self.assertIsNone(graph.selected_output_id)

    def test_wire_with_unknown_connector_skipped(self):
        """Wires referencing non-existent connector names are skipped gracefully."""
        components = [
            _component("mass",   "mass"),
            _component("spring", "translational_spring"),
            _component("ground", "mechanical_reference"),
        ]
        wires = [
            _wire("mass", "nonexistent_port", "spring", "R"),  # bad source connector
            _wire("spring", "C", "ground", "ref"),              # good wire
        ]
        # Should compile without raising
        graph = CanvasCompiler().compile(components, wires)
        # Only the good wire creates a connection
        self.assertEqual(len(graph.connections), 1)


if __name__ == "__main__":
    unittest.main()
