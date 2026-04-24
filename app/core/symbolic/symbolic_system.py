from __future__ import annotations

from dataclasses import dataclass, field

from app.core.symbolic.structured_equation import EquationRecord


@dataclass(slots=True)
class SymbolicSystem:
    all_equations: list[str] = field(default_factory=list)
    dae_equations: list[str] = field(default_factory=list)
    differential_equations: list[str] = field(default_factory=list)
    algebraic_constraints: list[str] = field(default_factory=list)
    equation_records: list[EquationRecord] = field(default_factory=list)
    dae_equation_records: list[EquationRecord] = field(default_factory=list)
    differential_records: list[EquationRecord] = field(default_factory=list)
    algebraic_records: list[EquationRecord] = field(default_factory=list)
    state_variables: list[str] = field(default_factory=list)
    input_variables: list[str] = field(default_factory=list)
    output_definitions: dict[str, str] = field(default_factory=dict)
    parameters: dict[str, float] = field(default_factory=dict)
    variable_registry: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ReducedODESystem:
    state_variables: list[str] = field(default_factory=list)
    input_variables: list[str] = field(default_factory=list)
    output_definitions: dict[str, str] = field(default_factory=dict)
    mass_matrix: list[list[float]] = field(default_factory=list)
    damping_matrix: list[list[float]] = field(default_factory=list)
    stiffness_matrix: list[list[float]] = field(default_factory=list)
    input_matrix: list[list[float]] = field(default_factory=list)
    first_order_a: list[list[float]] = field(default_factory=list)
    first_order_b: list[list[float]] = field(default_factory=list)
    node_order: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class StateSpaceModel:
    a_matrix: list[list[float]] = field(default_factory=list)
    b_matrix: list[list[float]] = field(default_factory=list)
    c_matrix: list[list[float]] = field(default_factory=list)
    d_matrix: list[list[float]] = field(default_factory=list)
    state_variables: list[str] = field(default_factory=list)
    input_variables: list[str] = field(default_factory=list)
    output_variables: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
