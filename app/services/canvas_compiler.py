"""CanvasCompiler — bridges canvas drawing to SystemGraph.

Converts a list of ``CanvasVisualComponent`` + ``CanvasWireConnection``
objects (the UI layer's representation of a user-drawn diagram) into a
fully-assembled ``SystemGraph`` that the symbolic/numeric pipeline can
simulate directly.

Design decisions
────────────────
Port mapping
    Each canvas component type exposes named connector ports ("top",
    "bottom", "R", "C", "ref", "output").  These are *visual* names and do
    not always have a 1-to-1 relationship with the core port names
    ("port_a", "port_b", "reference_port", "port").  The table
    ``_CANVAS_TO_CORE_PORT`` captures the authoritative mapping derived
    from the template source of truth (``model_canvas.py`` wire lists vs.
    the core template builders in ``app/core/templates/``).

    Notably, ``mass.top`` and ``mass.bottom`` *both* map to ``port_a``
    because a mass has a single DOF node that multiple elements can
    attach to from above or below.  The reference inertial port is
    handled implicitly (see below).

Implicit reference connections
    The ``reference_port`` of mass, wheel, and signal sources is never
    drawn as an explicit wire in the canvas — it is always the inertial
    ground.  The compiler discovers the ground node (the ``port`` of the
    ``mechanical_reference`` component, or creates one if absent) and
    unions every such implicit reference with it.

Union-find topology
    All port IDs (``"component_id.port_name"``) are put into a
    union-find structure.  Both explicit wires and implicit reference
    connections call ``union()``.  After all unions, each equivalence
    class becomes one ``Node`` in the ``SystemGraph``.

Node assembly
    Nodes and port ``node_id`` fields are set directly — we bypass
    ``SystemGraph.connect()`` (which has a subtle limitation when both
    ports already carry different node IDs) and build the Connection list
    manually.

Probes
    Probes are attached based on ``assigned_io_roles`` on each canvas
    component.  Components with ``OUTPUT`` role get a displacement probe
    (or spring-force probe for spring/tire).  The first output component
    becomes ``graph.selected_output_id``.  The first input component
    becomes ``graph.selected_input_id``.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.core.base.connection import Connection
from app.core.base.domain import MECHANICAL_TRANSLATIONAL_DOMAIN
from app.core.base.node import Node
from app.core.graph.system_graph import SystemGraph
from app.core.models.mechanical import Damper, Mass, MechanicalGround, Spring, Wheel
from app.core.models.sources import RandomRoad, StepForce
from app.core.probes import BaseProbe
from app.core.symbolic.output_kind import (
    OutputKind,
    QK_ACCELERATION,
    QK_DISPLACEMENT,
    QK_SPRING_FORCE,
)

if TYPE_CHECKING:
    from app.core.base.component import BaseComponent
    from app.ui.canvas.component_system import CanvasVisualComponent, CanvasWireConnection


# ---------------------------------------------------------------------------
# Canvas connector name → core port name, keyed by component type_key.
#
# Derivation: cross-reference model_canvas.py template wire lists with
# the corresponding core template builders (quarter_car.py, single_mass.py,
# two_mass.py).  The mapping is stable across all three templates.
#
# Notes:
#   • mass.top and mass.bottom both map to "port_a" — the mass has a single
#     DOF port that elements connect to from either direction.
#   • wheel.top and wheel.bottom similarly both map to "port_a".
#   • reference_port connections are handled implicitly (see _IMPLICIT_REF_TYPES).
# ---------------------------------------------------------------------------
_CANVAS_TO_CORE_PORT: dict[str, dict[str, str]] = {
    "mass": {
        "top":    "port_a",
        "bottom": "port_a",
    },
    "wheel": {
        "top":    "port_a",
        "bottom": "port_a",
    },
    "translational_spring": {
        "R": "port_a",
        "C": "port_b",
    },
    "translational_damper": {
        "R": "port_a",
        "C": "port_b",
    },
    "tire_stiffness": {
        "R": "port_a",
        "C": "port_b",
    },
    "mechanical_reference": {
        "ref": "port",
    },
    "mechanical_random_reference": {
        "output": "port",
    },
    "ideal_force_source": {
        "R": "port",
        "C": "reference_port",
    },
}

# Component types whose reference_port must be implicitly connected to ground.
# These components' canvas representations have no wire for the reference —
# the inertial ground connection is architectural, not user-drawn.
_IMPLICIT_REF_TYPES: frozenset[str] = frozenset({
    "mass",
    "wheel",
    "mechanical_random_reference",
})

# Implicit ground node ID used when no mechanical_reference component exists.
_IMPLICIT_GROUND_ID = "_implicit_ground"


# ---------------------------------------------------------------------------
# Union-Find (path-compressed, rank-based)
# ---------------------------------------------------------------------------

class _UnionFind:
    """Disjoint-set structure for grouping port IDs into shared nodes."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}
        self._rank:   dict[str, int] = {}

    def register(self, key: str) -> None:
        if key not in self._parent:
            self._parent[key] = key
            self._rank[key] = 0

    def find(self, key: str) -> str:
        self.register(key)
        root = key
        while self._parent[root] != root:
            root = self._parent[root]
        # Path compression
        cur = key
        while cur != root:
            nxt = self._parent[cur]
            self._parent[cur] = root
            cur = nxt
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        # Union by rank
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1

    def groups(self) -> dict[str, list[str]]:
        """Return a mapping from root → list of all members in that group."""
        result: dict[str, list[str]] = {}
        for key in self._parent:
            root = self.find(key)
            result.setdefault(root, []).append(key)
        return result


# ---------------------------------------------------------------------------
# CanvasCompiler
# ---------------------------------------------------------------------------

class CanvasCompiler:
    """Compiles a canvas drawing into a ``SystemGraph``.

    Usage::

        compiler = CanvasCompiler()
        graph = compiler.compile(canvas.components, canvas.wires)
        # graph is ready for EquationBuilder / QuarterCarNumericBackend / etc.

    The compiler is stateless — each call to ``compile()`` returns a fresh
    independent graph.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compile(
        self,
        components: list[CanvasVisualComponent],
        wires: list[CanvasWireConnection],
    ) -> SystemGraph:
        """Build a ``SystemGraph`` from a canvas layout.

        Args:
            components: All visual components on the canvas.
            wires:      All wire connections between connector ports.

        Returns:
            A fully assembled ``SystemGraph`` with nodes, connections,
            and probes attached.
        """
        # ── 1. Create core components ──────────────────────────────────
        graph = SystemGraph()
        type_map:    dict[str, str]  = {}   # component_id → type_key
        input_ids:   list[str]       = []
        output_ids:  list[str]       = []
        ground_port_id: str | None   = None

        for cv in components:
            type_key = cv.spec.type_key
            comp_id  = cv.component_id
            type_map[comp_id] = type_key

            core = self._create_core_component(comp_id, type_key)
            if core is not None:
                graph.add_component(core)

            if type_key == "mechanical_reference":
                ground_port_id = f"{comp_id}.port"

            from app.ui.canvas.component_system import ComponentIoRole
            for role in cv.assigned_io_roles:
                if role == ComponentIoRole.INPUT:
                    input_ids.append(comp_id)
                elif role == ComponentIoRole.OUTPUT:
                    output_ids.append(comp_id)

        # ── 2. Ensure a ground node exists ────────────────────────────
        if ground_port_id is None:
            # No mechanical_reference on canvas → create an implicit one
            gnd = MechanicalGround(_IMPLICIT_GROUND_ID)
            graph.add_component(gnd)
            type_map[_IMPLICIT_GROUND_ID] = "mechanical_reference"
            ground_port_id = f"{_IMPLICIT_GROUND_ID}.port"

        # ── 3. Build union-find from wires + implicit refs ────────────
        uf = _UnionFind()

        # Register every port in the graph
        for comp in graph.components.values():
            for port in comp.ports:
                uf.register(port.id)

        # Process explicit wire connections
        for wire in wires:
            src = self._resolve_port_id(wire.source_component_id,
                                         type_map, wire.source_connector_name)
            tgt = self._resolve_port_id(wire.target_component_id,
                                         type_map, wire.target_connector_name)
            if src is not None and tgt is not None and \
               src in uf._parent and tgt in uf._parent:
                uf.union(src, tgt)

        # Process implicit reference_port → ground connections
        for comp_id, type_key in type_map.items():
            if type_key in _IMPLICIT_REF_TYPES:
                ref_id = f"{comp_id}.reference_port"
                if ref_id in uf._parent:
                    uf.union(ref_id, ground_port_id)

        # ── 4. Assign nodes to port groups ────────────────────────────
        groups   = uf.groups()
        gnd_root = uf.find(ground_port_id)

        root_to_node_id: dict[str, str] = {}
        counter = 0
        for root in groups:
            if root == gnd_root:
                root_to_node_id[root] = "node_ground"
            else:
                root_to_node_id[root] = f"node_{counter}"
                counter += 1

        for root, port_ids in groups.items():
            node_id = root_to_node_id[root]
            node = Node(id=node_id, domain=MECHANICAL_TRANSLATIONAL_DOMAIN)
            graph.nodes[node_id] = node
            for port_id in port_ids:
                try:
                    port = graph.get_port(port_id)
                    port.connect_to(node_id)
                    node.attach_port(port_id)
                except KeyError:
                    pass  # Port not in graph (unknown component type — skip)

        # ── 5. Register explicit wire connections ─────────────────────
        for wire in wires:
            src = self._resolve_port_id(wire.source_component_id,
                                         type_map, wire.source_connector_name)
            tgt = self._resolve_port_id(wire.target_component_id,
                                         type_map, wire.target_connector_name)
            if src is None or tgt is None:
                continue
            conn = Connection(
                id=f"conn_{uuid.uuid4().hex[:8]}",
                port_a=src,
                port_b=tgt,
                label=(
                    f"{wire.source_component_id}.{wire.source_connector_name}"
                    f"→{wire.target_component_id}.{wire.target_connector_name}"
                ),
            )
            graph.connections.append(conn)

        # ── 6. Attach probes and set I/O selection ────────────────────
        self._attach_probes(graph, components, type_map, input_ids, output_ids)

        return graph

    # ------------------------------------------------------------------
    # Component factory
    # ------------------------------------------------------------------

    def _create_core_component(
        self,
        comp_id: str,
        type_key: str,
    ) -> BaseComponent | None:
        """Instantiate the core model component for a given canvas type_key."""
        if type_key == "mass":
            return Mass(comp_id, mass=1.0)
        if type_key == "wheel":
            return Wheel(comp_id, mass=1.0)
        if type_key in ("translational_spring", "tire_stiffness"):
            return Spring(comp_id, stiffness=1.0)
        if type_key == "translational_damper":
            return Damper(comp_id, damping=1.0)
        if type_key == "mechanical_reference":
            return MechanicalGround(comp_id)
        if type_key == "mechanical_random_reference":
            return RandomRoad(
                comp_id,
                amplitude=0.03,
                roughness=0.35,
                seed=7,
                vehicle_speed=6.0,
                dt=0.01,
                duration=15.0,
            )
        if type_key == "ideal_force_source":
            return StepForce(comp_id, amplitude=1.0)
        # Unknown / unsupported type — silently skip
        return None

    # ------------------------------------------------------------------
    # Port resolution
    # ------------------------------------------------------------------

    def _resolve_port_id(
        self,
        comp_id: str,
        type_map: dict[str, str],
        canvas_connector_name: str,
    ) -> str | None:
        """Return the core port ID for a canvas connector, or None."""
        type_key = type_map.get(comp_id, "")
        port_name = _CANVAS_TO_CORE_PORT.get(type_key, {}).get(canvas_connector_name)
        if port_name is None:
            return None
        return f"{comp_id}.{port_name}"

    # ------------------------------------------------------------------
    # Probe attachment
    # ------------------------------------------------------------------

    def _attach_probes(
        self,
        graph: SystemGraph,
        components: list[CanvasVisualComponent],
        type_map: dict[str, str],
        input_ids:  list[str],
        output_ids: list[str],
    ) -> None:
        """Attach probes based on IO roles and set graph.selected_input/output_id."""
        if input_ids:
            graph.selected_input_id = input_ids[0]

        first_probe_id: str | None = None

        for comp_id in output_ids:
            type_key = type_map.get(comp_id, "")
            probe: BaseProbe | None = None

            if type_key in ("mass", "wheel"):
                probe = BaseProbe(
                    id=f"probe_{comp_id}_displacement",
                    name=f"{comp_id} displacement",
                    quantity="displacement",
                    target_component_id=comp_id,
                    output_kind=OutputKind.STATE_DIRECT,
                    quantity_key=QK_DISPLACEMENT,
                )
            elif type_key in ("translational_spring", "tire_stiffness"):
                probe = BaseProbe(
                    id=f"probe_{comp_id}_force",
                    name=f"{comp_id} spring force",
                    quantity="spring_force",
                    target_component_id=comp_id,
                    output_kind=OutputKind.DERIVED_ALGEBRAIC,
                    quantity_key=QK_SPRING_FORCE,
                )
            elif type_key == "translational_damper":
                probe = BaseProbe(
                    id=f"probe_{comp_id}_force",
                    name=f"{comp_id} damper force",
                    quantity="damper_force",
                    target_component_id=comp_id,
                    output_kind=OutputKind.DERIVED_ALGEBRAIC,
                    quantity_key=QK_SPRING_FORCE,
                )
            # For other types (ground, sources) — no meaningful probe

            if probe is not None:
                graph.attach_probe(probe)
                if first_probe_id is None:
                    first_probe_id = probe.id

        if first_probe_id is not None:
            graph.selected_output_id = first_probe_id
