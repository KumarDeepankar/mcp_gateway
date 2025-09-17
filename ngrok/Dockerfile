# Ngrok Dockerfile
# Custom ngrok container for MCP gateway tunneling

FROM ngrok/ngrok:latest

# Set working directory
WORKDIR /ngrok

# Expose ngrok web interface port
EXPOSE 4040

# Default command - will be overridden by docker-compose
CMD ["ngrok", "http", "8000", "--log=stdout"]