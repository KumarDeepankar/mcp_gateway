# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libldap2-dev \
    libsasl2-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY static/ ./static/
COPY run.py .

# Copy database file (if exists)
COPY tools_gateway.db* ./

# Expose port
EXPOSE 8021

# Set environment variables
ENV HOST=0.0.0.0
ENV PORT=8021
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "run.py"]
