import os
import sys

os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)

from pyspark.sql import SparkSession, types as T

from .schema import ANON_FEATURES


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

from pyspark.sql import functions as F
from .scoring import score_transaction


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
