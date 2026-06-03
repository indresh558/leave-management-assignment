import os
import json
import logging

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message

logger = logging.getLogger("rabbitmq")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq/")
NOTIFICATION_EXCHANGE = "notifications"


async def publish_notification(event_type: str, payload: dict):
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                NOTIFICATION_EXCHANGE,
                ExchangeType.TOPIC,
                durable=True
            )
            message = Message(
                body=json.dumps(payload).encode(),
                delivery_mode=DeliveryMode.PERSISTENT
            )
            await exchange.publish(message, routing_key=event_type)
            logger.info("Published notification %s", event_type)
    except Exception:
        logger.exception("Failed to publish RabbitMQ notification")
