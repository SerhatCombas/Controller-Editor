"""OutputKind — Wave 3A canonical output taxonomy.

Defines the coarse-grained kind of each physical output expression, giving
all layers (OutputMapper, TFBuilder, UI, tests) a shared type-safe vocabulary.

Two-level design (Wave 3 decision)
────────────────────────────────────
  ``OutputKind``   — coarse enum: how the output is derived from state/params
  ``quantity_key`` — fine string: which physical quantity within that kind
                     (e.g. "acceleration" or "spring_force")

This separation avoids both the fragility of raw strings and the brittleness
of a flat enum that must enumerate every possible quantity.

Backward compatibility
──────────────────────
``probe.quantity`` (Wave 2 legacy string) is kept unchanged.
``infer_kind()`` maps it to ``OutputKind`` for callers that only have the
legacy string.  New code should set ``output_kind`` on the probe directly.

Faz 5 extension
───────────────
Electrical QK constants added (QK_CURRENT, QK_CAPACITOR_VOLTAGE, QK_VOLTAGE,
QK_RELATIVE_VOLTAGE) so the RLC template (and future electrical templates)
can attach probes following the same pattern as mechanical templates.
"""
from __future__ import annotations

from enum import Enum


class OutputKind(Enum):
    """Coarse classification of how an output is derived.

    STATE_DIRECT
        Output is a single entry in the state vector, selected by a
        unit C row.  Covers absolute displacement and velocity.

    STATE_RELATIVE
        Output is the difference of two state entries.  Covers relative
        displacement (suspension deflection) and relative velocity.
        C row has exactly two non-zero entries (+1 and -1).

    DERIVED_ALGEBRAIC
        Output is a state-linear expression that requires a physical
        parameter (e.g. spring stiffness k) as a scalar multiplier.
        Covers spring force (F = k·Δx) and damper force (F = d·Δv).
        D row is zero — no direct feedthrough.

    DERIVED_DYNAMIC
        Output is the time derivative of a state, expressed via the
        state equation: ÿ = A·x + B·u.  Covers acceleration.
        C row = C_base · A, D row = C_base · B (D ≠ 0 in general).

    UNSUPPORTED
        The output cannot be expressed in the current framework.
        OutputMapper must return zero C/D rows and set
        ``supported_for_tf=False`` with an explicit reason.
    """

    STATE_DIRECT      = "state_direct"
    STATE_RELATIVE    = "state_relative"
    DERIVED_ALGEBRAIC = "derived_algebraic"
    DERIVED_DYNAMIC   = "derived_dynamic"
    UNSUPPORTED       = "unsupported"


# ---------------------------------------------------------------------------
# quantity_key constants (fine-grained strings within each kind)
# ---------------------------------------------------------------------------

# STATE_DIRECT — mechanical
QK_DISPLACEMENT = "displacement"
QK_VELOCITY     = "velocity"

# STATE_DIRECT — electrical (Faz 5)
QK_CURRENT           = "current"
QK_CAPACITOR_VOLTAGE = "capacitor_voltage"

# STATE_RELATIVE — mechanical
QK_RELATIVE_DISPLACEMENT = "relative_displacement"
QK_RELATIVE_VELOCITY     = "relative_velocity"

# STATE_RELATIVE — electrical (Faz 5)
QK_RELATIVE_VOLTAGE      = "relative_voltage"

# DERIVED_ALGEBRAIC — mechanical
QK_SPRING_FORCE  = "spring_force"
QK_DAMPER_FORCE  = "damper_force"

# DERIVED_ALGEBRAIC — electrical (Faz 5)
QK_VOLTAGE       = "voltage"

# DERIVED_DYNAMIC — mechanical
QK_ACCELERATION = "acceleration"


# ---------------------------------------------------------------------------
# Backward-compat mapping: Wave 2 quantity string → OutputKind
# ---------------------------------------------------------------------------

_QUANTITY_TO_KIND: dict[str, OutputKind] = {
    # Mechanical
    "displacement":          OutputKind.STATE_DIRECT,
    "velocity":              OutputKind.STATE_DIRECT,
    "relative_displacement": OutputKind.STATE_RELATIVE,
    "relative_velocity":     OutputKind.STATE_RELATIVE,
    "acceleration":          OutputKind.DERIVED_DYNAMIC,
    "spring_force":          OutputKind.DERIVED_ALGEBRAIC,
    "damper_force":          OutputKind.DERIVED_ALGEBRAIC,
    "force":                 OutputKind.DERIVED_ALGEBRAIC,  # generic force probe

    # Electrical (Faz 5)
    "current":               OutputKind.STATE_DIRECT,
    "capacitor_voltage":     OutputKind.STATE_DIRECT,
    "voltage":               OutputKind.DERIVED_ALGEBRAIC,
    "relative_voltage":      OutputKind.STATE_RELATIVE,

    "unsupported":           OutputKind.UNSUPPORTED,
}

_QUANTITY_TO_KEY: dict[str, str] = {
    # Mechanical
    "displacement":          QK_DISPLACEMENT,
    "velocity":              QK_VELOCITY,
    "relative_displacement": QK_RELATIVE_DISPLACEMENT,
    "relative_velocity":     QK_RELATIVE_VELOCITY,
    "acceleration":          QK_ACCELERATION,
    "spring_force":          QK_SPRING_FORCE,
    "damper_force":          QK_DAMPER_FORCE,
    "force":                 QK_SPRING_FORCE,  # default interpretation

    # Electrical (Faz 5)
    "current":               QK_CURRENT,
    "capacitor_voltage":     QK_CAPACITOR_VOLTAGE,
    "voltage":               QK_VOLTAGE,
    "relative_voltage":      QK_RELATIVE_VOLTAGE,
}


def infer_kind(quantity: str) -> OutputKind:
    """Infer OutputKind from a legacy quantity string.

    Returns ``OutputKind.UNSUPPORTED`` for unknown strings so callers
    always get a valid enum value.
    """
    return _QUANTITY_TO_KIND.get(quantity, OutputKind.UNSUPPORTED)


def infer_quantity_key(quantity: str) -> str:
    """Infer fine-grained quantity_key from a legacy quantity string."""
    return _QUANTITY_TO_KEY.get(quantity, quantity)
