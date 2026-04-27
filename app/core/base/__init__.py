"""Shared modeling primitives for the future port-based simulation engine."""

from app.core.base.component import BaseComponent
from app.core.base.connection import Connection
from app.core.base.domain import (
    Domain,
    DomainSpec,
    DOMAIN_SPECS,
    ELECTRICAL_DOMAIN,
    MECHANICAL_TRANSLATIONAL_DOMAIN,
    get_domain_spec,
)
from app.core.base.component_helpers import (
    PortSetup,
    add_one_port,
    add_one_port_pair,
    add_rigid_pair,
)
from app.core.base.equation import SymbolicEquation, der
from app.core.base.node import Node
from app.core.base.port import Port
from app.core.base.variable import Variable

__all__ = [
    "BaseComponent",
    "Connection",
    "Domain",
    "DomainSpec",
    "DOMAIN_SPECS",
    "ELECTRICAL_DOMAIN",
    "MECHANICAL_TRANSLATIONAL_DOMAIN",
    "Node",
    "Port",
    "PortSetup",
    "SymbolicEquation",
    "Variable",
    "add_one_port",
    "add_one_port_pair",
    "add_rigid_pair",
    "der",
    "get_domain_spec",
]
