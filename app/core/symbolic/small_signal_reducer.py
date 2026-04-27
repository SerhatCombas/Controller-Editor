"""SmallSignalLinearReducer — symbolic equation → state-space (T2.2).

Scope (intentionally narrow per architecture feedback):
  - Handles small LTI circuits (RC, RL, RLC) and mass-spring-damper systems.
  - Assumes all equations are linear in states and inputs.
  - Supports a tiny index-reduction fallback for algebraically constrained
    candidate states (enough for the current mass-spring-damper helper path).
  - Assumes no algebraic loops, no higher-index DAE, no overconstrained sources.
  - Uses sympy substitution to eliminate algebraic variables, then
    collects coefficients to form A, B, C, D matrices.

This is NOT a general Modelica-style compiler.  It handles the MVP
subset described in SYSTEM_MODELING_ROADMAP.md.

Output: StateSpaceModel (same contract as PolymorphicDAEReducer output).
"""

from __future__ import annotations

from dataclasses import dataclass

import sympy
from sympy import Matrix, Symbol, zeros

from app.core.symbolic.symbolic_flattener import FlatSystem, _der_func
from app.core.symbolic.symbolic_system import StateSpaceModel


@dataclass
class ReductionResult:
    """Intermediate result before numeric evaluation."""
    state_space: StateSpaceModel
    symbolic_A: sympy.Matrix | None = None
    symbolic_B: sympy.Matrix | None = None


class SmallSignalLinearReducer:
    """Reduce a FlatSystem of symbolic equations to state-space form.

    Algorithm:
      1. Substitute all parameters with numeric values.
      2. Collect all equations into residual form: f_i(...) = 0.
      3. Identify der(x) terms → state derivatives.
      4. Solve for algebraic variables in terms of states and inputs.
      5. Substitute back to get dx/dt = A*x + B*u.
      6. Build C, D from output expressions.

    Limitations:
      - Linear systems only (no jacobian linearization).
      - No singular mass matrix handling.
      - Only narrow constrained-state fallback, not general index reduction.
    """

    def reduce(self, flat: FlatSystem) -> StateSpaceModel:
        """Reduce a flattened system to StateSpaceModel."""

        if not flat.equations:
            return StateSpaceModel()

        states = flat.state_symbols
        inputs = flat.input_symbols
        params = flat.parameter_map

        n = len(states)
        m = len(inputs)

        if n == 0:
            # Pure algebraic system — no dynamics
            return StateSpaceModel(
                state_variables=[],
                input_variables=[str(u) for u in inputs],
                output_variables=[str(o) for o in flat.output_symbols],
            )

        # Create derivative symbols: der(x) → dx
        der_syms: dict[sympy.Expr, Symbol] = {}
        der_to_state: dict[Symbol, Symbol] = {}
        for x in states:
            dx = Symbol(f"d_{x.name}", real=True)
            der_syms[_der_func(x)] = dx
            der_to_state[dx] = x

        # -----------------------------------------------------------------
        # Step 1: Substitute parameters and replace der() with proxy symbols
        # -----------------------------------------------------------------
        residuals: list[sympy.Expr] = []
        for eq in flat.equations:
            r = (eq.lhs - eq.rhs)
            # Substitute parameters
            r = r.subs(params)
            # Replace der(x) with dx proxy symbols
            r = r.subs(der_syms)
            residuals.append(r)

        # -----------------------------------------------------------------
        # Step 2: Classify variables
        # -----------------------------------------------------------------
        all_unknowns: set[Symbol] = set()
        for r in residuals:
            all_unknowns |= r.free_symbols

        derivative_set = set(der_to_state.keys())
        state_set = set(states)
        input_set = set(inputs)

        # Algebraic unknowns = everything except states, inputs, derivatives
        algebraic_set = all_unknowns - derivative_set - state_set - input_set

        algebraic_list = sorted(algebraic_set, key=str)

        # -----------------------------------------------------------------
        # Step 3: Solve for algebraic variables + derivatives
        # -----------------------------------------------------------------
        # We need to solve the system for all algebraic vars and derivative vars
        solve_for = list(derivative_set) + algebraic_list

        try:
            solution = sympy.solve(residuals, solve_for, dict=True)
        except Exception as e:
            solution = []  # Will trigger fallback below

        # -----------------------------------------------------------------
        # Step 3b: Fallback — demote constrained states (index-2 DAE)
        # -----------------------------------------------------------------
        # If the initial solve fails, some candidate states may be
        # algebraically constrained to other states (classic index-2
        # situation, e.g. damper's v_diff = s_b - s_a in an MSD system).
        #
        # Strategy: include candidate states in solve_for. States that
        # sympy can solve for (express as function of other states) are
        # "constrained" — demote them to algebraic and re-solve.
        if not solution:
            extended_for = solve_for + sorted(state_set, key=str)
            try:
                ext_solution = sympy.solve(residuals, extended_for, dict=True)
            except Exception:
                ext_solution = []

            if ext_solution:
                ext_sol = ext_solution[0]
                # States that got solved for are constrained
                demoted: set[Symbol] = set()
                for x in list(state_set):
                    if x in ext_sol:
                        demoted.add(x)

                if demoted:
                    # -------------------------------------------------
                    # Index reduction: for each demoted state x,
                    # add the differentiated algebraic constraint.
                    #
                    # If ext_sol says x = f(true_states, inputs), then
                    #   der(x) = sum( df/ds_i * der(s_i) )
                    # which gives: d_x = sum( df/ds_i * d_s_i )
                    #
                    # This equation is NOT in the original residuals
                    # (it requires differentiating an algebraic constraint)
                    # and must be added explicitly.
                    # -------------------------------------------------
                    remaining_states = state_set - demoted
                    for dx_dem, x_dem in list(der_to_state.items()):
                        if x_dem not in demoted:
                            continue
                        x_expr = ext_sol[x_dem]
                        # Differentiate: d_x = sum(d(expr)/d(s) * d_s)
                        diff_expr = sympy.Integer(0)
                        for s_true in remaining_states:
                            coeff = sympy.diff(x_expr, s_true)
                            if coeff != 0:
                                d_s = der_syms[_der_func(s_true)]
                                diff_expr += coeff * d_s
                        # Also handle input dependencies
                        for u in input_set:
                            coeff = sympy.diff(x_expr, u)
                            if coeff != 0:
                                # Inputs are constant (no der(u))
                                pass  # der(u) = 0 for step inputs
                        # Add: d_x_dem - diff_expr = 0
                        residuals.append(dx_dem - diff_expr)

                    # Demote constrained states → algebraic
                    state_set -= demoted
                    algebraic_set |= demoted
                    # Also demote their derivative proxies
                    for dx, x in list(der_to_state.items()):
                        if x in demoted:
                            derivative_set.discard(dx)
                            algebraic_set.add(dx)
                            del der_to_state[dx]

                    # Rebuild
                    states = [x for x in states if x not in demoted]
                    n = len(states)
                    algebraic_list = sorted(algebraic_set, key=str)
                    solve_for = list(derivative_set) + algebraic_list

                    # Re-solve with corrected classification + new equations
                    try:
                        solution = sympy.solve(
                            residuals, solve_for, dict=True
                        )
                    except Exception as e:
                        raise RuntimeError(
                            f"SmallSignalLinearReducer: solve failed even after "
                            f"demoting constrained states {demoted}. Error: {e}"
                        ) from e

        if not solution:
            raise RuntimeError(
                "SmallSignalLinearReducer: no solution found. "
                "System may be overconstrained or inconsistent."
            )

        # Take first solution (for linear systems there should be exactly one)
        sol = solution[0]

        # -----------------------------------------------------------------
        # Step 4: Extract dx/dt = f(x, u) and build A, B
        # -----------------------------------------------------------------
        A = zeros(n, n)
        B = zeros(n, m)

        for i, x in enumerate(states):
            dx = der_syms[_der_func(x)]
            if dx not in sol:
                raise RuntimeError(
                    f"SmallSignalLinearReducer: could not solve for der({x}). "
                    f"Missing equation or underdetermined system."
                )
            expr = sol[dx]

            # Collect coefficients for state variables
            for j, xj in enumerate(states):
                coeff = expr.coeff(xj)
                A[i, j] = coeff

            # Collect coefficients for input variables
            for j, uj in enumerate(inputs):
                coeff = expr.coeff(uj)
                B[i, j] = coeff

        # -----------------------------------------------------------------
        # Step 5: Build C, D from output expressions
        # -----------------------------------------------------------------
        p = len(flat.output_symbols)
        C = zeros(p, n)
        D = zeros(p, m)

        for i, osym in enumerate(flat.output_symbols):
            oexpr = flat.output_expressions.get(osym, osym)
            # Substitute algebraic vars with their solutions
            oexpr = oexpr.subs(sol).subs(params)

            for j, xj in enumerate(states):
                C[i, j] = oexpr.coeff(xj)

            for j, uj in enumerate(inputs):
                D[i, j] = oexpr.coeff(uj)

        # -----------------------------------------------------------------
        # Step 6: Convert to numeric StateSpaceModel
        # -----------------------------------------------------------------
        def mat_to_list(M: sympy.Matrix) -> list[list[float]]:
            return [[float(M[r, c]) for c in range(M.cols)] for r in range(M.rows)]

        return StateSpaceModel(
            a_matrix=mat_to_list(A),
            b_matrix=mat_to_list(B),
            c_matrix=mat_to_list(C),
            d_matrix=mat_to_list(D),
            state_variables=[str(x) for x in states],
            input_variables=[str(u) for u in inputs],
            output_variables=[str(o) for o in flat.output_symbols],
            metadata={
                "reducer": "SmallSignalLinearReducer",
                "n_states": n,
                "n_inputs": m,
                "n_outputs": p,
                "n_algebraic_eliminated": len(algebraic_list),
            },
        )
