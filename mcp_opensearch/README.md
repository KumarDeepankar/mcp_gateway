# MCP OpenSearch Server

MCP (Model Context Protocol) server for OpenSearch that uses HTTP requests instead of the OpenSearch Python library. This server is fully compliant with the MCP 2025-06-18 specification.

## Features

- **HTTP-based OpenSearch queries**: Uses `aiohttp` to make HTTP requests to OpenSearch REST API
- **Stories index support**: Pre-configured to work with the `stories` index
- **MCP 2025-06-18 compliant**: Implements Streamable HTTP transport with SSE
- **Four OpenSearch tools**:
  - `search_stories`: Search for stories using a query string
  - `get_story`: Retrieve a specific story by document ID
  - `list_stories`: List all stories with pagination
  - `count_stories`: Get the total count of stories

## Prerequisites

- Python 3.11+
- OpenSearch running at `http://localhost:9200` (or configure via environment variable)
- Stories index created in OpenSearch

## Installation

### Local Development

1. Install dependencies:
```bash
cd mcp_opensearch
pip install -r requirements.txt
```

2. Set environment variables (optional):
```bash
export OPENSEARCH_URL=http://localhost:9200
export PORT=8001
```

3. Run the server:
```bash
python mcp_server.py
```

### Docker

1. Build the Docker image:
```bash
docker build -t mcp-opensearch .
```

2. Run the container:
```bash
docker run -d \
  --name mcp-opensearch \
  -p 8001:8001 \
  -e OPENSEARCH_URL=http://host.docker.internal:9200 \
  -e DOCKER_CONTAINER=true \
  mcp-opensearch
```

## Environment Variables

- `OPENSEARCH_URL`: OpenSearch endpoint URL (default: `http://localhost:9200`)
- `PORT`: Server port (default: `8001`)
- `DOCKER_CONTAINER`: Set to `true` when running in Docker (default: `false`)

## API Endpoints

### Health Check
```bash
GET /health
```

Returns server health status and configuration.

### MCP Endpoints
- `GET /mcp`: Server-initiated SSE stream
- `POST /mcp`: Client-to-server communication (JSON-RPC)
- `DELETE /mcp`: Session termination

## Available Tools

### 1. search_stories
Search for stories using a query string.

**Parameters:**
- `query` (string, required): Search query text
- `size` (integer, optional): Number of results to return (default: 10, max: 100)

**Example:**
```json
{
  "name": "search_stories",
  "arguments": {
    "query": "adventure",
    "size": 5
  }
}
```

### 2. get_story
Retrieve a specific story by its document ID.

**Parameters:**
- `story_id` (string, required): The document ID of the story

**Example:**
```json
{
  "name": "get_story",
  "arguments": {
    "story_id": "story-123"
  }
}
```

### 3. list_stories
List all stories with pagination.

**Parameters:**
- `size` (integer, optional): Number of stories to return (default: 10, max: 100)
- `from` (integer, optional): Offset for pagination (default: 0)

**Example:**
```json
{
  "name": "list_stories",
  "arguments": {
    "size": 20,
    "from": 0
  }
}
```

### 4. count_stories
Get the total count of stories in the index.

**Parameters:** None

**Example:**
```json
{
  "name": "count_stories",
  "arguments": {}
}
```

## Testing

### Test the server is running:
```bash
curl http://localhost:8001/health
```

### Test MCP initialization:
```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-06-18",
      "capabilities": {},
      "clientInfo": {
        "name": "test-client",
        "version": "1.0.0"
      }
    }
  }'
```

### List available tools:
```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
  }'
```

### Search stories:
```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "search_stories",
      "arguments": {
        "query": "adventure",
        "size": 5
      }
    }
  }'
```

## Architecture

The server follows the same architecture as `mcp_server_1`:

- **mcp_server.py**: Main FastAPI application with MCP protocol implementation
- **tools.py**: OpenSearch tool definitions and HTTP-based handlers
- **EventStore**: Manages SSE event storage for resumability
- **StreamManager**: Manages active SSE streams
- **MessageRouter**: Routes messages to specific streams

## License

See repository root for license information.
