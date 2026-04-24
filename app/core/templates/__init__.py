"""Predefined runnable model templates for Phase 1."""

from app.core.templates.quarter_car import build_quarter_car_template
from app.core.templates.rc_circuit import build_rc_circuit_template
from app.core.templates.rlc_circuit import build_rlc_circuit_template
from app.core.templates.single_mass import build_single_mass_template
from app.core.templates.template_definition import TemplateDefinition
from app.core.templates.two_mass import build_two_mass_template

__all__ = [
    "TemplateDefinition",
    "build_quarter_car_template",
    "build_rc_circuit_template",
    "build_rlc_circuit_template",
    "build_single_mass_template",
    "build_two_mass_template",
]
