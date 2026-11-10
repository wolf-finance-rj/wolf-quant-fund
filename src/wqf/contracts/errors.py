"""Erros levantados pela validação dos contratos compartilhados."""

from __future__ import annotations


class ContractValidationError(ValueError):
    """Registro que viola um contrato compartilhado.

    Attributes:
        contract: Nome do contrato (ex.: ``"MarketData"``).
        field: Campo que causou a falha.
        reason: Descrição legível da violação.
    """

    def __init__(self, contract: str, field: str, reason: str) -> None:
        self.contract = contract
        self.field = field
        self.reason = reason
        super().__init__(f"{contract}.{field}: {reason}")
