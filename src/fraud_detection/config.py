from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs) -> bool:
        return False


def _detect_project_root() -> Path:
    override = os.getenv("FRAUD_PROJECT_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    candidates: list[Path] = []
    cwd = Path.cwd().resolve()
    candidates.extend([cwd, *cwd.parents])
    module_path = Path(__file__).resolve()
    candidates.extend(module_path.parents)
    for candidate in candidates:
        if (candidate / "pyproject.toml").exists() and (candidate / "src" / "fraud_detection").exists():
            return candidate
    return cwd


PROJECT_ROOT = _detect_project_root()
load_dotenv(PROJECT_ROOT / ".env")


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()

def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}

def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw not in {None, ""} else default

def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw not in {None, ""} else default

def _env_optional_float(name: str) -> float | None:
    raw = os.getenv(name)
    return None if raw in {None, ""} else float(raw)

def _env_optional_str(name: str) -> str | None:
    raw = os.getenv(name)
    return None if raw in {None, ""} else raw.strip()

def _env_optional_int(name: str) -> int | None:
    raw = os.getenv(name)
    return None if raw in {None, ""} else int(raw)

def _env_path(name: str, default: str) -> Path:
    candidate = Path(_env(name, default)).expanduser()
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate


@dataclass(frozen=True)
class Settings:
    project_root: Path
    dataset_url: str
    raw_data_path: Path
    streaming_seed_path: Path
    model_artifact_path: Path
    metrics_path: Path
    kafka_bootstrap_servers: str
    kafka_topic: str
    producer_rate_per_second: float
    fraud_boost_factor: int
    stream_limit: int
    spark_master: str
    spark_app_name: str
    spark_kafka_package: str
    spark_shuffle_partitions: int
    checkpoint_dir: Path
    predictions_dir: Path
    alerts_dir: Path
    min_alert_probability: float
    model_threshold_override: float | None
    s3_enabled: bool
    s3_endpoint_url: str | None
    s3_access_key: str | None
    s3_secret_key: str | None
    s3_bucket: str
    s3_predictions_prefix: str
    s3_alerts_prefix: str
    s3_region: str
    snowflake_enabled: bool
    snowflake_account: str | None
    snowflake_user: str | None
    snowflake_password: str | None
    snowflake_warehouse: str | None
    snowflake_database: str | None
    snowflake_schema: str | None
    snowflake_role: str | None
    snowflake_table: str
    dashboard_predictions_path: Path
    dashboard_alerts_path: Path
    dashboard_max_files: int | None

    def ensure_local_dirs(self) -> None:
        for path in (
            self.raw_data_path.parent,
            self.streaming_seed_path.parent,
            self.model_artifact_path.parent,
            self.metrics_path.parent,
            self.checkpoint_dir,
            self.predictions_dir,
            self.alerts_dir,
            self.dashboard_predictions_path,
            self.dashboard_alerts_path,
        ):
            path.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings(
        project_root=PROJECT_ROOT,
        dataset_url=_env("FRAUD_DATASET_URL",
            "https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv"),
        raw_data_path=_env_path("RAW_DATA_PATH", "data/raw/creditcard.csv"),
        streaming_seed_path=_env_path("STREAMING_SEED_PATH", "data/processed/streaming_seed.csv"),
        model_artifact_path=_env_path("MODEL_ARTIFACT_PATH", "data/artifacts/logistic_fraud_model.json"),
        metrics_path=_env_path("METRICS_PATH", "data/artifacts/training_metrics.json"),
        kafka_bootstrap_servers=_env("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        kafka_topic=_env("KAFKA_TOPIC", "transactions"),
        producer_rate_per_second=_env_float("PRODUCER_RATE_PER_SECOND", 10.0),
        fraud_boost_factor=_env_int("FRAUD_BOOST_FACTOR", 25),
        stream_limit=_env_int("STREAM_LIMIT", 0),
        spark_master=_env("SPARK_MASTER", "local[*]"),
        spark_app_name=_env("SPARK_APP_NAME", "fraud-detection-stream"),
        spark_kafka_package=_env("SPARK_KAFKA_PACKAGE",
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1"),
        spark_shuffle_partitions=_env_int("SPARK_SHUFFLE_PARTITIONS", 4),
        checkpoint_dir=_env_path("CHECKPOINT_DIR", "data/outputs/checkpoints"),
        predictions_dir=_env_path("PREDICTIONS_DIR", "data/outputs/predictions"),
        alerts_dir=_env_path("ALERTS_DIR", "data/outputs/alerts"),
        min_alert_probability=_env_float("MIN_ALERT_PROBABILITY", 0.75),
        model_threshold_override=_env_optional_float("MODEL_THRESHOLD_OVERRIDE"),
        s3_enabled=_env_bool("S3_ENABLED", True),
        s3_endpoint_url=_env_optional_str("S3_ENDPOINT_URL"),
        s3_access_key=_env_optional_str("S3_ACCESS_KEY"),
        s3_secret_key=_env_optional_str("S3_SECRET_KEY"),
        s3_bucket=_env("S3_BUCKET", "fraud-lake"),
        s3_predictions_prefix=_env("S3_PREDICTIONS_PREFIX", "predictions"),
        s3_alerts_prefix=_env("S3_ALERTS_PREFIX", "alerts"),
        s3_region=_env("S3_REGION", "us-east-1"),
        snowflake_enabled=_env_bool("SNOWFLAKE_ENABLED", False),
        snowflake_account=_env_optional_str("SNOWFLAKE_ACCOUNT"),
        snowflake_user=_env_optional_str("SNOWFLAKE_USER"),
        snowflake_password=_env_optional_str("SNOWFLAKE_PASSWORD"),
        snowflake_warehouse=_env_optional_str("SNOWFLAKE_WAREHOUSE"),
        snowflake_database=_env_optional_str("SNOWFLAKE_DATABASE"),
        snowflake_schema=_env_optional_str("SNOWFLAKE_SCHEMA"),
        snowflake_role=_env_optional_str("SNOWFLAKE_ROLE"),
        snowflake_table=_env("SNOWFLAKE_TABLE", "FRAUD_PREDICTIONS"),
        dashboard_predictions_path=_env_path("DASHBOARD_PREDICTIONS_PATH", "data/outputs/predictions"),
        dashboard_alerts_path=_env_path("DASHBOARD_ALERTS_PATH", "data/outputs/alerts"),
        dashboard_max_files=_env_optional_int("DASHBOARD_MAX_FILES"),
    )
