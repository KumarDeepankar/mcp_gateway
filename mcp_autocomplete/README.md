# MCP Fuzzy Autocomplete Server (FastMCP 2.0)

Simple, fast fuzzy autocomplete server using FastMCP 2.0.

## Features

- **2 Tools**: `fuzzy_autocomplete`, `validate_entity`
- **Auto Query Detection**: Numeric vs Text queries
- **Fuzzy Matching**: Handles typos, partial inputs
- **FastMCP 2.0**: Simple, standards-compliant

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Start Server (SSE Transport)

```bash
python server.py
```

### Start Server (Stdio Transport)

```bash
python server.py stdio
```

## Configuration

Environment variables:
- `OPENSEARCH_URL`: OpenSearch URL (default: `http://localhost:9200`)
- `INDEX_NAME`: Index name (default: `events`)

## Tools

### 1. fuzzy_autocomplete

```python
{
    "query": "climate",  # Search query
    "size": 10           # Number of results (1-50)
}
```

**Returns:**
```json
{
    "query": "climate",
    "query_type": "text",
    "total_matches": 12,
    "count": 10,
    "suggestions": [
        {
            "rank": 1,
            "id": "evt_123",
            "title": "Climate Summit 2023",
            "subtitle": "Denmark · 2023 · 500 attendees",
            "theme": "Environmental Policy",
            "score": 71.56,
            "highlight": "<mark>Climate</mark> Summit 2023"
        }
    ]
}
```

### 2. validate_entity

```python
{
    "entity_id": "evt_123"  # Entity ID to validate
}
```

**Returns:**
```json
{
    "exists": true,
    "entity_id": "evt_123",
    "entity": {
        "id": "evt_123",
        "title": "Climate Summit 2023",
        "country": "Denmark",
        "year": "2023",
        "theme": "Environmental Policy",
        "attendance": 500
    }
}
```

## Query Types

| Query | Type | Strategy |
|-------|------|----------|
| `2022` | numeric | Year exact match, ID wildcard |
| `climate` | text | Phrase match, fuzzy match |
| `tech` | text | Prefix + fuzzy |

## Testing

```bash
# Using MCP CLI (if installed)
mcp call server.py fuzzy_autocomplete '{"query": "climate", "size": 5}'

# Or test with Python client
python -c "
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test():
    server_params = StdioServerParameters(
        command='python',
        args=['server.py', 'stdio']
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                'fuzzy_autocomplete',
                arguments={'query': 'climate', 'size': 5}
            )
            print(result)

asyncio.run(test())
"
```

## Integration with Tools Gateway

Register in your MCP gateway:

```python
# Add to gateway registry
autocomplete_server = {
    "type": "stdio",
    "command": "python",
    "args": ["mcp_autocomplete/server.py", "stdio"]
}
```

## Performance

- Simple, single-file implementation
- ~150 lines of code
- <50ms response time
- Minimal dependencies

## License

MIT
