"""Faz 4h — Symbolic-backend linearization warnings.

When a non-linear constitutive law (e.g. Wheel Mode B's `max(0, ...)`
contact-force clamp introduced in Faz 4g) is folded into the symbolic
state-space, the dae_reducer's parameter-driven K/C accumulation
*silently* linearizes it: the reduced K matrix represents the
"always-in-contact" branch, and any actual lift-off is ignored.

This module surfaces those situations:

  * detect_linearized_mode_b_wheels(graph) returns the list of Wheel
    component IDs that will be silently linearized — Mode B with a wired
    road_contact_port. Free Mode B wheels (no road wiring) are excluded
    because nothing would have been linearized in the first place.

  * Symbolic backends call the helper, log a WARNING with a stable
    message, and pass the list through their state-space metadata under
    the key 'linearized_contact_mode_b'. UI panels reading the metadata
    can show a badge / banner without having to re-traverse the graph.

This is intentionally *not* an error path. Mode B's linearized form is a
correct local approximation around the always-in-contact equilibrium —
the warning exists so the user knows the symbolic state-space cannot
predict actual lift-off events even though the numerical backend can.

Faz 4j will deepen this:
  * Polymorphic component-side declaration
    (BaseComponent.declares_silent_linearization()) so adding a new
    non-linear component does not require touching this module.
  * Removal of the legacy class-name / parameter checks below.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.shared.graph.system_graph import SystemGraph


logger = logging.getLogger(__name__)


# Metadata key under which symbolic backends publish the list of
# component IDs that triggered a silent linearization. UI code that
# wants to surface a "linearized" badge should read this.
METADATA_KEY_LINEARIZED_MODE_B = "linearized_contact_mode_b"


def detect_linearized_mode_b_wheels(graph: "SystemGraph") -> list[str]:
    """Return component IDs of Wheel(s) that will be silently linearized.

    A Wheel triggers the warning when **both** conditions hold:
      * `parameters["contact_mode"] == "dynamic_contact"` (Faz 4g Mode B,
        emits a `max(0, ...)` contact-force law into the constitutive
        equations).
      * `road_contact_port` is wired to a node — without that wiring the
        contact law is never emitted in the first place, so the symbolic
        state-space already represents the wheel correctly (as a plain
        Mass) and there is nothing to warn about.

    Returns an empty list when no Wheel meets both criteria. Order
    matches the graph's component-insertion order so callers can rely
    on the result being deterministic for a given graph.
    """
    triggered: list[str] = []
    for component_id, component in graph.components.items():
        # Class-name check — paralleling the dae_reducer Wheel branch
        # that the linearization actually happens in. Faz 4j will move
        # this to a polymorphic `declares_silent_linearization()` API.
        if component.__class__.__name__ != "Wheel":
            continue
        if component.parameters.get("contact_mode") != "dynamic_contact":
            continue
        road_port = component.port("road_contact_port")
        if road_port.node_id is None:
            continue
        triggered.append(component_id)
    return triggered


def emit_linearization_warning(triggered: list[str], *, backend_label: str) -> None:
    """Log a WARNING when the symbolic backend silently linearizes Mode B.

    No-op when `triggered` is empty. The message format is stable so
    tests and external log scrapers can match against it.

    `backend_label` distinguishes which symbolic entry-point produced
    the warning (e.g. "SymbolicStateSpaceBackend" vs
    "SymbolicStateSpaceRuntimeBackend") — useful when both surface the
    same template and the user is debugging which path emitted the log.
    """
    if not triggered:
        return
    logger.warning(
        "Symbolic backend %s silently linearized Mode B Wheel(s) %s "
        "(contact_mode='dynamic_contact'). Lift-off is ignored in the "
        "reduced state-space; numerical backends remain accurate.",
        backend_label,
        triggered,
    )
