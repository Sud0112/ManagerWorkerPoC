# FastAPI Heartbeat Monitoring System

This system allows for monitoring multiple FastAPI applications through WebSocket heartbeats. It consists of a manager service that monitors worker applications and detects if any of them go down or stop sending heartbeats.

## System Components

1. **Manager**: Central service that listens for heartbeats and monitors worker status
2. **Workers**: FastAPI applications that register with the manager and send periodic heartbeats
3. **Redis**: Used for storing worker registration information and status
4. **Loki**: Centralized logging system for all components

## Features

- WebSocket-based async heartbeat system
- Automatic worker registration
- Redis for persistent worker information
- Docker setup for easy deployment
- Health status monitoring with configurable timeout
- Centralized logging with Loki
- Async logging to prevent blocking operations

## Architecture

The system follows this architecture:
- Workers register with the manager upon startup
- Each worker establishes a WebSocket connection to the manager
- Workers send periodic heartbeats through the WebSocket connection
- Manager processes heartbeats and updates worker status in Redis
- Manager periodically checks worker status and marks workers as "not_responding" if heartbeats stop
- All components send logs to Loki for centralized logging

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
- 1 Loki instance for logging
- 1 Manager service
- 2 Worker instances

### Manual Setup

If you want to run the components manually:

1. Start Redis:
```bash
redis-server
```

2. Start Loki:
```bash
docker run -p 3101:3100 grafana/loki:2.9.0
```

3. Start the manager:
```bash
uvicorn manager:app --host 0.0.0.0 --port 8000
```

4. Start one or more workers (on different ports):
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

### Loki Logging

The system uses Loki for centralized logging with the following features:

- Async logging to prevent blocking operations
- Queue-based log buffering
- Component-specific tags for easy filtering
- Centralized log storage and querying
- Access logs at `http://localhost:3101`

Example Loki queries:
- `{application="manager"}` - View manager logs
- `{application="worker"}` - View worker logs
- `{application="redis_helper"}` - View Redis helper logs

### Monitoring

Current monitoring options:

1. **API Endpoint**: The manager provides a `/workers` endpoint that returns real-time status of all registered workers
2. **Container Health**: Docker health checks are configured for Redis
3. **Loki Logs**: Centralized logging with queryable interface

### Future Extensions

The system is designed to be extended with more advanced monitoring:

- **Grafana Integration**: Add Grafana for visualizing Loki logs
- **Alerting**: Integration with alert managers for notification when workers go down
- **Dashboard**: A simple web UI could be added to visualize worker status
