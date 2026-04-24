from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLabel, QFrame


class LiveStatusWidget(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.form = QFormLayout(self)
        self.show_empty_state()

    def show_empty_state(self, message: str = "Select outputs to inspect live values.") -> None:
        self._clear_rows()
        self.form.addRow(QLabel("Live outputs"), QLabel(message))

    def update_signal_values(self, values: list[tuple[str, str]]) -> None:
        self._clear_rows()
        if not values:
            self.show_empty_state()
            return
        for label_text, value_text in values:
            self.form.addRow(QLabel(label_text), QLabel(value_text))

    def _clear_rows(self) -> None:
        while self.form.rowCount():
            self.form.removeRow(0)
