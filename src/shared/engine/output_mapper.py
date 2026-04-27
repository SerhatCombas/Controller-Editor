"""OutputMapper — Wave 3A update.

Maps a probe (BaseProbe / RelativeProbe) to a concrete state-space
output expression: a C row vector and a D row vector for use in

    y = C · x + D · u

Design contract:
  - NEVER produces a wrong TF silently.  Unsupported probe types return
    ``supported_for_tf=False`` with an explicit ``unsupported_reason``.
  - NEVER inspects class names.  Uses probe attributes (``quantity``,
    ``target_component_id``, ``reference_component_id``) only.
  - Uses the ReducedODESystem's ``state_variables`` list as the single
    source of truth for which DOFs exist.

Wave 3A supported quantity types
──────────────────────────────────
  BaseProbe, quantity="displacement"   → c_row[x_{cid}] = 1.0
  BaseProbe, quantity="velocity"       → c_row[v_{cid}] = 1.0
  BaseProbe, quantity="acceleration"   → c_row = A[vel_idx], d_row = B[vel_idx]
  BaseProbe, quantity="spring_force"   → c_row[x_a] = +k, c_row[x_b] = −k
  BaseProbe, quantity="damper_force"   → c_row[v_a] = +d, c_row[v_b] = −d
  BaseProbe, quantity="force"          → same as spring_force (generic force)
  RelativeProbe, quantity="displacement" → c_row[x_target] = 1.0,
                                           c_row[x_ref]    = −1.0
  RelativeProbe, quantity="velocity"   → c_row[v_target] = 1.0,
                                         c_row[v_ref]    = −1.0

Wave 3A NOT supported (explicit reason returned)
────────────────────────────────────────────────
  RelativeProbe whose reference is not an active DOF (source / ground) —
      would require a non-zero D row (direct feedthrough).
  BaseProbe with no recognised quantity string.
  Force probe with no graph context (graph=None).
  Force probe targeting a non-spring/damper component.

Single binding point
────────────────────
The OutputMapper is intentionally the *only* place that knows how probe
attributes map to state-space indices.  UI, equation panel, analysis
panel and TF builder all consume ``OutputExpression``; none of them
re-derive the mapping independently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from src.shared.engine.output_kind import OutputKind

if TYPE_CHECKING:
    from src.shared.engine.symbolic_system import ReducedODESystem

# ---------------------------------------------------------------------------
# Supported quantity literals (Wave 3A scope)
# ---------------------------------------------------------------------------

QuantityType = Literal[
    "displacement",
    "velocity",
    "relative_displacement",
    "relative_velocity",
    "acceleration",
    "spring_force",
    "damper_force",
    "unsupported",
]

# ---------------------------------------------------------------------------
# OutputExpression — single public output type
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class OutputExpression:
    """Result of ``OutputMapper.map()``.

    Attributes:
        output_id: ID of the probe / output channel.
        output_label: Human-readable name.
        quantity_type: Classified physical quantity (Wave 3A types or
            ``"unsupported"``).
        c_row: C-matrix row for this output, length = len(state_variables).
            Zero vector when ``supported_for_tf`` is False.
        d_row: D-matrix row for this output, length = len(input_variables).
            Non-zero for acceleration (DERIVED_DYNAMIC) and displacement
            sources with direct feedthrough.  Zero for all STATE_* and
            DERIVED_ALGEBRAIC outputs.
        supported_for_tf: False when this output cannot be expressed as a
            linear combination of states + inputs in Wave 3A.
        unsupported_reason: Plain-English explanation when
            ``supported_for_tf`` is False.  None otherwise.
        contributing_state_indices: Indices of non-zero entries in c_row
            (empty when not supported).
        contributing_state_names: State variable names at those indices.
        provenance: Ordered trace of decisions made during mapping (useful
            for debugging and decision auditing).
        kind: Coarse OutputKind classification (Wave 3A canonical taxonomy).
            Defaults to ``OutputKind.STATE_DIRECT`` for backward compatibility
            with test fixtures that construct ``OutputExpression`` directly.
    """

    output_id: str
    output_label: str
    quantity_type: QuantityType
    c_row: tuple[float, ...]
    d_row: tuple[float, ...]
    supported_for_tf: bool
    unsupported_reason: str | None
    contributing_state_indices: tuple[int, ...]
    contributing_state_names: tuple[str, ...]
    provenance: tuple[str, ...]
    kind: OutputKind = field(default=OutputKind.STATE_DIRECT)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _zero_c(n: int) -> list[float]:
    return [0.0] * n


def _zero_d(m: int) -> list[float]:
    return [0.0] * m


def _find_state(prefix: str, component_id: str, state_variables: list[str]) -> int | None:
    """Return the index of ``{prefix}_{component_id}`` in state_variables, or None."""
    name = f"{prefix}_{component_id}"
    try:
        return state_variables.index(name)
    except ValueError:
        return None


def _contributing(c_row: list[float], state_variables: list[str]) -> tuple[tuple[int, ...], tuple[str, ...]]:
    indices = tuple(i for i, v in enumerate(c_row) if v != 0.0)
    names = tuple(state_variables[i] for i in indices)
    return indices, names


def _unsupported(
    output_id: str,
    output_label: str,
    quantity_type: QuantityType,
    reason: str,
    n_states: int,
    n_inputs: int,
    provenance: list[str],
    kind: OutputKind = OutputKind.UNSUPPORTED,
) -> OutputExpression:
    provenance.append(f"UNSUPPORTED: {reason}")
    return OutputExpression(
        output_id=output_id,
        output_label=output_label,
        quantity_type=quantity_type,
        c_row=tuple(_zero_c(n_states)),
        d_row=tuple(_zero_d(n_inputs)),
        supported_for_tf=False,
        unsupported_reason=reason,
        contributing_state_indices=(),
        contributing_state_names=(),
        provenance=tuple(provenance),
        kind=kind,
    )


def _find_mass_for_node(node_id: str | None, graph: object) -> str | None:
    """Return the component ID of the DOF-bearing mass at *node_id*, or None.

    A mass component is identified by having a ``"mass"`` key in its
    ``get_parameters()`` dict.  Ground and source components do not.

    Only the DOF port (``port_a``) is considered — the ``reference_port``
    is excluded because it is the absolute reference frame connection, not
    a dynamic degree of freedom.  Matching via ``reference_port`` would
    incorrectly find the mass at the ground node.
    """
    if node_id is None:
        return None
    for cid, comp in graph.components.items():
        params = comp.get_parameters()
        if "mass" not in params:
            continue
        for port in comp.ports:
            if port.name == "reference_port":
                continue  # reference frame — not a DOF port
            if port.node_id == node_id:
                return cid
    return None


# ---------------------------------------------------------------------------
# OutputMapper
# ---------------------------------------------------------------------------

class OutputMapper:
    """Translate a probe into a state-space C / D row pair.

    The mapper is stateless — the same instance can be used for any number
    of probes and ReducedODESystems.

    Usage::

        mapper = OutputMapper()

        # Wave 2 — state-direct/relative quantities (graph optional):
        expr = mapper.map(probe, reduced_ode)

        # Wave 3A — derived quantities (acceleration/force) require graph:
        expr = mapper.map(probe, reduced_ode, graph=graph)

        if expr.supported_for_tf:
            c_row = expr.c_row   # use in C · x
        else:
            print(expr.unsupported_reason)
    """

    def map(
        self,
        probe: object,
        reduced_ode: "ReducedODESystem",
        graph: object = None,
    ) -> OutputExpression:
        """Map *probe* to an OutputExpression using *reduced_ode* state layout.

        Args:
            probe: A ``BaseProbe`` or ``RelativeProbe`` instance (duck-typed;
                only ``id``, ``name``, ``quantity``, ``target_component_id``,
                and ``reference_component_id`` are accessed).
            reduced_ode: A ``ReducedODESystem`` produced by any reducer.
                ``state_variables``, ``input_variables``,
                ``first_order_a``, and ``first_order_b`` are accessed.
            graph: Optional ``SystemGraph``.  Required for derived outputs
                (acceleration, force); ignored for state-direct and
                state-relative quantities.

        Returns:
            A frozen ``OutputExpression`` dataclass.  Always returns a value —
            never raises for unknown probe types; instead returns
            ``supported_for_tf=False`` with an explicit reason.
        """
        state_vars = reduced_ode.state_variables
        input_vars = reduced_ode.input_variables
        n = len(state_vars)
        m = len(input_vars)

        output_id: str = str(getattr(probe, "id", "unknown"))
        output_label: str = str(getattr(probe, "name", output_id))
        quantity: str = str(getattr(probe, "quantity", ""))
        target_cid: str | None = getattr(probe, "target_component_id", None)
        ref_cid: str | None = getattr(probe, "reference_component_id", None)

        prov: list[str] = [
            f"probe_id={output_id}",
            f"quantity={quantity!r}",
            f"target={target_cid!r}",
            f"reference={ref_cid!r}",
            f"n_states={n}",
            f"n_inputs={m}",
        ]

        # Guard: no target component
        if target_cid is None:
            return _unsupported(
                output_id, output_label, "unsupported",
                "Probe has no target_component_id; node-based probes are not "
                "supported in Wave 3A OutputMapper.",
                n, m, prov,
            )

        # ----------------------------------------------------------------
        # Dispatch by quantity
        # ----------------------------------------------------------------
        if quantity == "displacement":
            return self._map_single_state(
                "x", target_cid, ref_cid,
                output_id, output_label, "displacement", "relative_displacement",
                state_vars, n, m, prov,
            )

        if quantity == "velocity":
            return self._map_single_state(
                "v", target_cid, ref_cid,
                output_id, output_label, "velocity", "relative_velocity",
                state_vars, n, m, prov,
            )

        if quantity == "acceleration":
            return self._map_acceleration(
                target_cid, output_id, output_label,
                reduced_ode, state_vars, n, m, prov,
            )

        if quantity in ("force", "spring_force", "damper_force"):
            return self._map_force(
                target_cid, quantity, output_id, output_label,
                reduced_ode, graph, state_vars, n, m, prov,
            )

        return _unsupported(
            output_id, output_label, "unsupported",
            f"Unknown quantity type {quantity!r}.  Wave 3A supports: "
            "displacement, velocity, acceleration, spring_force, damper_force, "
            "(relative variants).",
            n, m, prov,
        )

    # ------------------------------------------------------------------
    # Internal: single-state and relative-state mapping
    # ------------------------------------------------------------------

    def _map_single_state(
        self,
        prefix: str,          # "x" or "v"
        target_cid: str,
        ref_cid: str | None,
        output_id: str,
        output_label: str,
        absolute_qt: QuantityType,
        relative_qt: QuantityType,
        state_vars: list[str],
        n: int,
        m: int,
        prov: list[str],
    ) -> OutputExpression:
        """Handle displacement or velocity, absolute or relative."""

        target_idx = _find_state(prefix, target_cid, state_vars)
        prov.append(f"target_state={prefix}_{target_cid} → index={target_idx}")

        if target_idx is None:
            return _unsupported(
                output_id, output_label, "unsupported",
                f"State variable '{prefix}_{target_cid}' not found in "
                f"ReducedODESystem.state_variables.  The component may be a "
                f"source, ground, or non-DOF element.",
                n, m, prov,
            )

        # ---- Absolute (no reference) ----
        if ref_cid is None:
            c = _zero_c(n)
            c[target_idx] = 1.0
            indices, names = _contributing(c, state_vars)
            prov.append(f"absolute {prefix}-state mapping: C[{target_idx}]=1.0")
            return OutputExpression(
                output_id=output_id,
                output_label=output_label,
                quantity_type=absolute_qt,
                c_row=tuple(c),
                d_row=tuple(_zero_d(m)),
                supported_for_tf=True,
                unsupported_reason=None,
                contributing_state_indices=indices,
                contributing_state_names=names,
                provenance=tuple(prov),
                kind=OutputKind.STATE_DIRECT,
            )

        # ---- Relative (has reference) ----
        ref_idx = _find_state(prefix, ref_cid, state_vars)
        prov.append(f"reference_state={prefix}_{ref_cid} → index={ref_idx}")

        if ref_idx is None:
            return _unsupported(
                output_id, output_label, "unsupported",
                f"Reference state '{prefix}_{ref_cid}' not found in "
                f"ReducedODESystem.state_variables.  If '{ref_cid}' is a "
                f"displacement source (e.g. RandomRoad), the output involves "
                f"a non-zero D row (direct feedthrough), which is Wave 3 scope.",
                n, m, prov,
            )

        c = _zero_c(n)
        c[target_idx] = 1.0
        c[ref_idx] = -1.0
        indices, names = _contributing(c, state_vars)
        prov.append(
            f"relative {prefix}-state mapping: C[{target_idx}]=1.0, "
            f"C[{ref_idx}]=-1.0"
        )
        return OutputExpression(
            output_id=output_id,
            output_label=output_label,
            quantity_type=relative_qt,
            c_row=tuple(c),
            d_row=tuple(_zero_d(m)),
            supported_for_tf=True,
            unsupported_reason=None,
            contributing_state_indices=indices,
            contributing_state_names=names,
            provenance=tuple(prov),
            kind=OutputKind.STATE_RELATIVE,
        )

    # ------------------------------------------------------------------
    # Internal: acceleration (DERIVED_DYNAMIC)
    # ------------------------------------------------------------------

    def _map_acceleration(
        self,
        target_cid: str,
        output_id: str,
        output_label: str,
        reduced_ode: "ReducedODESystem",
        state_vars: list[str],
        n: int,
        m: int,
        prov: list[str],
    ) -> OutputExpression:
        """Derive acceleration from the first-order A/B matrices.

        ÿ = A[vel_idx] · x + B[vel_idx] · u
        → c_row = A[vel_idx],  d_row = B[vel_idx]
        """
        vel_idx = _find_state("v", target_cid, state_vars)
        prov.append(f"acceleration: velocity_state=v_{target_cid} → index={vel_idx}")

        if vel_idx is None:
            return _unsupported(
                output_id, output_label, "unsupported",
                f"Velocity state 'v_{target_cid}' not found in state vector; "
                "cannot derive acceleration for this component.",
                n, m, prov, kind=OutputKind.UNSUPPORTED,
            )

        # ẍ = A[vel_idx] · x + B[vel_idx] · u
        c_row = tuple(float(v) for v in reduced_ode.first_order_a[vel_idx])
        d_row = tuple(float(v) for v in reduced_ode.first_order_b[vel_idx])

        indices, names = _contributing(list(c_row), state_vars)
        prov.append(
            f"c_row = first_order_a[{vel_idx}]; "
            f"d_row = first_order_b[{vel_idx}]"
        )

        return OutputExpression(
            output_id=output_id,
            output_label=output_label,
            quantity_type="acceleration",
            c_row=c_row,
            d_row=d_row,
            supported_for_tf=True,
            unsupported_reason=None,
            contributing_state_indices=indices,
            contributing_state_names=names,
            provenance=tuple(prov),
            kind=OutputKind.DERIVED_DYNAMIC,
        )

    # ------------------------------------------------------------------
    # Internal: force (DERIVED_ALGEBRAIC)
    # ------------------------------------------------------------------

    def _map_force(
        self,
        target_cid: str,
        quantity: str,
        output_id: str,
        output_label: str,
        reduced_ode: "ReducedODESystem",
        graph: object,
        state_vars: list[str],
        n: int,
        m: int,
        prov: list[str],
    ) -> OutputExpression:
        """Map spring or damper force to a C row.

        Spring: F = k · (x_a − x_b)  → c_row[x_a] += k, c_row[x_b] -= k
        Damper: F = d · (v_a − v_b)  → c_row[v_a] += d, c_row[v_b] -= d

        Requires a SystemGraph to resolve connected DOFs and parameters.
        """
        if graph is None:
            return _unsupported(
                output_id, output_label, "unsupported",
                "Force output requires graph context (graph=None passed to "
                "OutputMapper.map()).  Pass the SystemGraph as the 'graph' "
                "keyword argument.",
                n, m, prov, kind=OutputKind.UNSUPPORTED,
            )

        comp = graph.components.get(target_cid)
        if comp is None:
            return _unsupported(
                output_id, output_label, "unsupported",
                f"Component '{target_cid}' not found in graph.components.",
                n, m, prov, kind=OutputKind.UNSUPPORTED,
            )

        params = comp.get_parameters()

        # Classify: spring (F = k·Δx) or damper (F = d·Δv)
        if "stiffness" in params:
            param_val = float(params["stiffness"])
            state_prefix = "x"
            qt: QuantityType = "spring_force"
            prov.append(f"spring_force: k={param_val} N/m")
        elif "damping" in params:
            param_val = float(params["damping"])
            state_prefix = "v"
            qt = "damper_force"
            prov.append(f"damper_force: d={param_val} N·s/m")
        else:
            return _unsupported(
                output_id, output_label, "unsupported",
                f"Component '{target_cid}' has neither 'stiffness' nor "
                f"'damping' parameter; cannot compute force.",
                n, m, prov, kind=OutputKind.UNSUPPORTED,
            )

        # Identify the two ports
        try:
            port_a = comp.port("port_a")
            port_b = comp.port("port_b")
        except (KeyError, StopIteration, AttributeError):
            return _unsupported(
                output_id, output_label, "unsupported",
                f"Component '{target_cid}' does not expose 'port_a' and "
                f"'port_b'; cannot resolve connected DOFs.",
                n, m, prov, kind=OutputKind.UNSUPPORTED,
            )

        node_a = port_a.node_id
        node_b = port_b.node_id
        prov.append(f"port_a.node_id={node_a!r}, port_b.node_id={node_b!r}")

        # Find the mass (DOF) at each end
        mass_a = _find_mass_for_node(node_a, graph)
        mass_b = _find_mass_for_node(node_b, graph)
        prov.append(f"mass_at_port_a={mass_a!r}, mass_at_port_b={mass_b!r}")

        if mass_a is None and mass_b is None:
            return _unsupported(
                output_id, output_label, "unsupported",
                f"No DOF-bearing mass component found at either port of "
                f"'{target_cid}'.  Both ends appear to be grounded or "
                f"source-connected.",
                n, m, prov, kind=OutputKind.UNSUPPORTED,
            )

        # Build C row: F = param · (state_a − state_b)
        c = _zero_c(n)

        if mass_a is not None:
            idx_a = _find_state(state_prefix, mass_a, state_vars)
            if idx_a is not None:
                c[idx_a] += param_val
                prov.append(
                    f"C[{idx_a}] ({state_prefix}_{mass_a}) += {param_val}"
                )

        if mass_b is not None:
            idx_b = _find_state(state_prefix, mass_b, state_vars)
            if idx_b is not None:
                c[idx_b] -= param_val
                prov.append(
                    f"C[{idx_b}] ({state_prefix}_{mass_b}) -= {param_val}"
                )

        if all(v == 0.0 for v in c):
            return _unsupported(
                output_id, output_label, "unsupported",
                f"Force C-row for '{target_cid}' is all-zero: connected mass "
                f"state(s) not present in ReducedODESystem.state_variables.  "
                f"The component may be grounded on both sides, or the connected "
                f"masses are inactive DOFs.",
                n, m, prov, kind=OutputKind.UNSUPPORTED,
            )

        indices, names = _contributing(c, state_vars)
        return OutputExpression(
            output_id=output_id,
            output_label=output_label,
            quantity_type=qt,
            c_row=tuple(c),
            d_row=tuple(_zero_d(m)),
            supported_for_tf=True,
            unsupported_reason=None,
            contributing_state_indices=indices,
            contributing_state_names=names,
            provenance=tuple(prov),
            kind=OutputKind.DERIVED_ALGEBRAIC,
        )
