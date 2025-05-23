import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional
from logging_loki import LokiHandler
import asyncio
import aiohttp
from logging.handlers import QueueHandler
import queue

# Try to import redis, but provide fallback for local testing
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("Redis package not available, using in-memory mock instead")

# Create a queue for async logging
log_queue = queue.Queue()

# Configure logging with Loki
logger = logging.getLogger("redis_helper")
logger.setLevel(logging.INFO)

# Add queue handler
queue_handler = QueueHandler(log_queue)
logger.addHandler(queue_handler)

async def send_log_to_loki(log_record):
    """Async function to send logs to Loki"""
    async with aiohttp.ClientSession() as session:
        try:
            log_data = {
                "streams": [{
                    "stream": {"application": "redis_helper"},
                    "values": [[str(int(datetime.now().timestamp() * 1e9)), log_record.getMessage()]]
                }]
            }
            async with session.post(
                "http://loki:3100/loki/api/v1/push",
                json=log_data
            ) as response:
                if response.status != 204:
                    print(f"Failed to send log to Loki: {await response.text()}")
        except Exception as e:
            print(f"Error sending log to Loki: {e}")

async def process_log_queue():
    """Process logs from queue and send to Loki"""
    while True:
        try:
            log_record = log_queue.get_nowait()
            await send_log_to_loki(log_record)
        except queue.Empty:
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Error processing log queue: {e}")
            await asyncio.sleep(1)

# Get Redis connection details from environment variables with defaults
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))


class InMemoryRedis:
    """Mock Redis implementation for local testing"""
    
    def __init__(self):
        self.data = {}
        
    async def hset(self, hash_name, key, value):
        """Emulates Redis HSET"""
        if hash_name not in self.data:
            self.data[hash_name] = {}
        self.data[hash_name][key] = value
        return 1
        
    async def hget(self, hash_name, key):
        """Emulates Redis HGET"""
        if hash_name not in self.data or key not in self.data[hash_name]:
            return None
        return self.data[hash_name][key]
        
    async def hgetall(self, hash_name):
        """Emulates Redis HGETALL"""
        if hash_name not in self.data:
            return {}
        return self.data[hash_name]


class RedisManager:
    """Helper class for Redis operations related to worker management"""
    
    def __init__(self):
        self.redis_pool = None
        self.use_mock = not REDIS_AVAILABLE
        self.log_task = None
        
    async def connect(self) -> bool:
        """Connect to Redis or initialize mock"""
        # Start log processing task
        if not self.log_task:
            self.log_task = asyncio.create_task(process_log_queue())
            
        if self.use_mock:
            self.redis_pool = InMemoryRedis()
            logger.info("Using in-memory mock for Redis")
            return True
            
        try:
            self.redis_pool = await redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            # Fall back to mock if Redis connection fails
            self.redis_pool = InMemoryRedis()
            self.use_mock = True
            logger.info("Falling back to in-memory mock for Redis")
            return True
            
    async def register_worker(self, worker_id: str, worker_data: Dict[str, Any]) -> bool:
        """Register a worker in Redis"""
        try:
            # Ensure last_heartbeat is set
            if "last_heartbeat" not in worker_data:
                worker_data["last_heartbeat"] = str(datetime.now())
                
            await self.redis_pool.hset("workers", worker_id, json.dumps(worker_data))
            logger.info(f"Registered worker: {worker_id}")
            return True
        except Exception as e:
            logger.error(f"Error registering worker: {e}")
            return False
            
    async def update_worker_heartbeat(self, worker_id: str, status: str = "alive") -> bool:
        """Update worker heartbeat timestamp and status"""
        try:
            worker_data = await self.redis_pool.hget("workers", worker_id)
            if worker_data:
                worker_info = json.loads(worker_data)
                worker_info["status"] = status
                worker_info["last_heartbeat"] = str(datetime.now())
                await self.redis_pool.hset("workers", worker_id, json.dumps(worker_info))
                logger.debug(f"Updated heartbeat for worker {worker_id}")
                return True
            else:
                logger.warning(f"Worker {worker_id} not found in Redis")
                return False
        except Exception as e:
            logger.error(f"Error updating worker heartbeat: {e}")
            return False
            
    async def update_worker_status(self, worker_id: str, status: str) -> bool:
        """Update worker status"""
        try:
            worker_data = await self.redis_pool.hget("workers", worker_id)
            if worker_data:
                worker_info = json.loads(worker_data)
                worker_info["status"] = status
                await self.redis_pool.hset("workers", worker_id, json.dumps(worker_info))
                logger.info(f"Updated status of worker {worker_id} to {status}")
                return True
            else:
                logger.warning(f"Worker {worker_id} not found in Redis when updating status")
                return False
        except Exception as e:
            logger.error(f"Error updating worker status: {e}")
            return False
            
    async def get_worker(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Get worker data from Redis"""
        try:
            worker_data = await self.redis_pool.hget("workers", worker_id)
            if worker_data:
                return json.loads(worker_data)
            return None
        except Exception as e:
            logger.error(f"Error getting worker: {e}")
            return None
            
    async def get_all_workers(self) -> Dict[str, Dict[str, Any]]:
        """Get all workers from Redis"""
        try:
            workers = await self.redis_pool.hgetall("workers")
            result = {}
            for worker_id, worker_data in workers.items():
                result[worker_id] = json.loads(worker_data)
            return result
        except Exception as e:
            logger.error(f"Error getting all workers: {e}")
            return {}
