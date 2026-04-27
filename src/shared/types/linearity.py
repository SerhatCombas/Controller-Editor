"""Linearity profile metadata for components.

This module is part of Wave 1 of the architectural generalization effort.
It introduces a small, frozen dataclass that each component can use to
declare its own linearity character. The LinearityClassifier aggregates
these profiles at the graph level to decide which analysis pipeline
(DAL A — LTI, or DAL B — nonlinear) applies.

Behavior-neutral by design: the default LinearityProfile corresponds to
"fully linear, time-invariant, no operating-point dependence", which
matches the implicit assumption the existing pipeline makes today.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


NonlinearityKind = Literal[
    "smooth",      # differentiable nonlinearity, e.g. cubic spring, sin(theta)
    "hard",        # discontinuous, e.g. Coulomb friction, dead-zone, saturation
    "geometric",   # large-angle / large-deformation effects
    "parametric",  # parameter depends on state variable
    "fluid",       # turbulent flow, orifice, quadratic pressure-flow laws
]


@dataclass(frozen=True, slots=True)
class LinearityProfile:
    """Describes the linearity character of a single component.

    Instances are immutable so they can be shared freely and reasoned about
    without synchronization concerns. The default value represents a fully
    linear, time-invariant, operating-point-independent component — which is
    what every existing component in the repository already is in practice.

    Attributes:
        is_linear: True when constitutive relations obey superposition.
        is_time_invariant: True when parameters do not depend on time.
        nonlinearity_kind: When is_linear is False, categorizes how.
        requires_operating_point: True when the component only becomes linear
            after linearization around an equilibrium (e.g. a pendulum).
        notes: Free-form human-readable remarks useful in UI badges.
    """

    is_linear: bool = True
    is_time_invariant: bool = True
    nonlinearity_kind: NonlinearityKind | None = None
    requires_operating_point: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_lti(self) -> bool:
        """True when the component qualifies as Linear Time-Invariant."""
        return self.is_linear and self.is_time_invariant
