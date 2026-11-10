"""Funções auxiliares de validação compartilhadas pelos contratos.

Uso interno do pacote ``wqf.contracts``: cada função valida um único valor e levanta
``ContractValidationError`` com o nome do contrato e do campo quando a regra é violada.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from wqf.contracts.errors import ContractValidationError


def require_date(contract: str, field: str, value: object) -> date:
    """Exige uma data de calendário (``date``), recusando ``datetime``."""
    # ``datetime`` é subclasse de ``date``; aceitá-lo misturaria data de pregão com horário.
    if isinstance(value, datetime) or not isinstance(value, date):
        raise ContractValidationError(
            contract, field, f"esperado datetime.date, recebido {type(value).__name__}"
        )
    return value


def require_aware_datetime(contract: str, field: str, value: object) -> datetime:
    """Exige ``datetime`` com fuso horário explícito (timezone-aware)."""
    if not isinstance(value, datetime):
        raise ContractValidationError(
            contract, field, f"esperado datetime.datetime, recebido {type(value).__name__}"
        )
    if value.tzinfo is None or value.utcoffset() is None:
        raise ContractValidationError(
            contract, field, "datetime sem fuso horário; informe tzinfo (ex.: UTC ou BRT)"
        )
    return value


def require_number(
    contract: str,
    field: str,
    value: object,
    *,
    min_value: float | None = None,
    min_inclusive: bool = True,
    max_value: float | None = None,
) -> float:
    """Exige número real finito dentro dos limites informados e o converte para ``float``."""
    # ``bool`` é subclasse de ``int`` em Python; True/False não são quantidades válidas.
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ContractValidationError(
            contract, field, f"esperado número, recebido {type(value).__name__}"
        )
    number = float(value)
    if not math.isfinite(number):
        raise ContractValidationError(contract, field, f"valor não finito: {value!r}")
    if min_value is not None:
        if min_inclusive and number < min_value:
            raise ContractValidationError(contract, field, f"deve ser >= {min_value}: {number}")
        if not min_inclusive and number <= min_value:
            raise ContractValidationError(contract, field, f"deve ser > {min_value}: {number}")
    if max_value is not None and number > max_value:
        raise ContractValidationError(contract, field, f"deve ser <= {max_value}: {number}")
    return number


def require_text(contract: str, field: str, value: object) -> str:
    """Exige texto não vazio, removendo espaços nas pontas."""
    if not isinstance(value, str):
        raise ContractValidationError(
            contract, field, f"esperado str, recebido {type(value).__name__}"
        )
    text = value.strip()
    if not text:
        raise ContractValidationError(contract, field, "texto vazio")
    return text


def normalize_ticker(contract: str, field: str, value: object) -> str:
    """Normaliza o código do ativo para maiúsculas, sem espaços (mesma regra de ``wqf.data``)."""
    ticker = require_text(contract, field, value).upper()
    if any(ch.isspace() for ch in ticker):
        raise ContractValidationError(contract, field, f"ticker com espaço interno: {ticker!r}")
    return ticker


def check_schema_version(contract: str, value: object, supported: str) -> str:
    """Aceita versões com o mesmo número maior (ex.: ``1.x``) da versão suportada."""
    version = require_text(contract, "schema_version", value)
    major = version.split(".", 1)[0]
    if major != supported.split(".", 1)[0]:
        raise ContractValidationError(
            contract,
            "schema_version",
            f"versão {version!r} incompatível; suportada: {supported.split('.', 1)[0]}.x",
        )
    return version


def check_keys(
    contract: str,
    data: Mapping[str, Any],
    required: frozenset[str],
    optional: frozenset[str],
) -> None:
    """Verifica campos obrigatórios ausentes e campos desconhecidos em um registro serializado."""
    if not isinstance(data, Mapping):
        raise ContractValidationError(
            contract, "<registro>", f"esperado mapeamento, recebido {type(data).__name__}"
        )
    missing = sorted(required - data.keys())
    if missing:
        raise ContractValidationError(
            contract, missing[0], f"campos obrigatórios ausentes: {missing}"
        )
    unknown = sorted(data.keys() - required - optional)
    if unknown:
        raise ContractValidationError(contract, unknown[0], f"campos desconhecidos: {unknown}")


def parse_date(contract: str, field: str, value: object) -> date:
    """Converte texto ISO-8601 (``AAAA-MM-DD``) em ``date`` ao desserializar."""
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ContractValidationError(contract, field, f"data ISO inválida: {value!r}") from exc
    return require_date(contract, field, value)


def parse_datetime(contract: str, field: str, value: object) -> datetime:
    """Converte texto ISO-8601 com fuso em ``datetime`` ao desserializar."""
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ContractValidationError(
                contract, field, f"datetime ISO inválido: {value!r}"
            ) from exc
        return require_aware_datetime(contract, field, parsed)
    return require_aware_datetime(contract, field, value)
