# MCP Toolbox Dockerfile
# Production-ready container for MCP 2025-06-18 compliant proxy gateway

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY main.py .
COPY services.py .
COPY mcp_storage.py .
COPY config.py .
COPY test_mcp.html .
COPY static/ ./static/

# Create directory for persistent storage
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONPATH=/app
ENV HOST=0.0.0.0
ENV PORT=8021

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8021/ || exit 1

# Expose port
EXPOSE 8021

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash mcp && \
    chown -R mcp:mcp /app
USER mcp

# Run the application
CMD ["python", "main.py"]