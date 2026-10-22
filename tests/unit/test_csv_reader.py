"""Testes unitários para o módulo de ingestão e validação de dados de mercado (CSV/Parquet)."""

from io import StringIO
from pathlib import Path

import polars as pl
import pytest

from wqf.data import (
    DataValidationError,
    ingest_market_csv,
    read_market_csv,
)

FIXTURES_DIR = Path(__file__).parents[1] / "fixtures"


def test_read_valid_csv(tmp_path: Path) -> None:
    """Verifica se o CSV válido é lido com tipos corretos e ordenado temporalmente."""
    csv_file = FIXTURES_DIR / "market_data_valid.csv"
    df = read_market_csv(csv_file)

    assert isinstance(df, pl.DataFrame)
    assert df.height == 15
    assert df.columns == ["date", "ticker", "open", "high", "low", "close", "volume"]

    # Validação dos tipos de dados
    assert df.schema["date"] == pl.Date
    assert df.schema["ticker"] == pl.String
    assert df.schema["open"] == pl.Float64
    assert df.schema["high"] == pl.Float64
    assert df.schema["low"] == pl.Float64
    assert df.schema["close"] == pl.Float64
    assert df.schema["volume"] == pl.Float64

    # Verifica se os dados estão ordenados por date e ticker
    first_row = df.row(0, named=True)
    assert first_row["ticker"] == "BBDC4"  # Ordem alfabética em 2026-01-02


def test_export_to_parquet(tmp_path: Path) -> None:
    """Verifica se a persistência em arquivo Parquet gera um dataset com schema consistente."""
    csv_file = FIXTURES_DIR / "market_data_valid.csv"
    parquet_out = tmp_path / "subfolder" / "market_data.parquet"

    df_csv = read_market_csv(csv_file, output_parquet=parquet_out)

    assert parquet_out.exists()

    df_parquet = pl.read_parquet(parquet_out)
    assert df_parquet.equals(df_csv)
    assert df_parquet.schema == df_csv.schema


def test_reject_missing_columns() -> None:
    """Verifica se CSV com colunas obrigatórias ausentes é rejeitado com erro explícito."""
    csv_file = FIXTURES_DIR / "market_data_missing_columns.csv"

    with pytest.raises(DataValidationError) as exc_info:
        read_market_csv(csv_file)

    assert "Colunas obrigatórias ausentes" in str(exc_info.value)
    assert "volume" in str(exc_info.value)


def test_reject_missing_values_strict() -> None:
    """Verifica se valores nulos/faltantes disparam exceção explicativa no modo estrito."""
    csv_file = FIXTURES_DIR / "market_data_missing_values.csv"

    with pytest.raises(DataValidationError) as exc_info:
        read_market_csv(csv_file, strict=True)

    err_msg = str(exc_info.value)
    assert "Coluna 'close' possui" in err_msg or "Coluna 'ticker' possui" in err_msg


def test_missing_values_non_strict() -> None:
    """Verifica se no modo tolerante os erros são relatados sem lançar exceção."""
    csv_file = FIXTURES_DIR / "market_data_missing_values.csv"

    _df, report = ingest_market_csv(csv_file, strict=False)

    assert not report.is_valid
    assert len(report.errors) > 0
    assert "close" in report.null_counts or "ticker" in report.null_counts


def test_reject_duplicate_entries() -> None:
    """Verifica se duplicatas de ativo na mesma data são detectadas e rejeitadas."""
    csv_file = FIXTURES_DIR / "market_data_duplicates.csv"

    with pytest.raises(DataValidationError) as exc_info:
        read_market_csv(csv_file, strict=True)

    err_msg = str(exc_info.value)
    assert "chave duplicada" in err_msg
    assert "PETR4" in err_msg


def test_duplicates_non_strict() -> None:
    """Verifica a contagem e relato de duplicatas em modo não estrito."""
    csv_file = FIXTURES_DIR / "market_data_duplicates.csv"

    _, report = ingest_market_csv(csv_file, strict=False)

    assert not report.is_valid
    assert report.duplicate_rows_count >= 2


def test_reject_invalid_numerical_values() -> None:
    """Verifica rejeição de preços <= 0, high < low e volumes negativos."""
    csv_file = FIXTURES_DIR / "market_data_invalid_values.csv"

    with pytest.raises(DataValidationError) as exc_info:
        read_market_csv(csv_file, strict=True)

    err_msg = str(exc_info.value)
    assert "preços não positivos" in err_msg
    assert "estritamente menor que 'low'" in err_msg
    assert "volume financeiro negativo" in err_msg


def test_file_not_found() -> None:
    """Verifica se caminho inexistente levanta FileNotFoundError com clareza."""
    with pytest.raises(FileNotFoundError):
        read_market_csv("caminho/completamente/inexistente/dados.csv")


def test_ticker_normalization() -> None:
    """Verifica se tickers com espaços em branco e letras minúsculas são normalizados."""
    raw_csv = StringIO(
        "date,ticker,open,high,low,close,volume\n2026-01-02,  petr4  ,30.0,31.0,29.5,30.5,1000.0\n"
    )
    df = read_market_csv(raw_csv)
    assert df["ticker"][0] == "PETR4"


def test_column_name_case_and_whitespace_insensitivity() -> None:
    """Verifica se cabeçalhos com espaços ou maiúsculas são normalizados para minúsculo."""
    raw_csv = StringIO(
        "DATE , TICKER, OPEN , HIGH , LOW , CLOSE , VOLUME\n2026-01-02,VALE3,60.0,61.0,59.0,60.5,5000.0\n"
    )
    df = read_market_csv(raw_csv)
    assert df.columns == ["date", "ticker", "open", "high", "low", "close", "volume"]
    assert df["ticker"][0] == "VALE3"
