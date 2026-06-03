import json
import logging
import os
import asyncio
from datetime import datetime
from typing import Optional

import aio_pika
from aio_pika import ExchangeType

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s %(message)s"
)

logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq/")
MAX_RETRIES = int(os.getenv("NOTIFICATION_MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("NOTIFICATION_RETRY_DELAY", "5"))  # seconds


class NotificationConsumer:

    def __init__(self):
        self.connection = None
        self.channel = None
        self.exchange = None
        self.notification_history = []  # In-memory store (use DB in production)
        self.max_history = 1000  # Keep last 1000 notifications

    async def start(self):
        """Start the RabbitMQ consumer with retry logic."""
        max_attempts = MAX_RETRIES
        attempt = 0
        
        while attempt < max_attempts:
            try:
                self.connection = await aio_pika.connect_robust(
                    RABBITMQ_URL,
                    reconnect_interval=5
                )
                self.channel = await self.connection.channel()
                self.exchange = await self.channel.declare_exchange(
                    "notifications",
                    ExchangeType.TOPIC,
                    durable=True
                )
                queue = await self.channel.declare_queue(
                    "notification_queue",
                    durable=True
                )
                await queue.bind(self.exchange, routing_key="leave.*")
                await queue.consume(self._on_message)
                logger.info(f"✅ Notification consumer started successfully")
                await asyncio.Future()  # Keep running
                
            except Exception as e:
                attempt += 1
                logger.error(f"❌ Failed to start consumer (attempt {attempt}/{max_attempts}): {str(e)}")
                if attempt < max_attempts:
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    logger.critical("Max retries exceeded. Consumer startup failed.")
                    raise

    async def _on_message(self, message: aio_pika.IncomingMessage):
        """Process incoming RabbitMQ message with retry logic."""
        async with message.process():
            try:
                payload = json.loads(message.body.decode())
                routing_key = message.routing_key
                
                logger.debug(f"Received notification: {routing_key}")
                logger.debug(f"Payload: {payload}")
                
                # Route to appropriate handler
                if routing_key == "leave.applied":
                    await self._handle_leave_applied(payload)
                elif routing_key == "leave.approved":
                    await self._handle_leave_approved(payload)
                elif routing_key == "leave.rejected":
                    await self._handle_leave_rejected(payload)
                else:
                    logger.warning(f"Unknown routing key: {routing_key}")
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse notification message: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing notification: {str(e)}", exc_info=True)

    def _store_notification(self, notification_type: str, recipient: str, subject: str, content: str, status: str = "SENT"):
        """Store notification in history with auto-cleanup of old records."""
        notification = {
            "timestamp": datetime.now().isoformat(),
            "type": notification_type,
            "recipient": recipient,
            "subject": subject,
            "content": content,
            "status": status
        }
        
        self.notification_history.append(notification)
        
        # Clean up old records if exceeds max
        if len(self.notification_history) > self.max_history:
            self.notification_history = self.notification_history[-self.max_history:]
        
        return notification

    async def _handle_leave_applied(self, payload: dict):
        """
        Handle leave.applied event - notify manager.
        
        Manager should be notified that an employee has applied for leave.
        """
        try:
            leave_id = payload.get("leave_id")
            employee_username = payload.get("employee_username")
            leave_type = payload.get("leave_type")
            start_date = payload.get("start_date")
            end_date = payload.get("end_date")
            status = payload.get("status", "PENDING")
            
            subject = f"New Leave Application - {employee_username}"
            content = f"""
            LEAVE APPLICATION NOTIFICATION
            
            Leave ID: {leave_id}
            Employee: {employee_username}
            Leave Type: {leave_type}
            Start Date: {start_date}
            End Date: {end_date}
            Status: {status}
            
            ⏰ ACTION REQUIRED: Please approve or reject this leave request
            
            Timestamp: {datetime.now().isoformat()}
            """
            
            # Store notification
            manager_username = payload.get("manager_username", "manager")
            self._store_notification(
                notification_type="LEAVE_APPLIED",
                recipient=manager_username,
                subject=subject,
                content=content,
                status="SENT"
            )
            
            logger.info(f"📢 Leave application notification: {employee_username} → {manager_username}")
            
            # In production, implement actual sending:
            # await self._send_email(manager_username, subject, content)
            # await self._send_slack_message(manager_username, subject)
            # await self._send_sms(manager_username, subject)
            
        except Exception as e:
            logger.error(f"Error handling leave.applied: {str(e)}", exc_info=True)
            raise
        
    async def _handle_leave_approved(self, payload: dict):
        """
        Handle leave.approved event - notify employee.
        """
        try:
            leave_id = payload.get("leave_id")
            employee_username = payload.get("employee_username")
            approved_by = payload.get("approved_by")
            leave_type = payload.get("leave_type")
            start_date = payload.get("start_date")
            end_date = payload.get("end_date")
            
            subject = f"Leave Approved - {leave_type}"
            content = f"""
            LEAVE APPROVED NOTIFICATION
            
            Leave ID: {leave_id}
            Leave Type: {leave_type}
            Start Date: {start_date}
            End Date: {end_date}
            Approved by: {approved_by}
            Timestamp: {datetime.now().isoformat()}
            
            ✅ Congratulations! Your leave has been approved.
            Your leave balance will be updated accordingly.
            """
            
            # Store notification
            self._store_notification(
                notification_type="LEAVE_APPROVED",
                recipient=employee_username,
                subject=subject,
                content=content,
                status="SENT"
            )
            
            logger.info(f"✅ Leave approval notification: {leave_id} → {employee_username}")
            
            # In production, implement actual sending:
            # await self._send_email(employee_username, subject, content)
            # await self._send_slack_message(employee_username, content)
            
        except Exception as e:
            logger.error(f"Error handling leave.approved: {str(e)}", exc_info=True)
            raise
        
    async def _handle_leave_rejected(self, payload: dict):
        """
        Handle leave.rejected event - notify employee with reason.
        """
        try:
            leave_id = payload.get("leave_id")
            employee_username = payload.get("employee_username")
            rejection_comment = payload.get("comment", "No reason provided")
            leave_type = payload.get("leave_type")
            
            subject = f"Leave Rejected - {leave_type}"
            content = f"""
            LEAVE REJECTED NOTIFICATION
            
            Leave ID: {leave_id}
            Leave Type: {leave_type}
            Rejection Reason: {rejection_comment}
            Timestamp: {datetime.now().isoformat()}
            
            ❌ Your leave application has been rejected.
            Please contact your manager for more information or
            consider reapplying for different dates.
            """
            
            # Store notification
            self._store_notification(
                notification_type="LEAVE_REJECTED",
                recipient=employee_username,
                subject=subject,
                content=content,
                status="SENT"
            )
            
            logger.info(f"❌ Leave rejection notification: {leave_id} → {employee_username}")
            
            # In production, implement actual sending:
            # await self._send_email(employee_username, subject, content)
            # await self._send_slack_message(employee_username, content)
            
        except Exception as e:
            logger.error(f"Error handling leave.rejected: {str(e)}", exc_info=True)
            raise

    async def close(self):
        """Gracefully close the consumer."""
        try:
            if self.connection:
                await self.connection.close()
                logger.info("Notification consumer closed")
        except Exception as e:
            logger.error(f"Error closing consumer: {str(e)}")
