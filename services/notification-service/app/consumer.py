import json
import logging
import time

import pika

from .config import RABBITMQ_URL
from .db import SessionLocal
from .models import Notification

logger = logging.getLogger("notification-service")

EXCHANGE = "tasks"
QUEUE = "notifications"
BINDING_KEY = "task.*"

# для /ready: подключён ли потребитель к брокеру
state = {"connected": False}


def build_notifications(event: dict) -> list[tuple[int, str]]:
    """По событию решает, кому и что отправить: список (user_id, текст)."""
    event_type = event.get("type")
    title = event.get("title", "")
    actor = event.get("actor_id")

    if event_type == "task.assigned":
        recipients = {event.get("assignee_id")} - {actor, None}
        return [(uid, f"You were assigned to task '{title}'") for uid in recipients]

    if event_type == "task.status_changed":
        recipients = {event.get("assignee_id"), event.get("creator_id")} - {actor, None}
        text = (
            f"Task '{title}' moved from {event.get('old_status')} to {event.get('new_status')}"
        )
        return [(uid, text) for uid in recipients]

    return []  # task.created и неизвестные события: уведомлений нет


def handle_message(body: bytes) -> None:
    event = json.loads(body)
    items = build_notifications(event)
    if not items:
        logger.info("Event ignored: %s", event.get("type"))
        return

    with SessionLocal() as db:
        for user_id, message in items:
            db.add(
                Notification(
                    user_id=user_id,
                    type=event["type"],
                    message=message,
                    task_id=event.get("task_id"),
                    project_id=event.get("project_id"),
                    request_id=event.get("request_id"),
                )
            )
        db.commit()
    logger.info(
        "Event processed: %s notifications=%s request_id=%s",
        event["type"],
        len(items),
        event.get("request_id"),
    )


def consume_forever() -> None:
    """Подключается к RabbitMQ и читает очередь. При обрыве переподключается."""
    while True:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            channel = connection.channel()
            channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
            channel.queue_declare(queue=QUEUE, durable=True)
            channel.queue_bind(queue=QUEUE, exchange=EXCHANGE, routing_key=BINDING_KEY)
            channel.basic_qos(prefetch_count=10)

            def on_message(ch, method, properties, body):
                try:
                    handle_message(body)
                    ch.basic_ack(delivery_tag=method.delivery_tag)  # подтверждаем: обработано
                except Exception:
                    logger.exception("Failed to process message, dropping it")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_consume(queue=QUEUE, on_message_callback=on_message)
            state["connected"] = True
            logger.info("Consumer started: queue=%s binding=%s", QUEUE, BINDING_KEY)
            channel.start_consuming()
        except Exception:
            state["connected"] = False
            logger.exception("Consumer error, reconnecting in 5s")
            time.sleep(5)