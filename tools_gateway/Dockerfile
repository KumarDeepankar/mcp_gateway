# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    libldap2-dev \
    libsasl2-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY tools_gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (copying from project root)
# The tools_gateway/ directory already contains __init__.py and static/
COPY tools_gateway/ ./tools_gateway/

# Database will be created automatically on first run in /app directory

# Expose port
EXPOSE 8021

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8021/health || exit 1

# Run the application
CMD ["python", "-m", "tools_gateway.run"]
