"""Pipeline de ingestão histórica em camadas (raw/curated), ajuste causal de proventos e manifesto."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import polars as pl

from wqf.data.providers.base import (
    BENCHMARK_RAW_COLUMNS,
    CDI_RAW_COLUMNS,
    EQUITIES_RAW_COLUMNS,
    BenchmarkProvider,
    CdiProvider,
    EquitiesProvider,
)

SCHEMA_VERSION = "1.0.0"
DatasetKind = Literal["equities", "benchmark", "cdi"]


class HistoricalIngestionError(ValueError):
    """Exceção lançada quando a validação do pipeline histórico detecta inconsistências."""


@dataclass(frozen=True)
class ArtifactMetadata:
    """Metadados e hash criptográfico de um arquivo Parquet gerado pelo pipeline."""

    dataset: str
    layer: Literal["raw", "curated"]
    relative_path: str
    row_count: int
    sha256: str


@dataclass(frozen=True)
class IngestionManifest:
    """Manifesto reproduzível de um snapshot do pipeline de dados históricos."""

    schema_version: str
    start_date: str
    end_date: str
    collected_at: str
    sources: dict[str, str]
    artifacts: list[ArtifactMetadata]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def compute_file_sha256(path: Path) -> str:
    """Calcula o hash SHA-256 hexadecimal de um arquivo em disco."""
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_and_curate_equities(raw_df: pl.DataFrame) -> pl.DataFrame:
    """Valida ações brutas e calcula fator acumulado de proventos sem look-ahead bias.

    Regras:
    - Colunas obrigatórias: date, ticker, open, high, low, close, volume, dividend.
    - Sem valores nulos, preços <= 0, high < low, volume < 0 ou dividend < 0.
    - Sem duplicatas de (date, ticker).
    - Ordenação estrita por (ticker, date).
    - Ajuste causal de proventos: o fator `cumulative_dividend_factor` começa em 1.0
      e só incorpora o provento na própria data ex (`t`), multiplicando por
      `1 + dividend_t / close_{t-1}`. Dessa forma, nenhuma informação futura vaza para datas passadas.
    """
    missing = [c for c in EQUITIES_RAW_COLUMNS if c not in raw_df.columns]
    if missing:
        raise HistoricalIngestionError(f"Colunas ausentes em ações: {missing}")
    if raw_df.is_empty():
        raise HistoricalIngestionError("Dataset de ações está vazio para o período solicitado.")

    df = raw_df.select(
        [
            pl.col("date").cast(pl.Date),
            pl.col("ticker").cast(pl.String).str.strip_chars().str.to_uppercase(),
            pl.col("open").cast(pl.Float64),
            pl.col("high").cast(pl.Float64),
            pl.col("low").cast(pl.Float64),
            pl.col("close").cast(pl.Float64),
            pl.col("volume").cast(pl.Float64),
            pl.col("dividend").cast(pl.Float64),
        ]
    )

    for col in EQUITIES_RAW_COLUMNS:
        if df[col].null_count() > 0:
            raise HistoricalIngestionError(f"Valores nulos detectados na coluna '{col}' de ações.")

    if df.select(pl.struct(["date", "ticker"]).is_duplicated()).to_series().any():
        raise HistoricalIngestionError("Duplicatas detectadas para a chave ('date', 'ticker').")

    invalid_prices = df.filter(
        (pl.col("open") <= 0)
        | (pl.col("high") <= 0)
        | (pl.col("low") <= 0)
        | (pl.col("close") <= 0)
        | (pl.col("high") < pl.col("low"))
    )
    if invalid_prices.height > 0:
        raise HistoricalIngestionError("Preços inválidos (<= 0 ou high < low) detectados em ações.")

    if df.filter((pl.col("volume") < 0) | (pl.col("dividend") < 0)).height > 0:
        raise HistoricalIngestionError("Volume ou provento negativo detectado em ações.")

    # Ordena cronologicamente por ativo para cálculo estritamente causal (sem look-ahead)
    df = df.sort(["ticker", "date"])

    # Fator diário de provento causal: no dia ex, step = 1 + dividend_t / close_{t-1}
    prev_close = pl.col("close").shift(1).over("ticker")
    step_factor = (
        pl.when(prev_close.is_not_null() & (pl.col("dividend") > 0))
        .then(1.0 + (pl.col("dividend") / prev_close))
        .otherwise(1.0)
    )

    df = df.with_columns(
        step_factor.cum_prod().over("ticker").alias("cumulative_dividend_factor"),
    ).with_columns(
        (pl.col("close") * pl.col("cumulative_dividend_factor")).alias("causal_total_return_index"),
    )

    return df.sort(["date", "ticker"])


def validate_and_curate_benchmark(raw_df: pl.DataFrame) -> pl.DataFrame:
    """Valida e padroniza a série histórica de benchmark (ex.: Ibovespa)."""
    missing = [c for c in BENCHMARK_RAW_COLUMNS if c not in raw_df.columns]
    if missing:
        raise HistoricalIngestionError(f"Colunas ausentes no benchmark: {missing}")
    if raw_df.is_empty():
        raise HistoricalIngestionError("Dataset de benchmark está vazio para o período solicitado.")

    df = raw_df.select(
        [
            pl.col("date").cast(pl.Date),
            pl.col("symbol").cast(pl.String).str.strip_chars().str.to_uppercase(),
            pl.col("close").cast(pl.Float64),
        ]
    )

    for col in BENCHMARK_RAW_COLUMNS:
        if df[col].null_count() > 0:
            raise HistoricalIngestionError(
                f"Valores nulos detectados na coluna '{col}' do benchmark."
            )

    if df.select(pl.struct(["date", "symbol"]).is_duplicated()).to_series().any():
        raise HistoricalIngestionError(
            "Duplicatas detectadas no benchmark para ('date', 'symbol')."
        )

    if df.filter(pl.col("close") <= 0).height > 0:
        raise HistoricalIngestionError("Pontuação <= 0 detectada no benchmark.")

    df = df.sort(["symbol", "date"])
    prev_close = pl.col("close").shift(1).over("symbol")
    daily_return = (
        pl.when(prev_close.is_not_null()).then((pl.col("close") / prev_close) - 1.0).otherwise(0.0)
    )

    return df.with_columns(daily_return.alias("daily_return")).sort(["date", "symbol"])


def validate_and_curate_cdi(raw_df: pl.DataFrame) -> pl.DataFrame:
    """Valida a série diária do CDI e calcula o fator acumulado para remuneração de caixa."""
    missing = [c for c in CDI_RAW_COLUMNS if c not in raw_df.columns]
    if missing:
        raise HistoricalIngestionError(f"Colunas ausentes no CDI: {missing}")
    if raw_df.is_empty():
        raise HistoricalIngestionError("Dataset de CDI está vazio para o período solicitado.")

    df = raw_df.select(
        [
            pl.col("date").cast(pl.Date),
            pl.col("daily_rate").cast(pl.Float64),
        ]
    )

    for col in CDI_RAW_COLUMNS:
        if df[col].null_count() > 0:
            raise HistoricalIngestionError(f"Valores nulos detectados na coluna '{col}' do CDI.")

    if df.select(pl.col("date").is_duplicated()).to_series().any():
        raise HistoricalIngestionError("Datas duplicadas detectadas na série do CDI.")

    if df.filter(pl.col("daily_rate") < 0).height > 0:
        raise HistoricalIngestionError("Taxa diária negativa detectada na série do CDI.")

    df = df.sort("date")
    return df.with_columns(
        (1.0 + pl.col("daily_rate")).alias("daily_factor"),
        (1.0 + pl.col("daily_rate")).cum_prod().alias("cdi_accumulated_index"),
    )


def run_historical_ingestion_pipeline(
    equities_provider: EquitiesProvider,
    benchmark_provider: BenchmarkProvider,
    cdi_provider: CdiProvider,
    start_date: date,
    end_date: date,
    output_dir: str | Path,
    collected_at: datetime | None = None,
) -> IngestionManifest:
    """Executa o pipeline completo de ingestão histórica, gravando camadas Parquet e manifest.json.

    Estrutura gravada em `output_dir`:
    - `raw/equities.parquet`, `raw/benchmark.parquet`, `raw/cdi.parquet`
    - `curated/equities.parquet`, `curated/benchmark.parquet`, `curated/cdi.parquet`
    - `manifest.json` (com versões, fontes, contagem de linhas e hashes SHA-256)
    """
    if start_date > end_date:
        raise HistoricalIngestionError("start_date não pode ser posterior a end_date.")

    base_path = Path(output_dir)
    raw_dir = base_path / "raw"
    curated_dir = base_path / "curated"
    raw_dir.mkdir(parents=True, exist_ok=True)
    curated_dir.mkdir(parents=True, exist_ok=True)

    # 1. Coleta das 3 fontes
    raw_equities = equities_provider.fetch_equities(start_date, end_date)
    raw_benchmark = benchmark_provider.fetch_benchmark(start_date, end_date)
    raw_cdi = cdi_provider.fetch_cdi(start_date, end_date)

    # 2. Validação e tratamento (camada curated)
    curated_equities = validate_and_curate_equities(raw_equities)
    curated_benchmark = validate_and_curate_benchmark(raw_benchmark)
    curated_cdi = validate_and_curate_cdi(raw_cdi)

    # Ordena camada raw de forma determinística antes de persistir para garantir idempotência de hash
    raw_equities_sorted = raw_equities.select(EQUITIES_RAW_COLUMNS).sort(["date", "ticker"])
    raw_benchmark_sorted = raw_benchmark.select(BENCHMARK_RAW_COLUMNS).sort(["date", "symbol"])
    raw_cdi_sorted = raw_cdi.select(CDI_RAW_COLUMNS).sort("date")

    # 3. Persistência determinística em Parquet nas camadas raw e curated
    datasets_to_write: list[tuple[str, Literal["raw", "curated"], pl.DataFrame, Path]] = [
        ("equities", "raw", raw_equities_sorted, raw_dir / "equities.parquet"),
        ("benchmark", "raw", raw_benchmark_sorted, raw_dir / "benchmark.parquet"),
        ("cdi", "raw", raw_cdi_sorted, raw_dir / "cdi.parquet"),
        ("equities", "curated", curated_equities, curated_dir / "equities.parquet"),
        ("benchmark", "curated", curated_benchmark, curated_dir / "benchmark.parquet"),
        ("cdi", "curated", curated_cdi, curated_dir / "cdi.parquet"),
    ]

    artifacts: list[ArtifactMetadata] = []
    for ds_name, layer, df_obj, file_path in datasets_to_write:
        df_obj.write_parquet(file_path)
        rel_path = file_path.relative_to(base_path).as_posix()
        artifacts.append(
            ArtifactMetadata(
                dataset=ds_name,
                layer=layer,
                relative_path=rel_path,
                row_count=df_obj.height,
                sha256=compute_file_sha256(file_path),
            )
        )

    ts = collected_at or datetime.now(UTC)
    manifest = IngestionManifest(
        schema_version=SCHEMA_VERSION,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        collected_at=ts.isoformat(),
        sources={
            "equities": equities_provider.source_name,
            "benchmark": benchmark_provider.source_name,
            "cdi": cdi_provider.source_name,
        },
        artifacts=artifacts,
    )

    manifest_path = base_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return manifest


def load_curated_dataset(
    output_dir: str | Path,
    dataset: DatasetKind,
    verify_hash: bool = True,
) -> pl.DataFrame:
    """Carrega um dataset tratado ('equities', 'benchmark' ou 'cdi') validando o hash no manifest."""
    base_path = Path(output_dir)
    manifest_path = base_path / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifesto não encontrado em: {manifest_path}")

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    matching = [
        a
        for a in manifest_data.get("artifacts", [])
        if a.get("dataset") == dataset and a.get("layer") == "curated"
    ]
    if not matching:
        raise HistoricalIngestionError(
            f"Artefato curated para '{dataset}' não registrado no manifesto."
        )

    artifact = matching[0]
    parquet_path = base_path / artifact["relative_path"]
    if not parquet_path.exists():
        raise FileNotFoundError(f"Arquivo Parquet não encontrado: {parquet_path}")

    if verify_hash:
        actual_hash = compute_file_sha256(parquet_path)
        if actual_hash != artifact["sha256"]:
            raise HistoricalIngestionError(
                f"Falha de integridade em '{dataset}': hash atual ({actual_hash}) "
                f"difere do manifesto ({artifact['sha256']})."
            )

    return pl.read_parquet(parquet_path)
