"""Módulo de validação e garantia de integridade de dados de mercado."""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl

from wqf.data.exceptions import DataValidationError

REQUIRED_COLUMNS: list[str] = ["date", "ticker", "open", "high", "low", "close", "volume"]


@dataclass
class ValidationReport:
    """Relatório estruturado de validação de dados de mercado."""

    is_valid: bool
    total_rows: int
    errors: list[str] = field(default_factory=list)
    null_counts: dict[str, int] = field(default_factory=dict)
    duplicate_rows_count: int = 0
    invalid_price_rows_count: int = 0
    invalid_volume_rows_count: int = 0
    invalid_high_low_rows_count: int = 0

    def summary(self) -> str:
        """Retorna representação textual detalhada do relatório de validação."""
        status = "APROVADO" if self.is_valid else "REPROVADO"
        lines = [
            f"Relatório de Validação de Mercado: {status}",
            f"Total de registros analisados: {self.total_rows}",
        ]
        if self.errors:
            lines.append(f"Inconsistências encontradas ({len(self.errors)}):")
            for idx, err in enumerate(self.errors, start=1):
                lines.append(f"  {idx}. {err}")
        else:
            lines.append("Nenhuma inconsistência detectada.")
        return "\n".join(lines)


def validate_market_data(
    df: pl.DataFrame,
    strict: bool = True,
) -> tuple[pl.DataFrame, ValidationReport]:
    """Valida um DataFrame de dados de mercado contra o schema e regras financeiras.

    Regras verificadas:
    1. Presença de todas as colunas obrigatórias ('date', 'ticker', 'open', 'high', 'low', 'close', 'volume').
    2. Conversão e normalização de tipos (data, ticker string maiúsculo e floats).
    3. Rejeição de valores nulos / não parseáveis em qualquer coluna obrigatória.
    4. Unicidade temporal por ativo (sem duplicatas da chave 'date' + 'ticker').
    5. Integridade financeira dos preços: open, high, low, close > 0.
    6. Consistência de topo/fundo: high >= low.
    7. Integridade de volume: volume >= 0.

    Args:
        df: DataFrame do Polars contendo os dados brutos.
        strict: Se True, lança DataValidationError caso haja violações.

    Returns:
        Tupla (DataFrame validado e tipado, ValidationReport).

    Raises:
        DataValidationError: Se strict=True e alguma inconsistência for detectada.
    """
    errors: list[str] = []
    total_rows = df.height

    # 1. Checagem de colunas obrigatórias
    normalized_cols = {col.lower().strip(): col for col in df.columns}
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in normalized_cols]

    if missing_cols:
        errors.append(f"Colunas obrigatórias ausentes: {sorted(missing_cols)}")
        report = ValidationReport(
            is_valid=False,
            total_rows=total_rows,
            errors=errors,
        )
        if strict:
            raise DataValidationError(report.summary(), report=report)
        return df, report

    # Renomeia colunas para o padrão canônico minúsculo
    rename_map = {normalized_cols[c]: c for c in REQUIRED_COLUMNS if normalized_cols[c] != c}
    work_df = df.rename(rename_map) if rename_map else df

    # 2. Normalização e conversão de tipos
    # Ticker: string maiúsculo e sem espaços em branco
    ticker_expr = (
        pl.col("ticker").cast(pl.String, strict=False).str.strip_chars().str.to_uppercase()
    )

    # Date: parsing flexível (tenta formato padrão Date ou Datetime, depois converte para Date)
    if work_df.schema["date"] in (pl.Date, pl.Datetime):
        date_expr = pl.col("date").cast(pl.Date)
    else:
        date_expr = (
            pl.col("date").cast(pl.String, strict=False).str.strip_chars().str.to_date(strict=False)
        )

    # Numéricos: float64
    numeric_exprs = [
        pl.col(col).cast(pl.Float64, strict=False).alias(col)
        for col in ["open", "high", "low", "close", "volume"]
    ]

    typed_df = work_df.with_columns(
        [date_expr.alias("date"), ticker_expr.alias("ticker"), *numeric_exprs]
    )

    # 3. Detecção de nulos / dados faltantes
    null_counts: dict[str, int] = {}
    for col in REQUIRED_COLUMNS:
        null_n = typed_df.select(pl.col(col).is_null().sum()).item()
        if null_n > 0:
            null_counts[col] = null_n
            errors.append(f"Coluna '{col}' possui {null_n} valor(es) nulo(s) ou inválido(s).")

    # 4. Detecção de duplicatas (date + ticker)
    # Apenas se data e ticker não forem nulos para evitar mascarar
    duplicate_count = 0
    if "date" not in null_counts and "ticker" not in null_counts:
        dup_filter = typed_df.select(pl.struct(["date", "ticker"]).is_duplicated()).to_series()
        duplicate_rows = typed_df.filter(dup_filter)
        duplicate_count = duplicate_rows.height
        if duplicate_count > 0:
            samples = (
                duplicate_rows.select(["date", "ticker"]).unique().head(3).iter_rows(named=True)
            )
            sample_str = ", ".join(f"({r['ticker']}, {r['date']})" for r in samples)
            errors.append(
                f"Detectadas {duplicate_count} linhas com chave duplicada ('date', 'ticker'). Exemplos: {sample_str}"
            )

    # 5. Integridade financeira: preços estritamente positivos (> 0)
    invalid_price_count = 0
    price_cols = ["open", "high", "low", "close"]
    available_price_cols = [c for c in price_cols if c not in null_counts]
    if available_price_cols:
        price_cond = pl.any_horizontal([pl.col(c) <= 0 for c in available_price_cols])
        invalid_prices = typed_df.filter(price_cond)
        invalid_price_count = invalid_prices.height
        if invalid_price_count > 0:
            errors.append(
                f"Detectadas {invalid_price_count} linhas com preços não positivos (<= 0)."
            )

    # 6. Integridade de topo/fundo: high >= low
    invalid_hl_count = 0
    if "high" not in null_counts and "low" not in null_counts:
        invalid_hl = typed_df.filter(pl.col("high") < pl.col("low"))
        invalid_hl_count = invalid_hl.height
        if invalid_hl_count > 0:
            errors.append(
                f"Detectadas {invalid_hl_count} linhas onde 'high' é estritamente menor que 'low'."
            )

    # 7. Integridade de volume: volume >= 0
    invalid_vol_count = 0
    if "volume" not in null_counts:
        invalid_vol = typed_df.filter(pl.col("volume") < 0)
        invalid_vol_count = invalid_vol.height
        if invalid_vol_count > 0:
            errors.append(
                f"Detectadas {invalid_vol_count} linhas com volume financeiro negativo (< 0)."
            )

    is_valid = len(errors) == 0

    report = ValidationReport(
        is_valid=is_valid,
        total_rows=total_rows,
        errors=errors,
        null_counts=null_counts,
        duplicate_rows_count=duplicate_count,
        invalid_price_rows_count=invalid_price_count,
        invalid_volume_rows_count=invalid_vol_count,
        invalid_high_low_rows_count=invalid_hl_count,
    )

    if not is_valid and strict:
        raise DataValidationError(report.summary(), report=report)

    # Se válido, organiza e ordena temporalmente por data e ticker
    final_df = typed_df.select(REQUIRED_COLUMNS).sort(["date", "ticker"])

    return final_df, report
