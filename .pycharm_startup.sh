#!/bin/bash
# PyCharm Gateway Startup Script
# This script cleans cache and starts the gateway with proper environment

echo "🧹 Cleaning Python bytecode cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
find . -name "*.pyo" -delete 2>/dev/null

echo "🚀 Starting Tools Gateway..."
export PYTHONDONTWRITEBYTECODE=1
export PORT=8021
exec python tools_gateway/run.py
