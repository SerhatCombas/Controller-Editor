"""Faz 4h — Symbolic-backend linearization-warning tests.

Mode B Wheel (Faz 4g) emits a `max(0, ...)` contact-force law that the
dae_reducer's parameter-driven K/C accumulation silently flattens. Faz
4h surfaces this with a logged warning + a metadata field on the
symbolic backends. These tests pin both behaviors down.
"""
import logging
import unittest

from app.core.graph.system_graph import SystemGraph
from app.core.models.mechanical import (
    Damper,
    Mass,
    MechanicalGround,
    Spring,
    Wheel,
)
from app.core.models.sources import RandomRoad
from app.core.symbolic.linearization_warnings import (
    METADATA_KEY_LINEARIZED_MODE_B,
    detect_linearized_mode_b_wheels,
    emit_linearization_warning,
)


def _build_minimal_graph(*, contact_mode: str, wire_road_contact: bool) -> SystemGraph:
    """Smallest graph that lets the helper inspect a Wheel."""
    g = SystemGraph()
    g.add_component(Mass("body", mass=300.0))
    g.add_component(Wheel(
        "w", mass=40.0,
        contact_stiffness=180000.0, contact_damping=0.0,
        contact_mode=contact_mode,
    ))
    g.add_component(MechanicalGround("ground"))
    g.add_component(RandomRoad(
        "road", amplitude=0.03, roughness=0.35,
        seed=7, vehicle_speed=6.0, dt=0.01, duration=2.0,
    ))
    g.connect("body.reference_port", "ground.port")
    g.connect("w.reference_port", "ground.port")
    g.connect("road.reference_port", "ground.port")
    if wire_road_contact:
        g.connect("w.road_contact_port", "road.port")
    return g


class TestDetectLinearizedModeBWheels(unittest.TestCase):
    """detect_linearized_mode_b_wheels(graph) returns the IDs of wheels
    that satisfy BOTH (contact_mode=='dynamic_contact') AND
    (road_contact_port is wired)."""

    def test_empty_graph_returns_empty_list(self):
        self.assertEqual(detect_linearized_mode_b_wheels(SystemGraph()), [])

    def test_mode_a_wheel_is_not_flagged(self):
        """A kinematic_follow wheel is exact in the linear reducer; nothing
        gets silently linearized, so the helper returns []."""
        graph = _build_minimal_graph(
            contact_mode="kinematic_follow", wire_road_contact=True,
        )
        self.assertEqual(detect_linearized_mode_b_wheels(graph), [])

    def test_unwired_mode_b_wheel_is_not_flagged(self):
        """A Mode B wheel without an active road_contact_port emits no
        contact-force law to begin with — there is nothing to linearize,
        so no warning."""
        graph = _build_minimal_graph(
            contact_mode="dynamic_contact", wire_road_contact=False,
        )
        self.assertEqual(detect_linearized_mode_b_wheels(graph), [])

    def test_wired_mode_b_wheel_is_flagged(self):
        """The headline trigger condition: dynamic_contact + wired road
        port → component ID appears in the result list."""
        graph = _build_minimal_graph(
            contact_mode="dynamic_contact", wire_road_contact=True,
        )
        self.assertEqual(detect_linearized_mode_b_wheels(graph), ["w"])

    def test_multiple_wheels_returns_only_triggers_in_graph_order(self):
        """Mixed graph: Mode A wired + Mode B wired + Mode B unwired.
        Only the wired Mode B wheel should appear, and the order should
        match component-insertion order."""
        g = SystemGraph()
        g.add_component(Wheel("a_wired", mass=40.0))  # Mode A default
        g.add_component(Wheel("b_wired", mass=40.0,
                               contact_mode="dynamic_contact"))
        g.add_component(Wheel("b_free", mass=40.0,
                               contact_mode="dynamic_contact"))
        g.add_component(MechanicalGround("ground"))
        g.add_component(RandomRoad(
            "road", amplitude=0.03, roughness=0.35,
            seed=7, vehicle_speed=6.0, dt=0.01, duration=2.0,
        ))
        g.connect("a_wired.reference_port", "ground.port")
        g.connect("b_wired.reference_port", "ground.port")
        g.connect("b_free.reference_port", "ground.port")
        g.connect("road.reference_port", "ground.port")
        g.connect("a_wired.road_contact_port", "road.port")
        g.connect("b_wired.road_contact_port", "road.port")
        # b_free's road_contact_port intentionally left unwired
        self.assertEqual(detect_linearized_mode_b_wheels(g), ["b_wired"])


class TestEmitLinearizationWarning(unittest.TestCase):
    """emit_linearization_warning logs at WARNING level when the trigger
    list is non-empty and is a no-op when it is empty."""

    def test_empty_list_emits_no_log(self):
        with self.assertLogs("app.core.symbolic.linearization_warnings",
                              level="WARNING") as cm:
            emit_linearization_warning([], backend_label="Test")
            # Force at least one record to exist so assertLogs doesn't fail;
            # this confirms our call did NOT add anything above it.
            logging.getLogger(
                "app.core.symbolic.linearization_warnings"
            ).warning("sentinel")
        self.assertEqual(len(cm.records), 1)
        self.assertEqual(cm.records[0].getMessage(), "sentinel")

    def test_non_empty_list_emits_one_warning_with_label_and_ids(self):
        with self.assertLogs("app.core.symbolic.linearization_warnings",
                              level="WARNING") as cm:
            emit_linearization_warning(
                ["w1", "w2"], backend_label="MyBackend",
            )
        self.assertEqual(len(cm.records), 1)
        msg = cm.records[0].getMessage()
        self.assertIn("MyBackend", msg)
        self.assertIn("'w1'", msg)
        self.assertIn("'w2'", msg)


class TestSymbolicStateSpaceBackendMetadata(unittest.TestCase):
    """SymbolicStateSpaceBackend.get_state_space() exposes the trigger
    list under metadata[linearized_contact_mode_b]."""

    def test_default_template_yields_empty_trigger_list(self):
        """The legacy quarter-car template ships in Mode A; the symbolic
        backend's metadata list must be empty so UI panels render no
        badge for a default-configured template."""
        from app.services.simulation_backend import SymbolicStateSpaceBackend
        result = SymbolicStateSpaceBackend().get_state_space(
            input_channel="road_displacement",
        )
        self.assertEqual(
            result.metadata.get(METADATA_KEY_LINEARIZED_MODE_B), [],
        )


class TestSymbolicStateSpaceRuntimeBackendMetadata(unittest.TestCase):
    """SymbolicStateSpaceRuntimeBackend stashes the trigger list on
    self.metadata so simulation-service / UI code can read it."""

    def test_default_template_runtime_yields_empty_trigger_list(self):
        from app.core.models.quarter_car_model import QuarterCarParameters
        from app.services.runtime_backend import SymbolicStateSpaceRuntimeBackend
        backend = SymbolicStateSpaceRuntimeBackend(QuarterCarParameters())
        self.assertEqual(
            backend.metadata.get(METADATA_KEY_LINEARIZED_MODE_B), [],
        )


if __name__ == "__main__":
    unittest.main()
