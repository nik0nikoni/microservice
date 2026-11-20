import json
import logging

import pika

from .config import RABBITMQ_URL

logger = logging.getLogger("task-service")

EXCHANGE = "tasks"


def publish(event_type: str, payload: dict, request_id: str | None = None) -> None:
    """Публикует событие в RabbitMQ (topic exchange 'tasks').

    Если брокер недоступен, задача уже сохранена: пишем ошибку в лог и не роняем запрос.
    """
    message = {"type": event_type, "request_id": request_id, **payload}
    try:
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
        channel.basic_publish(
            exchange=EXCHANGE,
            routing_key=event_type,
            body=json.dumps(message, default=str),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
        )
        connection.close()
        logger.info("Event published: %s request_id=%s", event_type, request_id)
    except Exception:
        logger.exception("Failed to publish event %s", event_type)