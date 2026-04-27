"""Tests for Wave 1 InputRouter.

Verifies:
- RoutingResult / SourceRoute dataclass construction
- InputRouter.route() identifies sources via get_source_descriptor()
- Force vs displacement source classification
- Ground-node DOF resolution (driven_dof_index == -1 when node absent from index)
- Passive systems (no sources) produce empty RoutingResult
- Router does NOT inspect class names — only SourceDescriptor
- Separation contract: router returns data structures, no sympy algebra

Tests use lightweight stub graphs where possible.  Heavier integration tests
use the existing single_mass template to confirm end-to-end wiring.
"""
from __future__ import annotations

import unittest


# ---------------------------------------------------------------------------
# Lightweight stub helpers
# ---------------------------------------------------------------------------

class _StubPort:
    def __init__(self, name: str, node_id: str | None = None):
        self.name = name
        self.node_id = node_id


class _StubComponent:
    """Minimal stand-in for BaseComponent for router tests."""

    def __init__(self, comp_id: str, descriptor=None):
        self.id = comp_id
        self._descriptor = descriptor
        self._ports: dict[str, _StubPort] = {}

    def add_port(self, name: str, node_id: str | None = None) -> _StubPort:
        p = _StubPort(name, node_id)
        self._ports[name] = p
        return p

    def port(self, name: str) -> _StubPort:
        if name not in self._ports:
            raise KeyError(name)
        return self._ports[name]

    def get_source_descriptor(self):
        return self._descriptor


class _StubGraph:
    """Minimal stand-in for SystemGraph for router tests."""

    def __init__(self):
        self.components: dict[str, _StubComponent] = {}

    def add(self, comp: _StubComponent) -> _StubComponent:
        self.components[comp.id] = comp
        return comp


# ---------------------------------------------------------------------------
# RoutingResult / SourceRoute dataclass tests
# ---------------------------------------------------------------------------

class TestRoutingDataclasses(unittest.TestCase):

    def _make_route(self, **kwargs):
        from app.core.symbolic.input_router import SourceRoute
        defaults = dict(
            component_id="sf_1",
            source_kind="force",
            driven_node_id="node_a",
            reference_node_id="ground",
            input_variable_name="f_sf_1_out",
            amplitude_parameter="amplitude",
            driven_dof_index=0,
        )
        defaults.update(kwargs)
        return SourceRoute(**defaults)

    def test_source_route_construction(self):
        from app.core.symbolic.input_router import SourceRoute
        r = self._make_route()
        self.assertEqual(r.component_id, "sf_1")
        self.assertEqual(r.source_kind, "force")
        self.assertEqual(r.driven_dof_index, 0)

    def test_source_route_frozen(self):
        r = self._make_route()
        with self.assertRaises((AttributeError, TypeError)):
            r.driven_dof_index = 99  # type: ignore[misc]

    def test_routing_result_properties(self):
        from app.core.symbolic.input_router import RoutingResult, SourceRoute
        r = SourceRoute(
            component_id="sf_1",
            source_kind="force",
            driven_node_id="node_a",
            reference_node_id=None,
            input_variable_name="f_out",
            amplitude_parameter="amplitude",
            driven_dof_index=0,
        )
        result = RoutingResult(
            routes=(r,),
            node_index={"node_a": 0},
            force_sources=(r,),
            displacement_sources=(),
        )
        self.assertEqual(result.input_count, 1)
        self.assertTrue(result.has_sources())

    def test_routing_result_empty(self):
        from app.core.symbolic.input_router import RoutingResult
        result = RoutingResult(routes=(), node_index={})
        self.assertEqual(result.input_count, 0)
        self.assertFalse(result.has_sources())


# ---------------------------------------------------------------------------
# InputRouter.route() with stub graphs
# ---------------------------------------------------------------------------

class TestInputRouterStub(unittest.TestCase):

    def test_no_sources_yields_empty_result(self):
        """All passive components → empty RoutingResult."""
        from app.core.symbolic.input_router import InputRouter

        graph = _StubGraph()
        passive = _StubComponent("mass_1", descriptor=None)
        passive.add_port("port_a", "node_a")
        graph.add(passive)

        router = InputRouter()
        result = router.route(graph, {"node_a": 0})

        self.assertFalse(result.has_sources())
        self.assertEqual(result.input_count, 0)
        self.assertEqual(result.force_sources, ())
        self.assertEqual(result.displacement_sources, ())

    def test_single_force_source_identified(self):
        from app.core.symbolic.input_router import InputRouter
        from app.core.base.source_descriptor import SourceDescriptor

        graph = _StubGraph()
        src = _StubComponent(
            "sf_1",
            descriptor=SourceDescriptor(
                kind="force",
                driven_port_name="port",
                reference_port_name="reference_port",
                input_variable_name="f_sf_1_out",
                amplitude_parameter="amplitude",
            ),
        )
        src.add_port("port", "node_a")
        src.add_port("reference_port", "ground")
        graph.add(src)

        router = InputRouter()
        result = router.route(graph, {"node_a": 0})

        self.assertEqual(result.input_count, 1)
        self.assertEqual(len(result.force_sources), 1)
        self.assertEqual(len(result.displacement_sources), 0)

        route = result.force_sources[0]
        self.assertEqual(route.component_id, "sf_1")
        self.assertEqual(route.source_kind, "force")
        self.assertEqual(route.driven_node_id, "node_a")
        self.assertEqual(route.driven_dof_index, 0)
        self.assertEqual(route.input_variable_name, "f_sf_1_out")

    def test_displacement_source_classified_correctly(self):
        from app.core.symbolic.input_router import InputRouter
        from app.core.base.source_descriptor import SourceDescriptor

        graph = _StubGraph()
        src = _StubComponent(
            "rr_1",
            descriptor=SourceDescriptor(
                kind="displacement",
                driven_port_name="port",
                reference_port_name="reference_port",
                input_variable_name="r_rr_1",
                amplitude_parameter="amplitude",
            ),
        )
        src.add_port("port", "node_wheel")
        src.add_port("reference_port", "ground")
        graph.add(src)

        router = InputRouter()
        result = router.route(graph, {"node_wheel": 0})

        self.assertEqual(len(result.force_sources), 0)
        self.assertEqual(len(result.displacement_sources), 1)
        self.assertEqual(result.displacement_sources[0].source_kind, "displacement")

    def test_ground_driven_node_gets_minus_one_index(self):
        """Source drives a node that is not in node_index (ground/eliminated)."""
        from app.core.symbolic.input_router import InputRouter
        from app.core.base.source_descriptor import SourceDescriptor

        graph = _StubGraph()
        src = _StubComponent(
            "sf_bad",
            descriptor=SourceDescriptor(
                kind="force",
                driven_port_name="port",
                reference_port_name="reference_port",
                input_variable_name="f_bad",
                amplitude_parameter="amplitude",
            ),
        )
        src.add_port("port", "ground")  # driven node IS the ground — unusual but shouldn't crash
        src.add_port("reference_port", "ground")
        graph.add(src)

        router = InputRouter()
        result = router.route(graph, {})  # empty node_index → ground eliminated

        self.assertEqual(result.input_count, 1)
        self.assertEqual(result.routes[0].driven_dof_index, -1)  # ground = no DOF

    def test_mixed_sources_and_passive(self):
        from app.core.symbolic.input_router import InputRouter
        from app.core.base.source_descriptor import SourceDescriptor

        graph = _StubGraph()

        # Passive mass
        passive = _StubComponent("mass_1", descriptor=None)
        passive.add_port("port_a", "node_body")
        graph.add(passive)

        # Force source
        force_src = _StubComponent(
            "sf_1",
            descriptor=SourceDescriptor(
                kind="force",
                driven_port_name="port",
                reference_port_name="reference_port",
                input_variable_name="f_sf_1_out",
                amplitude_parameter="amplitude",
            ),
        )
        force_src.add_port("port", "node_body")
        force_src.add_port("reference_port", "ground")
        graph.add(force_src)

        router = InputRouter()
        result = router.route(graph, {"node_body": 0})

        self.assertEqual(result.input_count, 1)  # only source, not passive
        self.assertEqual(result.force_sources[0].component_id, "sf_1")

    def test_node_index_snapshot_is_independent(self):
        """RoutingResult.node_index is a snapshot — mutating original dict has no effect."""
        from app.core.symbolic.input_router import InputRouter

        graph = _StubGraph()
        ni = {"node_a": 0}
        result = InputRouter().route(graph, ni)

        ni["node_a"] = 99  # mutate original
        self.assertEqual(result.node_index.get("node_a"), 0)  # snapshot unchanged

    def test_router_does_not_inspect_class_name(self):
        """Router must not check isinstance or class name — only SourceDescriptor."""
        from app.core.symbolic.input_router import InputRouter
        from app.core.base.source_descriptor import SourceDescriptor

        # An arbitrary class with no inheritance from any real component
        class _RandomClass:
            id = "mystery_1"

            def port(self, name):
                return _StubPort(name, "node_x")

            def get_source_descriptor(self):
                return SourceDescriptor(
                    kind="force",
                    driven_port_name="port",
                    reference_port_name="reference_port",
                    input_variable_name="f_mystery",
                    amplitude_parameter="amplitude",
                )

        class _FakeGraph:
            components = {"mystery_1": _RandomClass()}

        result = InputRouter().route(_FakeGraph(), {"node_x": 0})
        self.assertEqual(result.input_count, 1)
        self.assertEqual(result.routes[0].component_id, "mystery_1")

    def test_missing_port_does_not_crash(self):
        """If a port name from the descriptor doesn't exist on the component, route gracefully."""
        from app.core.symbolic.input_router import InputRouter
        from app.core.base.source_descriptor import SourceDescriptor

        graph = _StubGraph()
        src = _StubComponent(
            "sf_broken",
            descriptor=SourceDescriptor(
                kind="force",
                driven_port_name="nonexistent_port",
                reference_port_name="reference_port",
                input_variable_name="f_out",
                amplitude_parameter="amplitude",
            ),
        )
        # Don't add "nonexistent_port" — component.port() will raise KeyError
        src.add_port("reference_port", "ground")
        graph.add(src)

        router = InputRouter()
        # Should not raise; driven_node_id will be None → dof_index = -1
        result = router.route(graph, {})
        self.assertEqual(result.input_count, 1)
        self.assertEqual(result.routes[0].driven_dof_index, -1)


# ---------------------------------------------------------------------------
# Integration test with real single_mass template
# ---------------------------------------------------------------------------

class TestInputRouterIntegration(unittest.TestCase):

    def test_single_mass_template_has_one_force_source(self):
        """The single_mass template contains exactly one StepForce source."""
        try:
            from tests.fixtures.graph_factories import build_single_mass_graph
        except ImportError:
            self.skipTest("Template or dependencies not available")

        from app.core.symbolic.input_router import InputRouter

        graph = build_single_mass_graph()

        # Build a minimal node_index: just the mass's port_a node
        mass_comp = graph.components.get("mass")
        if mass_comp is None:
            self.skipTest("Mass component not found in graph")

        port_a = mass_comp.port("port_a")
        if port_a.node_id is None:
            self.skipTest("Mass port_a not connected")

        node_index = {port_a.node_id: 0}

        router = InputRouter()
        result = router.route(graph, node_index)

        # StepForce should be detected
        self.assertTrue(result.has_sources())
        self.assertEqual(result.input_count, 1)
        self.assertEqual(len(result.force_sources), 1)
        self.assertEqual(len(result.displacement_sources), 0)

        route = result.force_sources[0]
        self.assertEqual(route.source_kind, "force")
        self.assertEqual(route.driven_dof_index, 0)
        self.assertEqual(route.input_variable_name, "f_input_force_out")

    def test_router_result_node_index_matches_input(self):
        """RoutingResult preserves the exact node_index passed in."""
        try:
            from tests.fixtures.graph_factories import build_single_mass_graph
        except ImportError:
            self.skipTest("Template not available")

        from app.core.symbolic.input_router import InputRouter

        graph = build_single_mass_graph()
        mass_comp = graph.components.get("mass")
        if mass_comp is None:
            self.skipTest("Mass component not found")

        port_a = mass_comp.port("port_a")
        if port_a.node_id is None:
            self.skipTest("Mass port_a not connected")

        ni = {port_a.node_id: 0}
        result = InputRouter().route(graph, ni)
        self.assertEqual(result.node_index, ni)


if __name__ == "__main__":
    unittest.main()
