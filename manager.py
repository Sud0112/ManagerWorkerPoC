import asyncio
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
import uvicorn
import os

# Import Redis helper
from redis_helper import RedisManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("manager")

# Environment variables
HEARTBEAT_TIMEOUT = int(os.getenv("HEARTBEAT_TIMEOUT", 15))  # seconds

app = FastAPI(title="FastAPI Workers Manager")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class WorkerInfo(BaseModel):
    worker_id: str
    worker_name: str
    host: str
    port: int
    status: str = "registered"
    last_heartbeat: str = None


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.redis = RedisManager()
        self.worker_status_task = None
    
    async def connect_redis(self):
        """Connect to Redis"""
        return await self.redis.connect()
            
    async def connect(self, websocket: WebSocket, worker_id: str):
        """Connect a worker via WebSocket"""
        await websocket.accept()
        self.active_connections[worker_id] = websocket
        logger.info(f"Worker {worker_id} connected")
        
    async def disconnect(self, worker_id: str):
        """Handle worker disconnect"""
        if worker_id in self.active_connections:
            del self.active_connections[worker_id]
            logger.info(f"Worker {worker_id} disconnected")
            await self.update_worker_status(worker_id, "disconnected")
            
    async def update_worker_status(self, worker_id: str, status: str):
        """Update worker status in Redis"""
        await self.redis.update_worker_status(worker_id, status)
            
    async def process_heartbeat(self, worker_id: str, data: dict):
        """Process a heartbeat from a worker"""
        await self.redis.update_worker_heartbeat(worker_id, "alive")
            
    async def check_worker_status(self):
        """Periodic task to check worker status"""
        while True:
            try:
                workers = await self.redis.get_all_workers()
                current_time = datetime.now()
                
                for worker_id, worker_info in workers.items():
                    # Skip already disconnected workers
                    if worker_info["status"] == "disconnected":
                        continue
                        
                    # Check last heartbeat time
                    if worker_info["last_heartbeat"]:
                        last_heartbeat = datetime.fromisoformat(worker_info["last_heartbeat"])
                        time_diff = (current_time - last_heartbeat).total_seconds()
                        
                        if time_diff > HEARTBEAT_TIMEOUT:
                            logger.warning(f"Worker {worker_id} ({worker_info['worker_name']}) is not responding. Last heartbeat: {last_heartbeat}")
                            await self.redis.update_worker_status(worker_id, "not_responding")
            except Exception as e:
                logger.error(f"Error checking worker status: {e}")
                
            await asyncio.sleep(5)  # Check every 5 seconds
            
    async def start_monitoring(self):
        """Start the background task for monitoring workers"""
        if not self.worker_status_task:
            self.worker_status_task = asyncio.create_task(self.check_worker_status())
            logger.info("Worker status monitoring started")


# Create manager instance
manager = ConnectionManager()


@app.on_event("startup")
async def startup_event():
    """Connect to Redis on startup"""
    redis_connected = await manager.connect_redis()
    if redis_connected:
        await manager.start_monitoring()


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "FastAPI Workers Manager"}


@app.get("/workers")
async def get_workers():
    """Get all registered workers"""
    try:
        result = await manager.redis.get_all_workers()
        return result
    except Exception as e:
        logger.error(f"Error getting workers: {e}")
        return {"error": str(e)}


@app.post("/register")
async def register_worker(worker: WorkerInfo):
    """Register a new worker"""
    try:
        worker_dict = worker.model_dump()
        worker_dict["last_heartbeat"] = str(datetime.now())
        
        success = await manager.redis.register_worker(worker.worker_id, worker_dict)
        if success:
            logger.info(f"Registered new worker: {worker.worker_id} ({worker.worker_name})")
            return {"status": "success", "worker_id": worker.worker_id}
        else:
            return {"status": "error", "error": "Failed to register worker"}
    except Exception as e:
        logger.error(f"Error registering worker: {e}")
        return {"status": "error", "error": str(e)}


@app.websocket("/ws/{worker_id}")
async def websocket_endpoint(websocket: WebSocket, worker_id: str):
    """WebSocket endpoint for worker heartbeats"""
    await manager.connect(websocket, worker_id)
    try:
        # First update status to connected
        await manager.update_worker_status(worker_id, "connected")
        
        # Handle heartbeats
        while True:
            data = await websocket.receive_json()
            await manager.process_heartbeat(worker_id, data)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for worker {worker_id}")
        await manager.disconnect(worker_id)
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")
        await manager.disconnect(worker_id)


if __name__ == "__main__":
    uvicorn.run(
        "manager:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
