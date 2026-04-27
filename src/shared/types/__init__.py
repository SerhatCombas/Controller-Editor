"""src.shared.types — Core data types for the modeling engine.

Re-exports all base types so consumers can write:
    from src.shared.types import BaseComponent, Port, Domain, ...
"""
from src.shared.types.component import BaseComponent
from src.shared.types.connection import Connection
from src.shared.types.contribution import MatrixContribution
from src.shared.types.domain import (
    ELECTRICAL_DOMAIN,
    MECHANICAL_TRANSLATIONAL_DOMAIN,
    Domain,
    DomainSpec,
    get_domain_spec,
)
from src.shared.types.equation import SymbolicEquation, der
from src.shared.types.linearity import LinearityProfile
from src.shared.types.node import Node
from src.shared.types.port import Port
from src.shared.types.source_descriptor import SourceDescriptor
from src.shared.types.state_contribution import StateContribution
from src.shared.types.variable import Variable

__all__ = [
    "BaseComponent",
    "Connection",
    "Domain",
    "DomainSpec",
    "ELECTRICAL_DOMAIN",
    "LinearityProfile",
    "MatrixContribution",
    "MECHANICAL_TRANSLATIONAL_DOMAIN",
    "Node",
    "Port",
    "SourceDescriptor",
    "StateContribution",
    "SymbolicEquation",
    "Variable",
    "der",
    "get_domain_spec",
]
