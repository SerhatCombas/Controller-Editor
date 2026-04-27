# app/core/symbols/renderer.py — SHIM
from src.shared.symbols.renderer import *  # noqa: F401, F403
from src.shared.symbols.renderer import (  # noqa: F401
    render_svg,
    render_entry_svg,
    load_and_render,
    extract_placeholders,
    _xml_escape,
    _format_param,
)
