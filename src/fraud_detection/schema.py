ANON_FEATURES = [f"V{i}" for i in range(1, 29)]
RAW_FEATURE_COLUMNS = ["Time", "Amount", *ANON_FEATURES]
MODEL_FEATURES = [
    *ANON_FEATURES,
    "Time",
    "Amount",
    "AmountLog",
    "HourOfDay",
    "DayIndex",
    "IsNight",
    "IsHighAmount",
]
STREAM_METADATA_COLUMNS = [
    "event_ts",
    "transaction_id",
    "customer_id",
    "card_token",
    "merchant_id",
    "merchant_category",
    "channel",
    "city",
    "country_code",
    "actual_label",
]
