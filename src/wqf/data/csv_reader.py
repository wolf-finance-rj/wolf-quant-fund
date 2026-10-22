"""Módulo de ingestão, parsing e persistência de dados de mercado a partir de arquivos CSV."""

from __future__ import annotations

import io
from pathlib import Path

import polars as pl

from wqf.data.validator import ValidationReport, validate_market_data


def ingest_market_csv(
    source: str | Path | io.StringIO | io.BytesIO,
    strict: bool = True,
    output_parquet: str | Path | None = None,
) -> tuple[pl.DataFrame, ValidationReport]:
    """Lê um arquivo CSV de mercado, valida os dados e opcionalmente exporta para Parquet.

    Args:
        source: Caminho para o arquivo CSV ou buffer de texto/bytes.
        strict: Se True, lança DataValidationError caso haja violações no schema ou regras.
        output_parquet: Caminho opcional onde o arquivo Parquet validado será gravado.

    Returns:
        Tupla (DataFrame validado, ValidationReport).

    Raises:
        FileNotFoundError: Se o caminho do CSV não existir.
        DataValidationError: Se strict=True e alguma validação falhar.
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo CSV não encontrado: {path}")

    # Lê o CSV como Polars DataFrame
    raw_df = pl.read_csv(source, infer_schema_length=10000)

    # Executa validação estrita ou tolerante
    validated_df, report = validate_market_data(raw_df, strict=strict)

    # Se válido e foi fornecido caminho de saída Parquet, grava no disco
    if report.is_valid and output_parquet is not None:
        out_path = Path(output_parquet)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        validated_df.write_parquet(out_path)

    return validated_df, report


def read_market_csv(
    source: str | Path | io.StringIO | io.BytesIO,
    strict: bool = True,
    output_parquet: str | Path | None = None,
) -> pl.DataFrame:
    """Atalho para ler e validar CSV de mercado, retornando diretamente o DataFrame validado.

    Args:
        source: Caminho para o arquivo CSV ou buffer de texto/bytes.
        strict: Se True (padrão), lança DataValidationError caso haja violações.
        output_parquet: Caminho opcional onde o arquivo Parquet validado será gravado.

    Returns:
        DataFrame tipado, ordenado e com schema garantido.
    """
    df, _ = ingest_market_csv(source, strict=strict, output_parquet=output_parquet)
    return df
