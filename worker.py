import asyncio
import json
import logging
import uuid
import os
import random
from datetime import datetime
import websockets
import uvicorn
import httpx
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import socket
from logging_loki import LokiHandler

# Import Redis helper if needed (not used in worker yet but prepared for future use)
from redis_helper import RedisManager

# Configure logging with Loki
logger = logging.getLogger("worker")
logger.setLevel(logging.INFO)

# Add Loki handler
loki_handler = LokiHandler(
    url="http://loki:3100/loki/api/v1/push",
    tags={"application": "worker"},
    version="1",
)
logger.addHandler(loki_handler)

# Configuration from environment variables
WORKER_NAME = os.getenv("WORKER_NAME", f"Worker-{random.randint(1, 1000)}")
WORKER_PORT = int(os.getenv("WORKER_PORT", 8001))
MANAGER_HOST = os.getenv("MANAGER_HOST", "localhost")
MANAGER_PORT = int(os.getenv("MANAGER_PORT", 8000))
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", 5))  # seconds

# Create unique worker ID
WORKER_ID = str(uuid.uuid4())

app = FastAPI(title=f"FastAPI {WORKER_NAME}")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
websocket_task = None
heartbeat_running = False


def get_host_ip():
    """Get the host IP address"""
    try:
        # Get host name 
        host_name = socket.gethostname()
        # Get the corresponding IP
        host_ip = socket.gethostbyname(host_name)
        return host_ip
    except:
        return "127.0.0.1"


async def register_with_manager():
    """Register this worker with the manager service"""
    try:
        host_ip = get_host_ip()
        worker_data = {
            "worker_id": WORKER_ID,
            "worker_name": WORKER_NAME,
            "host": host_ip,
            "port": WORKER_PORT,
            "status": "registering"
        }
        
        async with httpx.AsyncClient() as client:
            url = f"http://{MANAGER_HOST}:{MANAGER_PORT}/register"
            response = await client.post(url, json=worker_data)
            
            if response.status_code == 200:
                logger.info(f"Successfully registered with manager: {response.json()}")
                return True
            else:
                logger.error(f"Failed to register with manager: {response.text}")
                return False
    except Exception as e:
        logger.error(f"Error registering with manager: {e}")
        return False


async def send_heartbeats():
    """Send heartbeats to manager via WebSocket"""
    global heartbeat_running
    
    try:
        heartbeat_running = True
        uri = f"ws://{MANAGER_HOST}:{MANAGER_PORT}/ws/{WORKER_ID}"
        
        logger.info(f"Connecting to WebSocket at {uri}")
        
        async with websockets.connect(uri) as websocket:
            logger.info("WebSocket connection established")
            
            while heartbeat_running:
                # Create heartbeat data
                heartbeat_data = {
                    "timestamp": str(datetime.now()),
                    "worker_id": WORKER_ID,
                    "worker_name": WORKER_NAME,
                    "status": "alive",
                    "metrics": {
                        "cpu": random.randint(0, 100),  # Simulate some metrics
                        "memory": random.randint(100, 500),
                    }
                }
                
                # Send heartbeat
                await websocket.send(json.dumps(heartbeat_data))
                logger.debug(f"Heartbeat sent: {heartbeat_data}")
                
                # Wait for next heartbeat
                await asyncio.sleep(HEARTBEAT_INTERVAL)
    except Exception as e:
        logger.error(f"Error in heartbeat WebSocket connection: {e}")
        heartbeat_running = False
        
        # Try to reconnect after a delay
        await asyncio.sleep(5)
        # Restart heartbeat task
        start_heartbeat_task()


def start_heartbeat_task():
    """Start the heartbeat background task"""
    global websocket_task
    
    if websocket_task and not websocket_task.done():
        # Cancel existing task
        websocket_task.cancel()
        
    # Create new task
    websocket_task = asyncio.create_task(send_heartbeats())
    logger.info("Heartbeat task started")


@app.on_event("startup")
async def startup_event():
    """Register with manager and start sending heartbeats on startup"""
    # First register
    registered = await register_with_manager()
    
    if registered:
        # Then start heartbeats
        start_heartbeat_task()


@app.on_event("shutdown")
async def shutdown_event():
    """Stop heartbeats on shutdown"""
    global heartbeat_running, websocket_task
    
    heartbeat_running = False
    
    if websocket_task and not websocket_task.done():
        websocket_task.cancel()
        
    logger.info("Heartbeat task stopped")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": f"FastAPI {WORKER_NAME}",
        "worker_id": WORKER_ID,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "worker_id": WORKER_ID, "worker_name": WORKER_NAME}


if __name__ == "__main__":
    uvicorn.run(
        "worker:app",
        host="0.0.0.0",
        port=WORKER_PORT,
        reload=True
    )
