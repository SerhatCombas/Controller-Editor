"""Source descriptor metadata used by the InputRouter.

This module is part of Wave 1. It enforces a clean separation between a
source component (which describes *what it drives*) and the boundary /
topology logic that converts that declaration into actual B-matrix
contributions (which is the InputRouter's and reducer's job).

Under the legacy DAEReducer, source handling was split across several
places: metadata["role"] == "source", source_node_to_input dicts,
force_source_records, and implicit conventions inside
`_accumulate_branch`. Wave 1 centralizes all of that into two layers:

1. Source components expose a `SourceDescriptor` via
   `get_source_descriptor()`. They make no algebraic decisions.
2. The InputRouter consumes descriptors plus the graph topology and
   emits a RoutingResult. The polymorphic reducer consumes that
   RoutingResult to fill B and shape M/D/K accordingly.

This module only contains the descriptor dataclass; the router and the
reducer live in app/core/symbolic/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


SourceKind = Literal[
    "force",          # mechanical force (Newtons), goes directly into B
    "displacement",   # prescribed position, becomes an input node
    "velocity",       # prescribed velocity, becomes an input node
    "torque",         # rotational analog of force
    "voltage",        # electrical across source
    "current",        # electrical through source
]


@dataclass(frozen=True, slots=True)
class SourceDescriptor:
    """Describes how a source component drives the system topologically.

    The descriptor carries no algebraic intent; it only identifies which
    port drives which boundary, what kind of signal it is, and what
    symbolic name the input will be registered under. The InputRouter
    and reducer are responsible for translating this into matrix entries.

    Attributes:
        kind: The signal type injected by this source.
        driven_port_name: Name of the port whose node is forced by the
            source signal.
        reference_port_name: Optional name of the port providing the
            "other side" of the source (e.g. ground for a grounded force).
            May be None for single-ended sources.
        input_variable_name: The symbolic name that will appear in the
            input vector. Prefer physical channel names when a stable port
            variable exists, e.g. force sources use ``f_<component_id>_out``
            and road displacement sources use ``r_<component_id>``. Runtime
            adapters may still accept legacy ``u_<component_id>`` aliases.
        amplitude_parameter: Optional name of the parameter key in the
            component's `parameters` dict that carries the nominal
            amplitude (used by the UI when rendering defaults).
    """

    kind: SourceKind
    driven_port_name: str
    reference_port_name: str | None
    input_variable_name: str
    amplitude_parameter: str | None = None
