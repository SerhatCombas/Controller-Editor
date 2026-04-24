"""InputRouter — topology-only layer for input/source detection.

Design contract (Wave 1):
  - InputRouter reads *only* graph topology and component SourceDescriptors.
  - InputRouter does NOT perform any matrix algebra or symbolic manipulation.
  - InputRouter produces a RoutingResult dataclass that the PolymorphicDAEReducer
    then uses to assemble the B-matrix (input-to-force mapping).

Separation of concerns:
  ┌────────────────────────────────────────────────────────┐
  │  InputRouter                                           │
  │   • asks components: "are you a source?" (bool)       │
  │   • reads SourceDescriptor topology fields             │
  │   • maps source components to their driven DOF index   │
  │   • produces RoutingResult (pure data, no sympy)       │
  └────────────────────────────────────────────────────────┘
  ┌────────────────────────────────────────────────────────┐
  │  PolymorphicDAEReducer  (Commit 4)                     │
  │   • receives RoutingResult                             │
  │   • assembles M, D, K matrices from component contribs │
  │   • builds B vector from RoutingResult                 │
  │   • does all symbolic algebra                          │
  └────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.base.source_descriptor import SourceDescriptor, SourceKind


@dataclass(frozen=True, slots=True)
class SourceRoute:
    """Topology mapping for a single source component.

    Attributes:
        component_id: ID of the source component.
        source_kind: Physical kind of excitation (force / displacement / etc.).
        driven_node_id: The node_id that this source directly drives.
        reference_node_id: The node_id that serves as the source's reference
            (usually ground). May be None if not connected.
        input_variable_name: Symbolic name of the input signal (e.g. "u_body_force").
        amplitude_parameter: Name of the amplitude parameter in the component's
            parameters dict (used by the reducer for numeric substitution).
        driven_dof_index: DOF index in the assembled matrix.  -1 if the driven
            node is not an active DOF (e.g. if the source drives a ground node,
            which is physically ill-defined but should not crash the router).
    """

    component_id: str
    source_kind: SourceKind
    driven_node_id: str
    reference_node_id: str | None
    input_variable_name: str
    amplitude_parameter: str
    driven_dof_index: int


@dataclass(frozen=True)
class RoutingResult:
    """Complete input-routing information for one system.

    Produced by InputRouter.route(); consumed by PolymorphicDAEReducer.

    Attributes:
        routes: Ordered tuple of SourceRoute objects — one per identified source.
        node_index: The DOF-to-index mapping used when computing driven_dof_index.
            Included here so the reducer and router share exactly the same mapping.
        force_sources: Subset of routes whose source_kind == "force".
        displacement_sources: Subset of routes whose source_kind == "displacement".
        input_count: Total number of input channels (len(routes)).
    """

    routes: tuple[SourceRoute, ...]
    node_index: dict[str, int]
    force_sources: tuple[SourceRoute, ...] = field(default_factory=tuple)
    displacement_sources: tuple[SourceRoute, ...] = field(default_factory=tuple)

    @property
    def input_count(self) -> int:
        return len(self.routes)

    def has_sources(self) -> bool:
        return len(self.routes) > 0


class InputRouter:
    """Identifies source components and resolves their DOF topology.

    Usage::

        router = InputRouter()
        result = router.route(graph, node_index)

    The ``graph`` must be a ``SystemGraph`` instance.  ``node_index`` is the
    ``{node_id: dof_index}`` dict produced by the DOF-enumeration step of the
    PolymorphicDAEReducer.
    """

    def route(self, graph: object, node_index: dict[str, int]) -> RoutingResult:
        """Scan all components in *graph* for sources and build routing data.

        Args:
            graph: A ``SystemGraph`` instance (typed as ``object`` to avoid a
                circular import; only ``graph.components`` is accessed).
            node_index: Mapping from ``node_id → DOF index`` for active DOFs.
                Ground/reference nodes that were eliminated from the assembled
                matrices must NOT appear in this dict.

        Returns:
            A frozen ``RoutingResult`` describing every source in the system.
        """
        routes: list[SourceRoute] = []

        for component in self._iter_components(graph):
            descriptor: SourceDescriptor | None = component.get_source_descriptor()
            if descriptor is None:
                continue  # passive component — not a source

            driven_port_name = descriptor.driven_port_name
            reference_port_name = descriptor.reference_port_name

            driven_node_id = self._resolve_node(component, driven_port_name)
            reference_node_id = self._resolve_node(component, reference_port_name)

            # Determine DOF index; -1 signals "driven node is not an active DOF"
            driven_dof_index = node_index.get(driven_node_id, -1) if driven_node_id else -1

            routes.append(SourceRoute(
                component_id=component.id,
                source_kind=descriptor.kind,
                driven_node_id=driven_node_id or "",
                reference_node_id=reference_node_id,
                input_variable_name=descriptor.input_variable_name,
                amplitude_parameter=descriptor.amplitude_parameter,
                driven_dof_index=driven_dof_index,
            ))

        routes_tuple = tuple(routes)
        force_sources = tuple(r for r in routes_tuple if r.source_kind == "force")
        displacement_sources = tuple(r for r in routes_tuple if r.source_kind == "displacement")

        return RoutingResult(
            routes=routes_tuple,
            node_index=dict(node_index),  # snapshot — immutable copy
            force_sources=force_sources,
            displacement_sources=displacement_sources,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _iter_components(graph: object):
        """Yield components from a SystemGraph without importing SystemGraph."""
        # Access .components attribute generically to avoid circular import.
        components = getattr(graph, "components", None)
        if components is None:
            raise AttributeError(
                "InputRouter.route() expected 'graph' to have a 'components' attribute."
            )
        if isinstance(components, dict):
            yield from components.values()
        else:
            yield from components

    @staticmethod
    def _resolve_node(component: object, port_name: str) -> str | None:
        """Return the node_id connected to *port_name* on *component*, or None."""
        try:
            p = component.port(port_name)
            return p.node_id
        except (KeyError, AttributeError):
            return None
