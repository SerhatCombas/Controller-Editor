"""Template infrastructure for system graph factories.

Faz 5MVP: All hardcoded templates removed. Users build models by
drag-and-drop from the component palette. This module retains only
the TemplateDefinition dataclass which may be used by future
user-saved presets.
"""

from app.core.templates.template_definition import TemplateDefinition

__all__ = [
    "TemplateDefinition",
]
