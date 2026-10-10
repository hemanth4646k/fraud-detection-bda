import os
import sys
import time

os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)

from pyspark.sql import SparkSession, functions as F, types as T

from .config import get_settings
from .kafka_utils import ensure_topic
from .schema import ANON_FEATURES
from .scoring import load_model_artifact, score_transaction


def build_transaction_schema() -> T.StructType:
    metadata_fields = [
        T.StructField("event_ts", T.StringType(), True),
        T.StructField("transaction_id", T.StringType(), True),
        T.StructField("customer_id", T.StringType(), True),
        T.StructField("card_token", T.StringType(), True),
        T.StructField("merchant_id", T.StringType(), True),
        T.StructField("merchant_category", T.StringType(), True),
        T.StructField("channel", T.StringType(), True),
        T.StructField("city", T.StringType(), True),
        T.StructField("country_code", T.StringType(), True),
        T.StructField("actual_label", T.IntegerType(), True),
        T.StructField("Time", T.DoubleType(), True),
        T.StructField("Amount", T.DoubleType(), True),
    ]
    feature_fields = [T.StructField(name, T.DoubleType(), True) for name in ANON_FEATURES]
    return T.StructType(metadata_fields + feature_fields)


def build_spark_session(settings) -> SparkSession:
    builder = SparkSession.builder.appName(settings.spark_app_name).master(settings.spark_master)
    if settings.spark_kafka_package:
        builder = builder.config("spark.jars.packages", settings.spark_kafka_package)
    spark = builder.config("spark.sql.session.timeZone", "UTC").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    spark.conf.set("spark.sql.shuffle.partitions", str(settings.spark_shuffle_partitions))
    return spark


def build_score_udf(spark: SparkSession, artifact: dict):
    broadcast_artifact = spark.sparkContext.broadcast(artifact)
    output_schema = T.StructType([
        T.StructField("risk_score", T.DoubleType(), False),
        T.StructField("predicted_label", T.IntegerType(), False),
    ])

    def _score(payload):
        if payload is None:
            return 0.0, 0
        record = payload.asDict(recursive=True) if hasattr(payload, "asDict") else dict(payload)
        probability, predicted_label = score_transaction(record, broadcast_artifact.value)
        return float(probability), int(predicted_label)

    return F.udf(_score, output_schema)


def alert_level_expression(min_alert_probability: float):
    return (
        F.when(F.col("risk_score") >= 0.95, F.lit("critical"))
        .when(F.col("risk_score") >= 0.85, F.lit("high"))
        .when(F.col("risk_score") >= float(min_alert_probability), F.lit("medium"))
        .otherwise(F.lit("monitor"))
    )


def main() -> None:
    settings = get_settings()
    settings.ensure_local_dirs()

    artifact = load_model_artifact(settings.model_artifact_path)
    if settings.model_threshold_override is not None:
        artifact["threshold"] = float(settings.model_threshold_override)

    bootstrap_servers = [s.strip() for s in settings.kafka_bootstrap_servers.split(",")]
    ensure_topic(bootstrap_servers, settings.kafka_topic)

    spark = build_spark_session(settings)
    score_udf = build_score_udf(spark, artifact)

    kafka_stream = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", settings.kafka_bootstrap_servers)
        .option("subscribe", settings.kafka_topic)
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )

    parsed_stream = (
        kafka_stream.select(
            F.from_json(F.col("value").cast("string"), build_transaction_schema()).alias("payload")
        )
        .select("payload.*")
        .dropna(subset=["transaction_id"])
    )

    payload_columns = [F.col(col) for col in parsed_stream.columns]
    scored_stream = (
        parsed_stream.withColumn("model_output", score_udf(F.struct(*payload_columns)))
        .withColumn("risk_score", F.col("model_output.risk_score"))
        .withColumn("predicted_label", F.col("model_output.predicted_label"))
        .drop("model_output")
        .withColumn("processed_at", F.current_timestamp())
        .withColumn("model_threshold", F.lit(float(artifact["threshold"])))
        .withColumn("alert_level", alert_level_expression(settings.min_alert_probability))
    )

    alerts_stream = scored_stream.filter(
        (F.col("predicted_label") == 1) | (F.col("risk_score") >= float(settings.min_alert_probability))
    )

    queries = [
        scored_stream.writeStream.format("parquet")
        .outputMode("append")
        .option("path", str(settings.predictions_dir))
        .option("checkpointLocation", str(settings.checkpoint_dir / "predictions"))
        .start(),
        alerts_stream.writeStream.format("parquet")
        .outputMode("append")
        .option("path", str(settings.alerts_dir))
        .option("checkpointLocation", str(settings.checkpoint_dir / "alerts"))
        .start(),
    ]

    print(
        f"Spark fraud scorer running | topic={settings.kafka_topic} "
        f"| local sink={settings.predictions_dir}"
    )

    try:
        while True:
            inactive = [q for q in queries if not q.isActive]
            if inactive:
                exc = inactive[0].exception()
                if exc is not None:
                    raise RuntimeError(f"Streaming query failed: {exc}")
                break
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Stopping streaming queries...")
        for q in queries:
            if q.isActive:
                q.stop()
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
