"""PolymorphicDAEReducer — Wave 1 replacement for DAEReducer.

Design contract:
  - NEVER inspects component class names or ``__class__.__name__``.
  - NEVER reads ``component_records["type"]`` or ``metadata["role"]``.
  - Determines DOF structure via ``get_state_contribution()`` (inertial flag).
  - Determines sources via ``InputRouter`` (``get_source_descriptor()``).
  - Assembles M / D / K matrices via ``contribute_mass/damping/stiffness()``.
  - Handles displacement-source coupling via the "extended node index" pattern
    (negative column indices → input-matrix column).
  - Produces a ``ReducedODESystem`` whose shape and semantics match the legacy
    ``DAEReducer`` output, enabling numerical parity testing (Commit 5).

Boundary with InputRouter:
  InputRouter  →  topology only (who drives what node, what kind)
  PolymorphicDAEReducer  →  all matrix algebra (M·ẍ + D·ẋ + K·x = B·u)
"""
from __future__ import annotations

import sympy

from app.core.base.contribution import MatrixContribution
from app.core.symbolic.input_router import InputRouter, RoutingResult
from app.core.symbolic.symbolic_system import ReducedODESystem, SymbolicSystem


class PolymorphicDAEReducer:
    """DAE-to-ODE reducer driven purely by the component polymorphic interface.

    Usage::

        reducer = PolymorphicDAEReducer()
        reduced = reducer.reduce(graph, symbolic_system)

    The ``reduced`` object is a ``ReducedODESystem`` numerically compatible
    with the one produced by the legacy ``DAEReducer``.
    """

    def __init__(self, input_router: InputRouter | None = None) -> None:
        self._router = input_router or InputRouter()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reduce(self, graph: object, symbolic_system: SymbolicSystem) -> ReducedODESystem:
        """Reduce the system DAE to first-order ODE form.

        Args:
            graph: ``SystemGraph`` instance (accessed via .components only).
            symbolic_system: Output of ``EquationBuilder``.

        Returns:
            ``ReducedODESystem`` with numeric M / D / K / B matrices and A / B
            first-order state-space matrices.
        """
        components = list(self._iter_components(graph))

        # 1. Identify inertial DOFs and build primary node ordering
        node_order, node_index = self._build_node_index(components)
        dimension = len(node_order)

        # 2. Route inputs — force and displacement sources
        routing: RoutingResult = self._router.route(graph, node_index)

        # 3. Build extended node index: active DOFs (≥0) + displacement source
        #    nodes (negative sentinels) so contribute_* can emit coupling entries.
        #
        #    IMPORTANT — unified column ordering:
        #    The legacy DAEReducer assigns B-matrix columns by iterating ALL sources
        #    in graph-traversal order (force and displacement interleaved, no
        #    separation).  We must match that convention exactly.
        #
        #    We therefore use routing.routes (all sources in graph order) as the
        #    canonical column sequence, and encode each displacement source's
        #    UNIFIED column index as its negative sentinel:
        #      sentinel = -(unified_col + 1)
        #    so that later:
        #      unified_col = -(sentinel + 1) = -(col + 1)
        #
        #    This produces the same column order as the legacy reducer regardless
        #    of how many force vs. displacement sources are present.
        extended_index = dict(node_index)
        for unified_col, route in enumerate(routing.routes):
            if route.source_kind == "displacement" and route.driven_node_id:
                extended_index[route.driven_node_id] = -(unified_col + 1)

        # 4. Count inputs: all sources in unified order
        input_count = max(len(routing.routes), 1)

        # 5. Collect matrix contributions from all components
        raw_mass: list[MatrixContribution] = []
        raw_damping: list[MatrixContribution] = []
        raw_stiffness: list[MatrixContribution] = []

        for comp in components:
            raw_mass.extend(comp.contribute_mass(node_index))           # only active DOFs
            raw_damping.extend(comp.contribute_damping(extended_index)) # extended for coupling
            raw_stiffness.extend(comp.contribute_stiffness(extended_index))

        # 6. Build symbol substitution map (symbol → numeric value)
        sym_subs = self._build_symbol_subs(components)

        # 7. Assemble numeric M, D, K matrices; move displacement-coupling to B
        mass_matrix = self._zero(dimension, dimension)
        damping_matrix = self._zero(dimension, dimension)
        stiffness_matrix = self._zero(dimension, dimension)
        input_matrix = self._zero(dimension, input_count)

        # Force-source columns start at index 0
        # Displacement-source columns come after force columns: force_count + disp_input_idx
        for mc in raw_mass:
            if mc.row >= 0 and mc.col >= 0:
                mass_matrix[mc.row][mc.col] += self._eval(mc.value, sym_subs)

        for mc_list, matrix in [(raw_damping, damping_matrix), (raw_stiffness, stiffness_matrix)]:
            for mc in mc_list:
                row, col = mc.row, mc.col
                val = self._eval(mc.value, sym_subs)
                if row < 0:
                    continue  # rare: ground node on left — skip
                if col >= 0:
                    # Active DOF → goes into M / D / K
                    matrix[row][col] += val
                else:
                    # Negative col encodes the UNIFIED column index of the
                    # displacement source: unified_col = -(col + 1).
                    #
                    # Sign convention: the off-diagonal Laplacian entry is
                    # K[i,j] = -k (MatrixContribution value = -k_sym, val = -k).
                    # When we move this term to the RHS (B·u side), it negates:
                    #   B[i, input_col] = -K[i,j] = -(-k) = +k
                    # Therefore we SUBTRACT val (which is already negative):
                    #   input_matrix[i][col] -= val  ≡  input_matrix[i][col] += k
                    # This matches the legacy DAEReducer's
                    #   input_matrix[idx_a][input_b] += coefficient  (positive k).
                    input_col = -(col + 1)
                    if input_col < input_count:
                        input_matrix[row][input_col] -= val

        # 8. Force-source B-matrix entries.
        #
        #    A force source applies +F at its driven node and -F at its reference
        #    node (Newton's 3rd law).  If the reference node is an active DOF
        #    (e.g. a chassis-mounted actuator between body and wheel), the legacy
        #    DAEReducer subtracts 1.0 there.  We mirror that exactly.
        #
        #    unified_col is the position of this force source in routing.routes
        #    (same iteration order as legacy component_records traversal).
        for unified_col, route in enumerate(routing.routes):
            if route.source_kind != "force":
                continue
            if route.driven_dof_index >= 0:
                input_matrix[route.driven_dof_index][unified_col] += 1.0
            # Reference-node contribution (only when reference is an active DOF)
            if route.reference_node_id:
                ref_dof = node_index.get(route.reference_node_id)
                if ref_dof is not None:
                    input_matrix[ref_dof][unified_col] -= 1.0

        # 9. Build state variable list (matching legacy convention: x_… then v_…)
        state_variables = self._build_state_variables(components, node_order, node_index)

        # 10. Build input variable list in unified graph-traversal order.
        #     This matches the legacy DAEReducer's column ordering exactly.
        input_variables = [route.input_variable_name for route in routing.routes]
        if not input_variables:
            input_variables = ["u_undefined"]

        # 11. First-order conversion: ẋ = Ax + Bu
        first_order_a, first_order_b = self._to_first_order(
            node_order=node_order,
            mass_matrix=mass_matrix,
            damping_matrix=damping_matrix,
            stiffness_matrix=stiffness_matrix,
            input_matrix=input_matrix,
        )

        state_index_lookup = {sv: idx for idx, sv in enumerate(state_variables)}

        return ReducedODESystem(
            state_variables=state_variables,
            input_variables=input_variables,
            output_definitions=dict(symbolic_system.output_definitions),
            mass_matrix=mass_matrix,
            damping_matrix=damping_matrix,
            stiffness_matrix=stiffness_matrix,
            input_matrix=input_matrix,
            first_order_a=first_order_a,
            first_order_b=first_order_b,
            node_order=node_order,
            metadata={
                "reduction_type": "polymorphic_linear_mechanical",
                "algebraic_constraint_count": len(symbolic_system.algebraic_constraints),
                "component_records": symbolic_system.metadata.get("component_records", {}),
                "output_records": symbolic_system.metadata.get("output_records", {}),
                "state_index_lookup": state_index_lookup,
                "derivative_links": symbolic_system.metadata.get("derivative_links", {}),
                "force_source_count": len(routing.force_sources),
                "displacement_source_count": len(routing.displacement_sources),
                "routing_summary": {
                    route.component_id: {
                        "kind": route.source_kind,
                        "driven_dof_index": route.driven_dof_index,
                    }
                    for route in routing.routes
                },
            },
        )

    # ------------------------------------------------------------------
    # DOF / node ordering
    # ------------------------------------------------------------------

    def _build_node_index(self, components: list) -> tuple[list[str], dict[str, int]]:
        """Identify inertial state-carrying components and build DOF ordering.

        Convention: the same component-port ordering used by the legacy reducer
        (port_a of inertial components, in traversal order, deduplicated).
        """
        node_order: list[str] = []
        seen: set[str] = set()

        for comp in components:
            sc = comp.get_state_contribution()
            if sc is None or not sc.stores_inertial_energy:
                continue
            try:
                p = comp.port(sc.owning_port_name)
            except (KeyError, AttributeError):
                continue
            if p.node_id is None or p.node_id in seen:
                continue
            node_order.append(p.node_id)
            seen.add(p.node_id)

        node_index = {nid: idx for idx, nid in enumerate(node_order)}
        return node_order, node_index

    # ------------------------------------------------------------------
    # State variable naming
    # ------------------------------------------------------------------

    def _build_state_variables(
        self,
        components: list,
        node_order: list[str],
        node_index: dict[str, int],
    ) -> list[str]:
        """Build canonical [x_0, x_1, … v_0, v_1, …] state variable list.

        Matches the legacy reducer's displacement-first ordering.
        """
        # Map each active node to the component that owns it
        node_to_comp: dict[str, object] = {}
        for comp in components:
            sc = comp.get_state_contribution()
            if sc is None or not sc.stores_inertial_energy:
                continue
            try:
                p = comp.port(sc.owning_port_name)
            except (KeyError, AttributeError):
                continue
            if p.node_id and p.node_id in node_index:
                node_to_comp[p.node_id] = comp

        displacement_states: list[str] = []
        velocity_states: list[str] = []

        for node_id in node_order:
            comp = node_to_comp.get(node_id)
            if comp is not None:
                states = comp.get_states()
                x_states = [s for s in states if s.startswith("x_")]
                v_states = [s for s in states if s.startswith("v_")]
                displacement_states.append(x_states[0] if x_states else f"x_{comp.id}")
                velocity_states.append(v_states[0] if v_states else f"v_{comp.id}")
            else:
                idx = node_index[node_id]
                displacement_states.append(f"x_{idx}")
                velocity_states.append(f"v_{idx}")

        return displacement_states + velocity_states

    # ------------------------------------------------------------------
    # Symbol substitution
    # ------------------------------------------------------------------

    def _build_symbol_subs(self, components: list) -> dict:
        """Build {sympy.Symbol → float} substitution for all component parameters.

        Convention used in contribute_*: ``sympy.Symbol(f"m_{comp.id}")`` for mass,
        ``k_{comp.id}`` for stiffness, ``d_{comp.id}`` for damping.
        """
        subs: dict = {}
        for comp in components:
            cid = comp.id
            params: dict = getattr(comp, "parameters", {}) or {}
            if "mass" in params:
                subs[sympy.Symbol(f"m_{cid}")] = float(params["mass"])
            if "stiffness" in params:
                subs[sympy.Symbol(f"k_{cid}")] = float(params["stiffness"])
            if "damping" in params:
                subs[sympy.Symbol(f"d_{cid}")] = float(params["damping"])
        return subs

    # ------------------------------------------------------------------
    # Numeric evaluation
    # ------------------------------------------------------------------

    @staticmethod
    def _eval(value: object, subs: dict) -> float:
        """Evaluate a sympy expression (or plain float) to a Python float."""
        if isinstance(value, (int, float)):
            return float(value)
        try:
            substituted = value.subs(subs)  # type: ignore[union-attr]
            return float(substituted)
        except (AttributeError, TypeError):
            return float(value)

    # ------------------------------------------------------------------
    # Matrix utilities (mirrored from DAEReducer for self-containment)
    # ------------------------------------------------------------------

    @staticmethod
    def _zero(rows: int, cols: int) -> list[list[float]]:
        return [[0.0] * cols for _ in range(rows)]

    @staticmethod
    def _identity(size: int) -> list[list[float]]:
        m = [[0.0] * size for _ in range(size)]
        for i in range(size):
            m[i][i] = 1.0
        return m

    @staticmethod
    def _invert_diagonal(matrix: list[list[float]]) -> list[list[float]]:
        n = len(matrix)
        inv = [[0.0] * n for _ in range(n)]
        for i, row in enumerate(matrix):
            v = row[i]
            inv[i][i] = 0.0 if v == 0.0 else 1.0 / v
        return inv

    @staticmethod
    def _multiply(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
        if not left or not right:
            return []
        rows, cols, shared = len(left), len(right[0]), len(right)
        result = [[0.0] * cols for _ in range(rows)]
        for i in range(rows):
            for j in range(cols):
                result[i][j] = sum(left[i][k] * right[k][j] for k in range(shared))
        return result

    @staticmethod
    def _negate(matrix: list[list[float]]) -> list[list[float]]:
        return [[-v for v in row] for row in matrix]

    def _to_first_order(
        self,
        *,
        node_order: list[str],
        mass_matrix: list[list[float]],
        damping_matrix: list[list[float]],
        stiffness_matrix: list[list[float]],
        input_matrix: list[list[float]],
    ) -> tuple[list[list[float]], list[list[float]]]:
        """Convert Mẍ + Dẋ + Kx = Bu to ẋ = Ax + Bu (first-order form)."""
        dof = len(node_order)
        if dof == 0:
            return [], []

        m_inv = self._invert_diagonal(mass_matrix)
        top_a = self._zero(dof, dof) + [list(row) for row in self._identity(dof)]
        bottom_a = (
            self._negate(self._multiply(m_inv, stiffness_matrix))
            + self._negate(self._multiply(m_inv, damping_matrix))
        )

        # Build A row by row: top = [0 | I], bottom = [-M⁻¹K | -M⁻¹D]
        # top_a and bottom_a are already split; zip them together per-row
        a_top_left = self._zero(dof, dof)
        a_top_right = self._identity(dof)
        a_bot_left = self._negate(self._multiply(m_inv, stiffness_matrix))
        a_bot_right = self._negate(self._multiply(m_inv, damping_matrix))

        a_matrix = [
            a_top_left[i] + a_top_right[i] for i in range(dof)
        ] + [
            a_bot_left[i] + a_bot_right[i] for i in range(dof)
        ]

        n_inputs = len(input_matrix[0]) if input_matrix else 0
        top_b = self._zero(dof, n_inputs)
        bottom_b = self._multiply(m_inv, input_matrix)
        b_matrix = top_b + bottom_b

        return a_matrix, b_matrix

    # ------------------------------------------------------------------
    # Graph iteration helper
    # ------------------------------------------------------------------

    @staticmethod
    def _iter_components(graph: object):
        components = getattr(graph, "components", None)
        if components is None:
            raise AttributeError(
                "PolymorphicDAEReducer expected 'graph' to have a 'components' attribute."
            )
        if isinstance(components, dict):
            yield from components.values()
        else:
            yield from components
