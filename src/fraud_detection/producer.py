from __future__ import annotations

import argparse
import json
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from kafka import KafkaProducer

from .config import get_settings
from .kafka_utils import ensure_topic
from .schema import ANON_FEATURES


MERCHANT_CATEGORIES = ["grocery", "electronics", "travel", "fuel", "restaurant", "luxury_retail", "gaming", "pharmacy"]
CHANNELS = ["online", "pos", "contactless", "atm"]
COUNTRIES = ["US", "CA", "GB", "DE", "IN"]
CITIES = ["Chicago", "New York", "Austin", "San Francisco", "Toronto", "London"]


def load_seed_records(path: str | Path) -> tuple[list[dict], list[dict], list[dict]]:
    frame = pd.read_csv(path)
    records = frame.to_dict(orient="records")
    fraud_records = [r for r in records if int(r["Class"]) == 1]
    legit_records = [r for r in records if int(r["Class"]) == 0]
    return records, legit_records, fraud_records


def boosted_fraud_probability(total_records: list[dict], fraud_boost_factor: int) -> float:
    if not total_records:
        return 0.0
    base_rate = sum(int(r["Class"]) for r in total_records) / len(total_records)
    return min(0.5, base_rate * max(fraud_boost_factor, 1))


def build_event(record: dict, rng: random.Random) -> dict:
    payload = {
        "event_ts": datetime.now(timezone.utc).isoformat(),
        "transaction_id": str(uuid.uuid4()),
        "customer_id": f"CUST-{rng.randint(10000, 99999)}",
        "card_token": f"CARD-{rng.randint(100000, 999999)}",
        "merchant_id": f"MER-{rng.randint(1000, 9999)}",
        "merchant_category": rng.choice(MERCHANT_CATEGORIES),
        "channel": rng.choice(CHANNELS),
        "city": rng.choice(CITIES),
        "country_code": rng.choice(COUNTRIES),
        "actual_label": int(record["Class"]),
        "Time": float(record["Time"]),
        "Amount": float(record["Amount"]),
    }
    for feature_name in ANON_FEATURES:
        payload[feature_name] = float(record[feature_name])
    return payload


def choose_record(legit_records: list[dict], fraud_records: list[dict], fraud_probability: float, rng: random.Random) -> dict:
    if fraud_records and rng.random() < fraud_probability:
        return rng.choice(fraud_records)
    return rng.choice(legit_records)


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Replay fraud transactions into Kafka.")
    parser.add_argument("--rate", type=float, default=settings.producer_rate_per_second)
    parser.add_argument("--fraud-boost", type=int, default=settings.fraud_boost_factor)
    parser.add_argument("--limit", type=int, default=settings.stream_limit)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seed-path", type=Path, default=settings.streaming_seed_path)
    args = parser.parse_args()

    total_records, legit_records, fraud_records = load_seed_records(args.seed_path)
    if not legit_records:
        raise RuntimeError("The streaming seed file does not contain legitimate transactions.")

    rng = random.Random(args.seed)
    fraud_probability = boosted_fraud_probability(total_records, args.fraud_boost)

    bootstrap_servers = [s.strip() for s in settings.kafka_bootstrap_servers.split(",")]
    ensure_topic(bootstrap_servers, settings.kafka_topic)

    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        linger_ms=50,
    )

    print(f"Producing to topic '{settings.kafka_topic}' at ~{args.rate:.2f} events/sec with fraud probability {fraud_probability:.4f}.")
    produced = 0
    sleep_time = 1.0 / args.rate if args.rate > 0 else 0.0

    try:
        while args.limit <= 0 or produced < args.limit:
            record = choose_record(legit_records, fraud_records, fraud_probability, rng)
            event = build_event(record, rng)
            producer.send(settings.kafka_topic, event)
            produced += 1
            if produced % 100 == 0:
                producer.flush()
                print(f"Published {produced} events...")
            if sleep_time > 0:
                time.sleep(sleep_time)
    except KeyboardInterrupt:
        print("Producer interrupted.")
    finally:
        producer.flush()
        producer.close()
        print(f"Producer finished after {produced} events.")


if __name__ == "__main__":
    main()
