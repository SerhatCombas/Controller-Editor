"""Shared helper: resolve which SystemGraph a backend should use.

When flags.canvas_compiled_graph is True and a provider is available,
calls the provider and returns the compiled canvas graph.

Faz 5MVP: No template fallback — if the canvas graph fails to compile,
raise instead of silently falling back to a hardcoded template.

Returns (SystemGraph, graph_id) so callers that need the template id
(e.g. SymbolicStateSpaceBackend) can use it.
"""
from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import TYPE_CHECKING

from src.shared.utils.feature_flags import FeatureFlags

if TYPE_CHECKING:
    from src.shared.graph.system_graph import SystemGraph


def resolve_graph(
    flags: FeatureFlags,
    canvas_graph_provider: Callable[[], SystemGraph | None] | None,
) -> tuple[SystemGraph, str]:
    """Return (SystemGraph, graph_id) for the given flags and provider.

    - flag ON, provider returns graph → (canvas_graph, "canvas_compiled")
    - flag ON, provider raises or returns None → RuntimeError
    - flag OFF or no provider → RuntimeError (no template fallback)
    """
    if flags.canvas_compiled_graph and canvas_graph_provider is not None:
        try:
            graph = canvas_graph_provider()
            if graph is not None:
                return graph, "canvas_compiled"
        except Exception as exc:
            raise RuntimeError(
                f"canvas_compiled_graph: compilation failed ({exc!r}). "
                "No template fallback available — build a model on the canvas first."
            ) from exc

    raise RuntimeError(
        "No graph available. Draw a model on the canvas and compile it, "
        "or enable canvas_compiled_graph in feature flags."
    )
