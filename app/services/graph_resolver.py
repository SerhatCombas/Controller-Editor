"""Shared helper: resolve which SystemGraph a backend should use.

When flags.canvas_compiled_graph is True and a provider is available,
calls the provider and returns the compiled canvas graph.
Falls back to build_quarter_car_template() on any failure.

Returns (SystemGraph, graph_id) so callers that need the template id
(e.g. SymbolicStateSpaceBackend's parity harness) can use it.
"""
from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import TYPE_CHECKING

from app.core.state.feature_flags import FeatureFlags
from app.core.templates import build_quarter_car_template

if TYPE_CHECKING:
    from app.core.graph.system_graph import SystemGraph


def resolve_graph(
    flags: FeatureFlags,
    canvas_graph_provider: Callable[[], SystemGraph | None] | None,
) -> tuple[SystemGraph, str]:
    """Return (SystemGraph, graph_id) for the given flags and provider.

    - flag OFF or no provider → template path, graph_id = template.id
    - flag ON, provider returns graph → (canvas_graph, "canvas_compiled")
    - flag ON, provider raises or returns None → warning + template fallback
    """
    if flags.canvas_compiled_graph and canvas_graph_provider is not None:
        try:
            graph = canvas_graph_provider()
            if graph is not None:
                return graph, "canvas_compiled"
        except Exception as exc:
            warnings.warn(
                f"canvas_compiled_graph: compilation failed ({exc!r}), "
                "falling back to build_quarter_car_template()",
                RuntimeWarning,
                stacklevel=3,
            )
    template = build_quarter_car_template()
    return template.graph, template.id
