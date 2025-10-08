# Use Python 3.11 slim base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Build-time arguments - can be overridden during build
ARG MCP_GATEWAY_URL=http://localhost:8021
ARG AGENTIC_SEARCH_ORIGIN=http://localhost:8023
ARG HOST=0.0.0.0
ARG PORT=8023
ARG OLLAMA_HOST=http://localhost:11434
ARG OLLAMA_MODEL=llama3.2:latest
ARG LOG_LEVEL=INFO

# Set runtime environment variables from build args
ENV MCP_GATEWAY_URL=${MCP_GATEWAY_URL} \
    AGENTIC_SEARCH_ORIGIN=${AGENTIC_SEARCH_ORIGIN} \
    HOST=${HOST} \
    PORT=${PORT} \
    OLLAMA_HOST=${OLLAMA_HOST} \
    OLLAMA_MODEL=${OLLAMA_MODEL} \
    LOG_LEVEL=${LOG_LEVEL}

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Expose the port
EXPOSE 8023

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8023/health || exit 1

# Default command
CMD ["python", "server.py"]