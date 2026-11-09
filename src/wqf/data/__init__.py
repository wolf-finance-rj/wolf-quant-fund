"""Subpacote de engenharia de dados do Wolf Quant Fund."""

from wqf.data.pipelines import (
    SCHEMA_VERSION,
    ArtifactMetadata,
    HistoricalIngestionError,
    IngestionManifest,
    load_curated_dataset,
    run_historical_ingestion_pipeline,
)
from wqf.data.providers import (
    BenchmarkBar,
    BenchmarkProvider,
    CdiProvider,
    CdiRatePoint,
    EquitiesProvider,
    EquityBar,
    InMemoryBenchmarkProvider,
    InMemoryCdiProvider,
    InMemoryEquitiesProvider,
)

__all__ = [
    "SCHEMA_VERSION",
    "ArtifactMetadata",
    "BenchmarkBar",
    "BenchmarkProvider",
    "CdiProvider",
    "CdiRatePoint",
    "EquitiesProvider",
    "EquityBar",
    "HistoricalIngestionError",
    "InMemoryBenchmarkProvider",
    "InMemoryCdiProvider",
    "InMemoryEquitiesProvider",
    "IngestionManifest",
    "load_curated_dataset",
    "run_historical_ingestion_pipeline",
]
