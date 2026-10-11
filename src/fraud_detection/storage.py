from __future__ import annotations

import io
from datetime import datetime, timezone

import boto3
import pandas as pd
from botocore.exceptions import ClientError

from .config import Settings


def _batch_to_pandas(batch_frame) -> pd.DataFrame:
    if batch_frame.limit(1).count() == 0:
        return pd.DataFrame()
    return batch_frame.toPandas()


def _s3_client(settings: Settings):
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )


def ensure_s3_bucket(settings: Settings) -> None:
    if not settings.s3_enabled:
        return

    client = _s3_client(settings)
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)


def upload_dataframe_to_s3(
    frame: pd.DataFrame,
    prefix: str,
    batch_id: int,
    settings: Settings,
) -> None:
    if frame.empty or not settings.s3_enabled:
        return

    ensure_s3_bucket(settings)
    client = _s3_client(settings)
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    buffer.seek(0)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"{prefix.rstrip('/')}/batch_id={batch_id}/microbatch_{timestamp}.parquet"
    client.put_object(Bucket=settings.s3_bucket, Key=key, Body=buffer.getvalue())
    print(f"Uploaded {len(frame)} rows to s3://{settings.s3_bucket}/{key}")


def _missing_snowflake_config(settings: Settings) -> bool:
    required = [
        settings.snowflake_account,
        settings.snowflake_user,
        settings.snowflake_password,
        settings.snowflake_warehouse,
        settings.snowflake_database,
        settings.snowflake_schema,
    ]
    return any(value in {None, ""} for value in required)


def _snowflake_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(series):
        return "NUMBER"
    if pd.api.types.is_float_dtype(series):
        return "FLOAT"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "TIMESTAMP_NTZ"
    return "VARCHAR"


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _qualified_table_name(settings: Settings) -> str:
    database = _quote(settings.snowflake_database.upper()) if settings.snowflake_database else None
    schema = _quote(settings.snowflake_schema.upper()) if settings.snowflake_schema else None
    table = _quote(settings.snowflake_table.upper())
    return ".".join(part for part in (database, schema, table) if part)


def ensure_snowflake_table(connection, frame: pd.DataFrame, settings: Settings) -> None:
    normalized = frame.copy()
    normalized.columns = [str(column).upper() for column in normalized.columns]
    column_definitions = ", ".join(
        f"{_quote(column)} {_snowflake_type(normalized[column])}"
        for column in normalized.columns
    )
    ddl = f"CREATE TABLE IF NOT EXISTS {_qualified_table_name(settings)} ({column_definitions})"
    with connection.cursor() as cursor:
        cursor.execute(ddl)


def write_dataframe_to_snowflake(frame: pd.DataFrame, settings: Settings) -> None:
    if frame.empty or not settings.snowflake_enabled or _missing_snowflake_config(settings):
        return

    import snowflake.connector
    from snowflake.connector.pandas_tools import write_pandas

    normalized = frame.copy()
    normalized.columns = [str(column).upper() for column in normalized.columns]

    connection_kwargs = {
        "account": settings.snowflake_account,
        "user": settings.snowflake_user,
        "password": settings.snowflake_password,
        "warehouse": settings.snowflake_warehouse,
        "database": settings.snowflake_database,
        "schema": settings.snowflake_schema,
    }
    if settings.snowflake_role:
        connection_kwargs["role"] = settings.snowflake_role

    connection = snowflake.connector.connect(**connection_kwargs)
    try:
        ensure_snowflake_table(connection, normalized, settings)
        success, _, rows_written, _ = write_pandas(
            connection,
            normalized,
            settings.snowflake_table.upper(),
            database=settings.snowflake_database.upper() if settings.snowflake_database else None,
            schema=settings.snowflake_schema.upper() if settings.snowflake_schema else None,
        )
        if not success:
            raise RuntimeError("Snowflake write_pandas returned an unsuccessful status.")
        print(f"Wrote {rows_written} rows to Snowflake table {settings.snowflake_table.upper()}")
    finally:
        connection.close()


def export_predictions_batch(batch_frame, batch_id: int, settings: Settings) -> None:
    frame = _batch_to_pandas(batch_frame)
    if frame.empty:
        return
    if settings.s3_enabled:
        upload_dataframe_to_s3(frame, settings.s3_predictions_prefix, batch_id, settings)
    if settings.snowflake_enabled:
        write_dataframe_to_snowflake(frame, settings)


def export_alerts_batch(batch_frame, batch_id: int, settings: Settings) -> None:
    frame = _batch_to_pandas(batch_frame)
    if frame.empty:
        return
    if settings.s3_enabled:
        upload_dataframe_to_s3(frame, settings.s3_alerts_prefix, batch_id, settings)

