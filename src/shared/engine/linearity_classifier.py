"""LinearityClassifier — Wave 1 component-level linearity analysis.

Design contract (Warning 4, approved before Wave 1 began):
  "LinearityClassifier must be honest — verdict_confidence='component_level_only',
   topology_assumptions_modeled=False, caveats always populated."

The classifier inspects each component's LinearityProfile and assembles a
SystemClass verdict.  It NEVER claims the full system is definitely LTI —
only that every inspected component reports linear and time-invariant
behaviour at the component level.  Topology effects (saturation through
coupling, effective nonlinearity from parameter scheduling, etc.) are
explicitly out of scope for Wave 1.

Usage::

    from src.shared.engine.linearity_classifier import LinearityClassifier
    result = LinearityClassifier().classify(graph)
    if result.is_lti_candidate:
        # Safe to use linear state-space machinery
        ...

The ``SystemClass`` dataclass is the sole public output type.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # graph type is structural — no hard import needed


# ---------------------------------------------------------------------------
# Public output type
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ComponentVerdictEntry:
    """Per-component linearity verdict, stored in SystemClass for traceability.

    Attributes:
        component_id: Unique identifier of the inspected component.
        component_type: Human-readable class name (for diagnostics only —
            never used in logic branches).
        is_linear: From ``LinearityProfile.is_linear``.
        is_time_invariant: From ``LinearityProfile.is_time_invariant``.
        nonlinearity_kind: Populated when ``is_linear=False``.
        notes: Forwarded from ``LinearityProfile.notes``.
    """

    component_id: str
    component_type: str
    is_linear: bool
    is_time_invariant: bool
    nonlinearity_kind: str | None
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SystemClass:
    """Output of ``LinearityClassifier.classify()``.

    Attributes:
        is_lti_candidate: True **only** if every component reports
            ``is_linear=True`` **and** ``is_time_invariant=True`` at the
            component level.  This is a *necessary* condition for LTI — it
            is *not* sufficient (see ``caveats``).
        component_level_verdict: Human-readable one-line verdict string,
            e.g. ``"LTI candidate (component-level only)"`` or
            ``"Nonlinear: 2 nonlinear component(s) found"``.
        verdict_confidence: Always ``"component_level_only"`` in Wave 1.
            Future waves may introduce topology-aware analysis.
        topology_assumptions_modeled: Always ``False`` in Wave 1.  Means
            the classifier did NOT inspect coupling, saturation chains, or
            parameter-scheduled gains.
        nonlinear_component_ids: IDs of components that reported
            ``is_linear=False``.
        time_varying_component_ids: IDs of components that reported
            ``is_time_invariant=False`` (but may be linear).
        component_verdicts: Per-component breakdown for traceability.
        caveats: Non-empty list of plain-English limitation notices.
            Always populated — even for LTI candidates — to prevent
            accidental over-reliance on this verdict.
        component_count: Number of components inspected.
    """

    is_lti_candidate: bool
    component_level_verdict: str
    verdict_confidence: str
    topology_assumptions_modeled: bool
    nonlinear_component_ids: tuple[str, ...]
    time_varying_component_ids: tuple[str, ...]
    component_verdicts: tuple[ComponentVerdictEntry, ...]
    caveats: tuple[str, ...]
    component_count: int


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

_WAVE1_CAVEATS: tuple[str, ...] = (
    "Verdict is component-level only: topology effects are not modeled.",
    "Coupling between components may introduce effective nonlinearities "
    "not visible at the individual component level.",
    "Parameter-scheduled or load-dependent components report as linear "
    "at nominal operating point only.",
    "Wave 1 classifier does not inspect algebraic loops or constraint equations.",
)


class LinearityClassifier:
    """Inspect a SystemGraph and return a conservative SystemClass verdict.

    The classifier is stateless — the same instance can classify multiple
    graphs sequentially.

    Design decisions:
    - Uses ``component.linearity_profile()`` exclusively; never inspects
      class names or component type strings.
    - Returns ``verdict_confidence="component_level_only"`` unconditionally.
    - ``topology_assumptions_modeled`` is always ``False`` (Wave 1 scope).
    - ``caveats`` is always non-empty.
    """

    def classify(self, graph: object) -> SystemClass:
        """Classify the linearity of all components in *graph*.

        Args:
            graph: A ``SystemGraph`` instance.  Any object with a
                ``.components`` dict of BaseComponent-like objects is
                accepted (duck-typed).

        Returns:
            A frozen ``SystemClass`` dataclass.
        """
        components = getattr(graph, "components", {})
        entries: list[ComponentVerdictEntry] = []
        nonlinear_ids: list[str] = []
        time_varying_ids: list[str] = []

        for cid, comp in components.items():
            profile = comp.linearity_profile()
            entry = ComponentVerdictEntry(
                component_id=cid,
                component_type=type(comp).__name__,
                is_linear=profile.is_linear,
                is_time_invariant=profile.is_time_invariant,
                nonlinearity_kind=profile.nonlinearity_kind,
                notes=profile.notes,
            )
            entries.append(entry)
            if not profile.is_linear:
                nonlinear_ids.append(cid)
            if not profile.is_time_invariant:
                time_varying_ids.append(cid)

        is_lti = (not nonlinear_ids) and (not time_varying_ids)

        if is_lti:
            verdict = "LTI candidate (component-level only)"
        elif nonlinear_ids and time_varying_ids:
            verdict = (
                f"Nonlinear and time-varying: "
                f"{len(nonlinear_ids)} nonlinear, "
                f"{len(time_varying_ids)} time-varying component(s)"
            )
        elif nonlinear_ids:
            verdict = f"Nonlinear: {len(nonlinear_ids)} nonlinear component(s) found"
        else:
            verdict = (
                f"Linear but time-varying (LTV): "
                f"{len(time_varying_ids)} time-varying component(s)"
            )

        return SystemClass(
            is_lti_candidate=is_lti,
            component_level_verdict=verdict,
            verdict_confidence="component_level_only",
            topology_assumptions_modeled=False,
            nonlinear_component_ids=tuple(nonlinear_ids),
            time_varying_component_ids=tuple(time_varying_ids),
            component_verdicts=tuple(entries),
            caveats=_WAVE1_CAVEATS,
            component_count=len(entries),
        )
