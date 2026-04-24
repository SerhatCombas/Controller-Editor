from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTextBrowser, QVBoxLayout, QWidget


class EquationPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        title = QLabel("Model Equations")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setStyleSheet(
            "QTextBrowser {"
            "background: #fbfcfe;"
            "border: 1px solid #c8d5e2;"
            "border-radius: 8px;"
            "padding: 10px;"
            "font-family: Menlo, Consolas, monospace;"
            "font-size: 12px;"
            "}"
        )
        layout.addWidget(title)
        layout.addWidget(self.browser, 1)
        self.show_empty_state()

    def show_empty_state(self, message: str = "Select inputs and outputs to inspect the model summary.") -> None:
        self.browser.setHtml(
            f"""
            <div style="margin-bottom:8px; display:inline-block; padding:4px 8px; background:#f4f7fb; border:1px solid #d7e0ea; border-radius:999px;">
            <b>No active I/O selection</b></div>
            <p>{message}</p>
            """
        )

    def update_summary(self, summary: dict[str, str]) -> None:
        html = f"""
        <div style="margin-bottom:8px; display:inline-block; padding:4px 8px; background:#e8f1fb; border:1px solid #c8d5e2; border-radius:999px;">
        <b>{summary['source_badge']}</b></div>
        <h3 style="margin-bottom:6px;">Selected Input / Output</h3>
        <p><b>Input:</b> {summary['input_label']}<br>
        <b>Outputs:</b> {summary['output_label']}</p>
        <h3 style="margin-bottom:6px;">Governing Equations</h3>
        <pre>{summary['equations']}</pre>
        <h3 style="margin-bottom:6px;">Equation Trace</h3>
        <pre>{summary['equation_trace']}</pre>
        <h3 style="margin-bottom:6px;">State Variables</h3>
        <pre>{summary['states']}</pre>
        <h3 style="margin-bottom:6px;">State-Space Form</h3>
        <pre>{summary['state_space']}</pre>
        <h3 style="margin-bottom:6px;">Transfer Function</h3>
        <pre>{summary['transfer_function']}</pre>
        """
        self.browser.setHtml(html)
