"""Exceções para o módulo de ingestão e validação de dados de mercado."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wqf.data.validator import ValidationReport


class DataValidationError(ValueError):
    """Exceção lançada quando a validação de dados de mercado encontra inconsistências."""

    def __init__(self, message: str, report: ValidationReport | None = None) -> None:
        super().__init__(message)
        self.report = report
