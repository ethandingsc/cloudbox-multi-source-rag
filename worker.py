"""Kafka consumer that runs the existing RAG pipeline outside the API."""

import json
import os
import time

from src import service


def main() -> None:
    from kafka import KafkaConsumer
    from api import run_rag

    consumer = KafkaConsumer(
        service.TOPIC,
        bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        group_id="cloudbox-rag-workers",
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )
    for record in consumer:
        try:
            service.process_job(record.value, run_rag)
            consumer.commit()
        except service.InvalidJobMessage:
            # A poison message cannot become valid on retry. Commit it so one
            # malformed record does not block every later job in the partition.
            consumer.commit()
        except Exception:
            # A short retry prevents a transient lock or Redis outage from
            # silently acknowledging the message.
            time.sleep(2)
            from kafka import TopicPartition
            consumer.seek(TopicPartition(record.topic, record.partition),
                          record.offset)


if __name__ == "__main__":
    main()
