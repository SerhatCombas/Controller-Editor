"""Shared modeling primitives for the future port-based simulation engine."""

from app.core.base.component import BaseComponent
from app.core.base.connection import Connection
from app.core.base.domain import Domain, ELECTRICAL_DOMAIN, MECHANICAL_TRANSLATIONAL_DOMAIN
from app.core.base.node import Node
from app.core.base.port import Port
from app.core.base.variable import Variable

__all__ = [
    "BaseComponent",
    "Connection",
    "Domain",
    "ELECTRICAL_DOMAIN",
    "MECHANICAL_TRANSLATIONAL_DOMAIN",
    "Node",
    "Port",
    "Variable",
]
