FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Command will be specified in docker-compose.yml
# This Dockerfile can be used for both manager and worker services
