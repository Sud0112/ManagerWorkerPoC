# Build stage
FROM python:3.10-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.10-slim

# Add metadata labels
LABEL maintainer="Your Name <your.email@example.com>"
LABEL description="Manager/Worker Service"
LABEL version="1.0"

WORKDIR /app

# Copy only necessary files from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages/ /usr/local/lib/python3.10/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy only Python files
COPY *.py .

# Create start script
RUN echo '#!/bin/bash\n\
uvicorn manager:app --host 0.0.0.0 --port 8000 & \
uvicorn worker:app --host 0.0.0.0 --port 8001 & \
wait' > /app/start.sh && \
chmod +x /app/start.sh

# Expose ports
EXPOSE 8000
EXPOSE 8001

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start both services
CMD ["/app/start.sh"]
