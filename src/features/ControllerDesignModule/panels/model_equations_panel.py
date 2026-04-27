"""ModelEquationsPanel — Faz UI-4b.

Read-only equations display panel for the System Controlling module.
Shows governing equations, state-space form, and transfer functions.
Designed to sit inside a CollapsibleSidebar on the right side (default collapsed).

Evolves from the existing EquationPanel with a simpler text-based display.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ModelEquationsPanel(QWidget):
    """Read-only equation display panel.

    Uses QPlainTextEdit for monospace text rendering of equations,
    state-space matrices, and transfer functions.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModelEquationsPanel")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self.editor = QPlainTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setPlaceholderText("Model equations will appear here after analysis.")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.editor)

        # Show default placeholder content
        self.show_empty_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_empty_state(self, message: str = "") -> None:
        """Clear the editor and show placeholder text."""
        self.editor.clear()
        if message:
            self.editor.setPlainText(message)

    def update_equations(self, summary: dict[str, str]) -> None:
        """Update the equations display from analysis results.

        Parameters
        ----------
        summary : dict
            Keys: state_variables, input_variables, output_variables,
                  a_matrix, b_matrix, c_matrix, d_matrix,
                  transfer_functions, stability
        """
        lines = []
        lines.append("═══ System Equations ═══")
        lines.append("")

        if "state_variables" in summary:
            lines.append(f"State variables: {summary['state_variables']}")
        if "input_variables" in summary:
            lines.append(f"Input variables: {summary['input_variables']}")
        if "output_variables" in summary:
            lines.append(f"Output variables: {summary['output_variables']}")
        lines.append("")

        lines.append("═══ State-Space Form ═══")
        lines.append("")
        lines.append("ẋ = A·x + B·u")
        lines.append("y = C·x + D·u")
        lines.append("")

        if "a_matrix" in summary:
            lines.append(f"A = {summary['a_matrix']}")
            lines.append("")
        if "b_matrix" in summary:
            lines.append(f"B = {summary['b_matrix']}")
            lines.append("")
        if "c_matrix" in summary:
            lines.append(f"C = {summary['c_matrix']}")
            lines.append("")
        if "d_matrix" in summary:
            lines.append(f"D = {summary['d_matrix']}")
            lines.append("")

        lines.append("═══ Transfer Functions ═══")
        lines.append("")
        if "transfer_functions" in summary:
            lines.append(summary["transfer_functions"])
            lines.append("")

        if "stability" in summary:
            lines.append(f"Stability: {summary['stability']}")

        self.editor.setPlainText("\n".join(lines))

    def set_text(self, text: str) -> None:
        """Direct text setter for custom content."""
        self.editor.setPlainText(text)
