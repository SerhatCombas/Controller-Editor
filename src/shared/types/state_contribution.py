"""State contribution metadata for components.

This module is part of Wave 1. Its purpose is to let a component declare
"I own N degree-of-freedom state variables" without tying that decision to
the component's class name. Historically the DAEReducer asked
`if record["type"] in {"Mass", "Wheel"}` — this created a hard-coded
coupling between the reducer and the mechanical translational domain.

By replacing that check with a polymorphic `get_state_contribution()`
method that returns (or does not return) an instance of this dataclass,
new component types (electrical inductors, rotational inertias, thermal
capacitances, ...) can be added later without touching the reducer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


StateKind = Literal[
    # Energy-storage classifications used by the mechanical/electrical/thermal
    # domains today. These names match the runtime values returned by the
    # current Mass / Spring / Wheel implementations.
    "inertial",                # mass-like: stores kinetic energy (Mass, Wheel)
    "potential",               # spring-like: stores potential energy (Spring)
    "transducer",              # state-less force/displacement passthrough
                               # (Faz 4d-2b: Wheel with mass=0)
    # Canonical state-pair classifications retained for future use.
    "position_velocity",       # mechanical translational: x, v
    "angle_angular_velocity",  # mechanical rotational: theta, omega
    "charge_voltage",          # electrical capacitance: q, v_C
    "flux_current",            # electrical inductance: phi, i_L
    "thermal_energy",          # thermal capacitance: single state T
]


@dataclass(frozen=True, slots=True)
class StateContribution:
    """Declares that a component owns degree-of-freedom state variables.

    Only components that store energy (inertial or potential) return a
    StateContribution from `get_state_contribution()`. Dissipative elements
    (dampers, resistors) and pure topology elements (grounds, probes) return
    None, because they do not introduce new integration states.

    Attributes:
        stores_inertial_energy: True for masses, inductors, etc.
        stores_potential_energy: True for springs, capacitors, etc.
            (Wave 1 reducer only treats inertial contributors as DoF owners;
            potential-energy storage is kept as a separate bit for future use.)
        state_kind: Which canonical state pair this component produces.
        dof_count: Number of independent DoFs introduced (typically 1).
        owning_port_name: Name of the port whose node will be promoted to a
            state node. For a Mass this is typically "port_a".
    """

    stores_inertial_energy: bool = False
    stores_potential_energy: bool = False
    state_kind: StateKind = "position_velocity"
    dof_count: int = 1
    owning_port_name: str | None = None
