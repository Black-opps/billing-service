"""
Kafka consumer for usage events.
"""
import asyncio
from aiokafka import AIOKafkaConsumer
import json
import logging
from typing import Dict

from ..services.metering import UsageMeteringService
from ..core.database import SessionLocal
from ..core.config import settings

logger = logging.getLogger(__name__)


class UsageEventConsumer:
    """Kafka consumer for usage events."""
    
    def __init__(self):
        self.consumer = AIOKafkaConsumer(
            settings.KAFKA_USAGE_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id="billing-usage-group",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=False,
            max_poll_records=100
        )
        
        self.running = False
        self.batch_size = 50
    
    async def start(self):
        """Start the consumer."""
        await self.consumer.start()
        self.running = True
        
        logger.info(f"Usage consumer started, listening to {settings.KAFKA_USAGE_TOPIC}")
        
        try:
            await self.consume_loop()
        finally:
            await self.consumer.stop()
    
    async def stop(self):
        """Stop the consumer."""
        self.running = False
    
    async def consume_loop(self):
        """Main consume loop."""
        batch = []
        
        async for msg in self.consumer:
            if not self.running:
                break
            
            try:
                # Process message
                batch.append(msg)
                
                if len(batch) >= self.batch_size:
                    await self.process_batch(batch)
                    await self.consumer.commit()
                    batch = []
                    
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                # Handle error - possibly send to DLQ
        
        # Process remaining
        if batch:
            await self.process_batch(batch)
            await self.consumer.commit()
    
    async def process_batch(self, messages):
        """Process a batch of usage events."""
        # Create database session
        db = SessionLocal()
        
        try:
            metering = UsageMeteringService(db)
            
            for msg in messages:
                await self.process_single_message(msg.value, metering)
            
            db.commit()
            logger.info(f"Processed batch of {len(messages)} usage events")
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            db.rollback()
            raise
        finally:
            db.close()
    
    async def process_single_message(self, data: Dict, metering: UsageMeteringService):
        """Process a single usage event."""
        try:
            await metering.track_usage(
                tenant_id=data["tenant_id"],
                metric_name=data["metric"],
                quantity=data.get("quantity", 1),
                service=data.get("service", "unknown"),
                metadata=data.get("metadata", {}),
                idempotency_key=data.get("idempotency_key")
            )
            
            logger.debug(f"Tracked usage: {data}")
            
        except Exception as e:
            logger.error(f"Failed to track usage: {e}")
            raise


async def run_consumer():
    """Run the consumer."""
    consumer = UsageEventConsumer()
    await consumer.start()


if __name__ == "__main__":
    asyncio.run(run_consumer())