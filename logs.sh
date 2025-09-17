#!/bin/bash

# View MCP Gateway Service Logs

echo "📋 MCP Gateway Service Logs"
echo "==========================="
echo ""

if [ "$1" = "" ]; then
    echo "Select a service to view logs:"
    echo "1. All services"
    echo "2. MCP Server"
    echo "3. Ngrok"
    echo "4. Registry Discovery"
    echo ""
    read -p "Enter choice (1-4): " choice

    case $choice in
        1) docker-compose logs -f ;;
        2) docker-compose logs -f mcp-server ;;
        3) docker-compose logs -f ngrok ;;
        4) docker-compose logs -f mcp-registry-discovery ;;
        *) echo "Invalid choice" ;;
    esac
else
    case $1 in
        "all") docker-compose logs -f ;;
        "mcp") docker-compose logs -f mcp-server ;;
        "ngrok") docker-compose logs -f ngrok ;;
        "registry") docker-compose logs -f mcp-registry-discovery ;;
        *) echo "Usage: ./logs.sh [all|mcp|ngrok|registry]" ;;
    esac
fi