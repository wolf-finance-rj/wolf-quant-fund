"""Subpacote de dados do Wolf Quant Fund: ingestão, validação e persistência."""

from wqf.data.csv_reader import ingest_market_csv, read_market_csv
from wqf.data.exceptions import DataValidationError
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
from wqf.data.validator import REQUIRED_COLUMNS, ValidationReport, validate_market_data

__all__ = [
    "REQUIRED_COLUMNS",
    "SCHEMA_VERSION",
    "ArtifactMetadata",
    "BenchmarkBar",
    "BenchmarkProvider",
    "CdiProvider",
    "CdiRatePoint",
    "DataValidationError",
    "EquitiesProvider",
    "EquityBar",
    "HistoricalIngestionError",
    "InMemoryBenchmarkProvider",
    "InMemoryCdiProvider",
    "InMemoryEquitiesProvider",
    "IngestionManifest",
    "ValidationReport",
    "ingest_market_csv",
    "load_curated_dataset",
    "read_market_csv",
    "run_historical_ingestion_pipeline",
    "validate_market_data",
]
