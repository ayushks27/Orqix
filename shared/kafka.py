import json
import logging
import threading
from typing import Callable, Dict, Any
from shared.config import settings

logger = logging.getLogger("orqix.shared.kafka")

# Try to import kafka libraries, fallback if not available
try:
    from kafka import KafkaProducer, KafkaConsumer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

# Fallback using redis for internal pub/sub if kafka isn't running or import fails
import redis

class EventBroker:
    def __init__(self):
        self.use_kafka = KAFKA_AVAILABLE
        self.producer = None
        self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.subscribers = {}
        
        if self.use_kafka:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    request_timeout_ms=5000,
                    retries=3
                )
                logger.info("Kafka producer successfully initialized.")
            except Exception as e:
                logger.warning(f"Could not connect to Kafka bootstrap server: {e}. Falling back to Redis PubSub.")
                self.use_kafka = False

    def publish(self, topic: str, event_type: str, data: Dict[str, Any]):
        message = {
            "event_type": event_type,
            "data": data
        }
        
        if self.use_kafka and self.producer:
            try:
                self.producer.send(topic, message)
                self.producer.flush()
                logger.info(f"Published event {event_type} to Kafka topic {topic}")
                return
            except Exception as e:
                logger.error(f"Kafka publish failed: {e}. Attempting Redis fallback.")
        
        # Redis Fallback
        try:
            self.redis_client.publish(topic, json.dumps(message))
            logger.info(f"Published event {event_type} to Redis channel {topic}")
        except Exception as re:
            logger.critical(f"Redis and Kafka both failed to publish event: {re}")

    def subscribe(self, topic: str, event_type: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Register a consumer listener for a topic/event combination.
        """
        if topic not in self.subscribers:
            self.subscribers[topic] = {}
        if event_type not in self.subscribers[topic]:
            self.subscribers[topic][event_type] = []
        
        self.subscribers[topic][event_type].append(callback)
        logger.info(f"Subscribed callback to {topic}::{event_type}")

    def start_consumer_loop(self, topic: str):
        """
        Runs a background thread listening to events and routing them to subscribers.
        """
        thread = threading.Thread(target=self._run_consumer, args=(topic,), daemon=True)
        thread.start()
        logger.info(f"Started background event consumer for {topic}")

    def _run_consumer(self, topic: str):
        if self.use_kafka:
            try:
                consumer = KafkaConsumer(
                    topic,
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    auto_offset_reset='latest',
                    enable_auto_commit=True,
                    group_id=f"orqix-consumer-{topic}"
                )
                for message in consumer:
                    event = message.value
                    self._dispatch_event(topic, event)
                return
            except Exception as e:
                logger.warning(f"Kafka consumer error: {e}. Falling back to Redis channel subscribe.")
        
        # Redis Fallback Consumer
        try:
            pubsub = self.redis_client.pubsub()
            pubsub.subscribe(topic)
            for raw_message in pubsub.listen():
                if raw_message['type'] == 'message':
                    event = json.loads(raw_message['data'])
                    self._dispatch_event(topic, event)
        except Exception as e:
            logger.critical(f"Redis subscription runner failed for {topic}: {e}")

    def _dispatch_event(self, topic: str, event: Dict[str, Any]):
        event_type = event.get("event_type")
        data = event.get("data", {})
        if topic in self.subscribers and event_type in self.subscribers[topic]:
            for callback in self.subscribers[topic][event_type]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Error executing event callback for {event_type}: {e}")

event_broker = EventBroker()
