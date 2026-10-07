from __future__ import annotations

import time

from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import KafkaError, TopicAlreadyExistsError


def ensure_topic(
    bootstrap_servers: list[str],
    topic_name: str,
    num_partitions: int = 1,
    replication_factor: int = 1,
    retries: int = 10,
    retry_delay_seconds: float = 2.0,
) -> None:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        admin = None
        try:
            admin = KafkaAdminClient(bootstrap_servers=bootstrap_servers, client_id="fraud-topic-bootstrap")
            admin.create_topics(
                new_topics=[NewTopic(name=topic_name, num_partitions=num_partitions, replication_factor=replication_factor)],
                validate_only=False,
            )
            print(f"Created Kafka topic '{topic_name}'.")
            return
        except TopicAlreadyExistsError:
            return
        except (KafkaError, OSError) as exc:
            last_error = exc
            if attempt == retries:
                break
            print(f"Kafka broker not reachable (attempt {attempt}/{retries}). Retrying in {retry_delay_seconds:.1f}s...")
            time.sleep(retry_delay_seconds)
        finally:
            if admin is not None:
                admin.close()
    raise RuntimeError(f"Unable to reach Kafka brokers at {bootstrap_servers}.") from last_error
