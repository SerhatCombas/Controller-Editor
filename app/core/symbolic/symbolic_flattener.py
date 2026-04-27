"""SymbolicFlattener — collect all symbolic equations from a SystemGraph (T2.1).

Walks the graph, gathers each component's symbolic_equations(),
then adds node-level connection equations (across equality + through balance).

Output: a FlatSystem containing all equations + classified variable lists.

Scope limitation (per architecture feedback):
  This flattener handles simple LTI circuits and mechanical systems.
  It does NOT handle: index reduction, tearing, matching, overconstrained
  ideal source loops, or algebraic loops.  Those are future work.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import sympy

from app.core.base.equation import SymbolicEquation
from app.core.base.domain import get_domain_spec


@dataclass
class FlatSystem:
    """Result of flattening a SystemGraph into symbolic equations.

    Attributes:
        equations: All symbolic equations (component + node).
        state_symbols: Symbols that appear inside der() — these become states.
        algebraic_symbols: All other unknown symbols (not state, not parameter, not input).
        input_symbols: Symbols tagged as system inputs.
        output_symbols: Symbols tagged as system outputs.
        parameter_map: symbol → numeric value for all component parameters.
    """
    equations: list[SymbolicEquation] = field(default_factory=list)
    state_symbols: list[sympy.Symbol] = field(default_factory=list)
    algebraic_symbols: list[sympy.Symbol] = field(default_factory=list)
    input_symbols: list[sympy.Symbol] = field(default_factory=list)
    output_symbols: list[sympy.Symbol] = field(default_factory=list)
    output_expressions: dict[sympy.Symbol, sympy.Expr] = field(default_factory=dict)
    parameter_map: dict[sympy.Symbol, float] = field(default_factory=dict)


# We need to recognize der() calls — import the same function used by components
_der_func = sympy.Function("der")


def _find_der_args(expr: sympy.Expr) -> set[sympy.Symbol]:
    """Find all symbols x such that der(x) appears in expr."""
    results = set()
    for atom in expr.atoms(sympy.Basic):
        if hasattr(atom, 'func') and atom.func == _der_func and len(atom.args) == 1:
            arg = atom.args[0]
            if isinstance(arg, sympy.Symbol):
                results.add(arg)
    # Also walk the expression tree more carefully
    for sub in sympy.preorder_traversal(expr):
        if hasattr(sub, 'func') and sub.func == _der_func and len(sub.args) == 1:
            arg = sub.args[0]
            if isinstance(arg, sympy.Symbol):
                results.add(arg)
    return results


def flatten(graph: object, input_symbol_names: list[str] | None = None,
            output_exprs: dict[str, sympy.Expr] | None = None) -> FlatSystem:
    """Flatten a SystemGraph into a FlatSystem.

    Args:
        graph: SystemGraph instance.
        input_symbol_names: Names of symbols to treat as inputs.
                           Typically the prescribed source values.
        output_exprs: Mapping of output_name → sympy expression for outputs.
    """
    from app.core.graph.system_graph import SystemGraph
    assert isinstance(graph, SystemGraph)

    all_equations: list[SymbolicEquation] = []
    parameter_map: dict[sympy.Symbol, float] = {}

    # -----------------------------------------------------------------
    # 1. Collect component equations
    # -----------------------------------------------------------------
    for comp in graph.components.values():
        eqs = comp.symbolic_equations()
        all_equations.extend(eqs)

        # Map parameter symbols to numeric values
        for pname, pval in comp.parameters.items():
            psym = comp._sym(pname)
            parameter_map[psym] = pval

    # -----------------------------------------------------------------
    # 2. Generate node connection equations (across equality + through balance)
    # -----------------------------------------------------------------
    for node in graph.nodes.values():
        if len(node.port_ids) < 2:
            continue

        # Find actual Port objects for this node
        ports = []
        for pid in node.port_ids:
            ports.append(graph.get_port(pid))

        # Determine domain spec for symbol naming
        domain_name = node.domain.name
        # Try to find matching DomainSpec
        spec = None
        try:
            from app.core.base.domain import DOMAIN_SPECS
            # Legacy domain names may differ from DomainSpec keys
            for key, ds in DOMAIN_SPECS.items():
                legacy = ds.to_domain()
                if legacy.name == domain_name or ds.name == domain_name:
                    spec = ds
                    break
        except Exception:
            pass

        across_var_name = spec.across_var if spec else "v"
        through_var_name = spec.through_var if spec else "i"

        # Node across variable
        node_across = sympy.Symbol(f"node_{node.id}_{across_var_name}", real=True)

        # Across equality: each port's across var = node across var
        for port in ports:
            # Find the port's across symbol from its component
            comp = graph.components[port.component_id]
            # The symbol name follows the pattern: {comp_id}__{port_name}_{across_var}
            port_across = sympy.Symbol(
                f"{comp.id}__{port.name}_{across_var_name}", real=True
            )
            all_equations.append(SymbolicEquation(
                lhs=port_across,
                rhs=node_across,
                provenance=f"node_{node.id}_across_eq",
            ))

        # Through balance (KCL/KFL): sum of all through variables = 0
        # Sign convention: positive direction depends on direction_hint
        through_terms = []
        for port in ports:
            comp = graph.components[port.component_id]
            port_through = sympy.Symbol(
                f"{comp.id}__{port.name}_{through_var_name}", real=True
            )
            through_terms.append(port_through)

        if through_terms:
            all_equations.append(SymbolicEquation(
                lhs=sum(through_terms),
                rhs=sympy.Integer(0),
                provenance=f"node_{node.id}_through_balance",
            ))

    # -----------------------------------------------------------------
    # 3. Classify variables
    # -----------------------------------------------------------------
    # Find all free symbols across all equations
    all_symbols: set[sympy.Symbol] = set()
    for eq in all_equations:
        all_symbols |= eq.free_symbols()

    # State symbols: anything inside der(...)
    state_set: set[sympy.Symbol] = set()
    for eq in all_equations:
        state_set |= _find_der_args(eq.lhs)
        state_set |= _find_der_args(eq.rhs)

    # Input symbols
    input_set: set[sympy.Symbol] = set()
    if input_symbol_names:
        for name in input_symbol_names:
            for s in all_symbols:
                if s.name == name:
                    input_set.add(s)

    # Remove input symbols from parameter_map — they must stay symbolic
    # (e.g. VoltageSource has parameters={"value": 1.0} but "vs1__value"
    # is the system input, not a fixed parameter)
    for isym in input_set:
        parameter_map.pop(isym, None)

    # Parameter symbols
    param_set = set(parameter_map.keys())

    # Algebraic: everything that's not state, input, or parameter
    algebraic_set = all_symbols - state_set - input_set - param_set
    # Also remove node variables that are just intermediate
    # (they'll be eliminated during reduction)

    # Output expressions
    output_sym_map: dict[sympy.Symbol, sympy.Expr] = {}
    output_syms: list[sympy.Symbol] = []
    if output_exprs:
        for oname, oexpr in output_exprs.items():
            osym = sympy.Symbol(oname, real=True)
            output_syms.append(osym)
            output_sym_map[osym] = oexpr

    return FlatSystem(
        equations=all_equations,
        state_symbols=sorted(state_set, key=str),
        algebraic_symbols=sorted(algebraic_set, key=str),
        input_symbols=sorted(input_set, key=str),
        output_symbols=output_syms,
        output_expressions=output_sym_map,
        parameter_map=parameter_map,
    )
