# FastAPI Heartbeat Monitoring System

This system allows for monitoring multiple FastAPI applications through WebSocket heartbeats. It consists of a manager service that monitors worker applications and detects if any of them go down or stop sending heartbeats.

## System Components

1. **Manager**: Central service that listens for heartbeats and monitors worker status
2. **Workers**: FastAPI applications that register with the manager and send periodic heartbeats
3. **Redis**: Used for storing worker registration information and status

## Features

- WebSocket-based async heartbeat system
- Automatic worker registration
- Redis for persistent worker information
- Docker setup for easy deployment
- Health status monitoring with configurable timeout

## Architecture

The system follows this architecture:
- Workers register with the manager upon startup
- Each worker establishes a WebSocket connection to the manager
- Workers send periodic heartbeats through the WebSocket connection
- Manager processes heartbeats and updates worker status in Redis
- Manager periodically checks worker status and marks workers as "not_responding" if heartbeats stop

### Redis Data Structure

Worker status information is stored in Redis using a Hash data structure:
- A single Redis Hash named `workers` contains all worker data
- Each worker's ID is used as a field in the hash
- The value for each field is a JSON string containing worker details including:
  - Worker ID and name
  - Host and port
  - Current status (registered, connected, alive, not_responding, disconnected)
  - Last heartbeat timestamp
- This structure enables efficient storage and quick retrieval of worker information

## Running the System

### Using Docker Compose

The easiest way to run the entire system is with Docker Compose:

```bash
docker-compose up
```

This will start:
- 1 Redis instance
- 1 Manager service
- 4 Worker instances

### Manual Setup

If you want to run the components manually:

1. Start Redis:
```bash
redis-server
```

2. Start the manager:
```bash
uvicorn manager:app --host 0.0.0.0 --port 8000
```

3. Start one or more workers (on different ports):
```bash
WORKER_NAME="Worker 1" WORKER_PORT=8001 uvicorn worker:app --host 0.0.0.0 --port 8001
```

## Configuration

The system is configurable through environment variables:

### Manager
- `REDIS_HOST`: Redis host (default: "localhost")
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_DB`: Redis database number (default: 0)
- `HEARTBEAT_TIMEOUT`: Time in seconds after which a worker is considered down (default: 15)

### Worker
- `WORKER_NAME`: Name of the worker (default: random name)
- `WORKER_PORT`: Port for the worker's FastAPI app (default: 8001)
- `MANAGER_HOST`: Host of the manager service (default: "localhost")
- `MANAGER_PORT`: Port of the manager service (default: 8000)
- `HEARTBEAT_INTERVAL`: Time in seconds between heartbeats (default: 5)

## API Endpoints

### Manager
- `GET /workers`: List all registered workers and their status
- `POST /register`: Register a new worker
- `WebSocket /ws/{worker_id}`: WebSocket endpoint for worker heartbeats

### Worker
- `GET /health`: Health check endpoint

## Simulating Worker Failure

To simulate a worker failure, you can stop one of the worker containers:

```bash
docker-compose stop worker2
```

After the heartbeat timeout period (default 15 seconds), the manager will mark the worker as "not_responding".

## Logging and Monitoring

### Current Logging

The system uses Python's built-in logging module with the following features:

- Configurable log levels (default: INFO)
- Timestamp and component identification in log entries
- Different loggers for manager and worker components
- Structured logging of important events:
  - Worker registration/disconnection
  - WebSocket connection status
  - Heartbeat processing
  - Worker status changes

When running in Docker, logs are directed to stdout/stderr and can be viewed with:
```bash
docker-compose logs -f manager  # View manager logs
docker-compose logs -f worker1   # View worker1 logs
```

### Monitoring

Current monitoring options:

1. **API Endpoint**: The manager provides a `/workers` endpoint that returns real-time status of all registered workers
2. **Container Health**: Docker health checks are configured for Redis

### Future Extensions

The system is designed to be extended with more advanced monitoring:

- **Prometheus Integration**: Metrics endpoints could be added to expose:
  - Worker registration counts
  - Heartbeat latency
  - Worker uptime statistics
  - Status change events

- **Alerting**: Integration with alert managers for notification when workers go down

- **Dashboard**: A simple web UI could be added to visualize worker status
