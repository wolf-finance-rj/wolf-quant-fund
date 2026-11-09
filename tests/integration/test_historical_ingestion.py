"""Testes de integração para o pipeline de ingestão histórica, camadas Parquet e manifesto (#8)."""

import math
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from wqf.data import (
    BenchmarkBar,
    CdiRatePoint,
    EquityBar,
    HistoricalIngestionError,
    InMemoryBenchmarkProvider,
    InMemoryCdiProvider,
    InMemoryEquitiesProvider,
    load_curated_dataset,
    run_historical_ingestion_pipeline,
)


def _sample_providers() -> tuple[
    InMemoryEquitiesProvider,
    InMemoryBenchmarkProvider,
    InMemoryCdiProvider,
]:
    equities = InMemoryEquitiesProvider(
        [
            EquityBar(date(2026, 1, 2), "PETR4", 36.0, 37.0, 35.5, 36.5, 45_000_000.0, 0.0),
            EquityBar(date(2026, 1, 2), "VALE3", 68.0, 69.0, 67.5, 68.5, 30_000_000.0, 0.0),
            EquityBar(date(2026, 1, 5), "PETR4", 36.6, 37.5, 36.2, 37.23, 48_000_000.0, 0.73),
            EquityBar(date(2026, 1, 5), "VALE3", 68.5, 69.5, 68.0, 69.0, 31_000_000.0, 0.0),
        ]
    )
    benchmark = InMemoryBenchmarkProvider(
        [
            BenchmarkBar(date(2026, 1, 2), "IBOV", 128_000.0),
            BenchmarkBar(date(2026, 1, 5), "IBOV", 129_280.0),
        ]
    )
    cdi = InMemoryCdiProvider(
        [
            CdiRatePoint(date(2026, 1, 2), 0.0004),
            CdiRatePoint(date(2026, 1, 5), 0.0004),
        ]
    )
    return equities, benchmark, cdi


def test_pipeline_runs_offline_and_loads_common_schema(tmp_path: Path) -> None:
    """Verifica ingestão sem rede, criação de camadas raw/curated e leitura validada."""
    eq_prov, bm_prov, cdi_prov = _sample_providers()
    fixed_ts = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)

    manifest = run_historical_ingestion_pipeline(
        equities_provider=eq_prov,
        benchmark_provider=bm_prov,
        cdi_provider=cdi_prov,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10),
        output_dir=tmp_path,
        collected_at=fixed_ts,
    )

    assert len(manifest.artifacts) == 6
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "raw" / "equities.parquet").exists()
    assert (tmp_path / "curated" / "equities.parquet").exists()

    df_eq = load_curated_dataset(tmp_path, "equities")
    df_bm = load_curated_dataset(tmp_path, "benchmark")
    df_cdi = load_curated_dataset(tmp_path, "cdi")

    assert df_eq.height == 4
    assert "cumulative_dividend_factor" in df_eq.columns
    assert "causal_total_return_index" in df_eq.columns

    assert df_bm.height == 2
    assert math.isclose(df_bm.row(1, named=True)["daily_return"], 0.01, rel_tol=1e-9)

    assert df_cdi.height == 2
    assert math.isclose(
        df_cdi.row(1, named=True)["cdi_accumulated_index"],
        1.0004 * 1.0004,
        rel_tol=1e-9,
    )


def test_causal_dividend_adjustment_has_no_look_ahead(tmp_path: Path) -> None:
    """Garante que proventos futuros não alteram fatores ou preços ajustados no passado."""
    eq_short, bm_prov, cdi_prov = _sample_providers()

    # Adiciona um dividendo extraordinário no futuro (2026-01-06)
    eq_future_div = InMemoryEquitiesProvider(
        [
            EquityBar(date(2026, 1, 2), "PETR4", 36.0, 37.0, 35.5, 36.5, 45_000_000.0, 0.0),
            EquityBar(date(2026, 1, 2), "VALE3", 68.0, 69.0, 67.5, 68.5, 30_000_000.0, 0.0),
            EquityBar(date(2026, 1, 5), "PETR4", 36.6, 37.5, 36.2, 37.23, 48_000_000.0, 0.73),
            EquityBar(date(2026, 1, 5), "VALE3", 68.5, 69.5, 68.0, 69.0, 31_000_000.0, 0.0),
            EquityBar(date(2026, 1, 6), "PETR4", 30.0, 31.0, 29.5, 30.5, 60_000_000.0, 10.0),
        ]
    )

    dir_a = tmp_path / "run_short"
    dir_b = tmp_path / "run_with_future"

    run_historical_ingestion_pipeline(
        eq_short, bm_prov, cdi_prov, date(2026, 1, 1), date(2026, 1, 10), dir_a
    )
    run_historical_ingestion_pipeline(
        eq_future_div, bm_prov, cdi_prov, date(2026, 1, 1), date(2026, 1, 10), dir_b
    )

    df_a = load_curated_dataset(dir_a, "equities")
    df_b = load_curated_dataset(dir_b, "equities").filter(pl.col("date") <= date(2026, 1, 5))

    assert df_a.equals(df_b)


def test_pipeline_idempotency_and_reproducible_hashes(tmp_path: Path) -> None:
    """Verifica que duas execuções sobre os mesmos dados geram hashes SHA-256 idênticos."""
    eq_prov, bm_prov, cdi_prov = _sample_providers()
    fixed_ts = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)

    m1 = run_historical_ingestion_pipeline(
        eq_prov,
        bm_prov,
        cdi_prov,
        date(2026, 1, 1),
        date(2026, 1, 10),
        tmp_path / "run1",
        collected_at=fixed_ts,
    )
    m2 = run_historical_ingestion_pipeline(
        eq_prov,
        bm_prov,
        cdi_prov,
        date(2026, 1, 1),
        date(2026, 1, 10),
        tmp_path / "run2",
        collected_at=fixed_ts,
    )

    assert m1.to_dict() == m2.to_dict()


def test_quality_validation_rejects_duplicates_and_invalid_values(tmp_path: Path) -> None:
    """Garante que duplicatas ou preços negativos são barrados com HistoricalIngestionError."""
    _, bm_prov, cdi_prov = _sample_providers()

    dup_equities = InMemoryEquitiesProvider(
        [
            EquityBar(date(2026, 1, 2), "PETR4", 36.0, 37.0, 35.5, 36.5, 1000.0, 0.0),
            EquityBar(date(2026, 1, 2), "PETR4", 36.1, 37.0, 35.5, 36.6, 1000.0, 0.0),
        ]
    )
    with pytest.raises(HistoricalIngestionError, match="Duplicatas"):
        run_historical_ingestion_pipeline(
            dup_equities, bm_prov, cdi_prov, date(2026, 1, 1), date(2026, 1, 10), tmp_path / "dup"
        )

    neg_cdi = InMemoryCdiProvider([CdiRatePoint(date(2026, 1, 2), -0.001)])
    eq_ok, _, _ = _sample_providers()
    with pytest.raises(HistoricalIngestionError, match="negativa"):
        run_historical_ingestion_pipeline(
            eq_ok, bm_prov, neg_cdi, date(2026, 1, 1), date(2026, 1, 10), tmp_path / "neg_cdi"
        )


def test_hash_verification_detects_tampered_file(tmp_path: Path) -> None:
    """Verifica que adulteração no Parquet após geração é detectada pelo checksum do manifesto."""
    eq_prov, bm_prov, cdi_prov = _sample_providers()
    run_historical_ingestion_pipeline(
        eq_prov, bm_prov, cdi_prov, date(2026, 1, 1), date(2026, 1, 10), tmp_path
    )

    # Corrompe/sobrescreve o arquivo curated de benchmark
    tampered_df = pl.DataFrame(
        {"date": [date(2026, 1, 2)], "symbol": ["IBOV"], "close": [999_999.0]}
    )
    tampered_df.write_parquet(tmp_path / "curated" / "benchmark.parquet")

    with pytest.raises(HistoricalIngestionError, match="Falha de integridade"):
        load_curated_dataset(tmp_path, "benchmark", verify_hash=True)
