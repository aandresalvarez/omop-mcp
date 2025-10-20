# Generic MCP Client Integration Guide

This guide provides instructions for integrating the OMOP MCP server with any MCP-compatible client, including custom applications and other AI frameworks.

## Prerequisites

- **MCP-compatible client** (e.g., custom Python app, Node.js client, etc.)
- **Python 3.11+** installed
- **OMOP CDM database** access
- **OpenAI API key** (for AI agents)

## MCP Protocol Overview

The OMOP MCP server implements the Model Context Protocol (MCP) specification, providing:

- **Tools**: Executable functions for OMOP operations
- **Resources**: Cacheable data endpoints
- **Prompts**: Reusable prompt templates
- **Transports**: stdio and HTTP modes

## Server Modes

### stdio Mode (Recommended)

Direct process communication via standard input/output:

```bash
# Start server in stdio mode
uv run python -m omop_mcp.server --stdio

# Server communicates via JSON-RPC over stdin/stdout
```

### HTTP Mode

REST API with Server-Sent Events (SSE):

```bash
# Start server in HTTP mode
uv run python -m omop_mcp.server --http --port 8000

# Available endpoints:
# - http://localhost:8000/tools
# - http://localhost:8000/resources
# - http://localhost:8000/prompts
# - http://localhost:8000/sse (SSE endpoint)
```

## Client Implementation Examples

### Python Client (stdio)

```python
import asyncio
import json
import subprocess
from typing import Any, Dict

class OMOPMCPClient:
    def __init__(self, server_path: str = "uv run python -m omop_mcp.server --stdio"):
        self.server_path = server_path
        self.process = None

    async def start(self):
        """Start the MCP server process."""
        self.process = await asyncio.create_subprocess_exec(
            *self.server_path.split(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Initialize MCP connection
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "omop-mcp-client",
                    "version": "1.0.0"
                }
            }
        }

        await self._send_request(init_request)

    async def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request to the server."""
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()

        response_line = await self.process.stdout.readline()
        response = json.loads(response_line.decode())
        return response

    async def discover_concepts(
        self,
        clinical_text: str,
        domain: str = None,
        vocabulary: str = None,
        standard_only: bool = True,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Discover OMOP concepts."""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "discover_concepts",
                "arguments": {
                    "clinical_text": clinical_text,
                    "domain": domain,
                    "vocabulary": vocabulary,
                    "standard_only": standard_only,
                    "limit": limit
                }
            }
        }

        response = await self._send_request(request)
        return response.get("result", {})

    async def query_omop(
        self,
        query_type: str,
        concept_ids: list[int],
        domain: str = "Condition",
        backend: str = "bigquery",
        execute: bool = True,
        limit: int = 1000
    ) -> Dict[str, Any]:
        """Execute OMOP analytical query."""
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "query_omop",
                "arguments": {
                    "query_type": query_type,
                    "concept_ids": concept_ids,
                    "domain": domain,
                    "backend": backend,
                    "execute": execute,
                    "limit": limit
                }
            }
        }

        response = await self._send_request(request)
        return response.get("result", {})

    async def get_information_schema(
        self,
        table_name: str = None,
        backend: str = "bigquery"
    ) -> Dict[str, Any]:
        """Get database schema information."""
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "get_information_schema",
                "arguments": {
                    "table_name": table_name,
                    "backend": backend
                }
            }
        }

        response = await self._send_request(request)
        return response.get("result", {})

    async def select_query(
        self,
        sql: str,
        validate: bool = True,
        execute: bool = True,
        backend: str = "bigquery",
        limit: int = 1000
    ) -> Dict[str, Any]:
        """Execute direct SQL query."""
        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "select_query",
                "arguments": {
                    "sql": sql,
                    "validate": validate,
                    "execute": execute,
                    "backend": backend,
                    "limit": limit
                }
            }
        }

        response = await self._send_request(request)
        return response.get("result", {})

    async def stop(self):
        """Stop the MCP server process."""
        if self.process:
            self.process.terminate()
            await self.process.wait()

# Usage example
async def main():
    client = OMOPMCPClient()

    try:
        await client.start()

        # Discover diabetes concepts
        concepts = await client.discover_concepts("diabetes", domain="Condition")
        print(f"Found {len(concepts['concepts'])} diabetes concepts")

        # Query patient counts
        concept_ids = [c['concept_id'] for c in concepts['concepts'][:5]]
        result = await client.query_omop("count", concept_ids, execute=True)
        print(f"Patient count: {result['results'][0]['patient_count']}")

    finally:
        await client.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### Python Client (HTTP)

```python
import asyncio
import aiohttp
import json
from typing import Any, Dict

class OMOPMCPHTTPClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None

    async def start(self):
        """Initialize HTTP session."""
        self.session = aiohttp.ClientSession()

    async def discover_concepts(
        self,
        clinical_text: str,
        domain: str = None,
        vocabulary: str = None,
        standard_only: bool = True,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Discover OMOP concepts via HTTP."""
        payload = {
            "name": "discover_concepts",
            "arguments": {
                "clinical_text": clinical_text,
                "domain": domain,
                "vocabulary": vocabulary,
                "standard_only": standard_only,
                "limit": limit
            }
        }

        async with self.session.post(
            f"{self.base_url}/tools/discover_concepts",
            json=payload
        ) as response:
            return await response.json()

    async def query_omop(
        self,
        query_type: str,
        concept_ids: list[int],
        domain: str = "Condition",
        backend: str = "bigquery",
        execute: bool = True,
        limit: int = 1000
    ) -> Dict[str, Any]:
        """Execute OMOP query via HTTP."""
        payload = {
            "name": "query_omop",
            "arguments": {
                "query_type": query_type,
                "concept_ids": concept_ids,
                "domain": domain,
                "backend": backend,
                "execute": execute,
                "limit": limit
            }
        }

        async with self.session.post(
            f"{self.base_url}/tools/query_omop",
            json=payload
        ) as response:
            return await response.json()

    async def stop(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()

# Usage example
async def main():
    client = OMOPMCPHTTPClient()

    try:
        await client.start()

        # Discover concepts
        concepts = await client.discover_concepts("hypertension")
        print(f"Found {len(concepts['concepts'])} hypertension concepts")

        # Query database
        concept_ids = [c['concept_id'] for c in concepts['concepts'][:3]]
        result = await client.query_omop("count", concept_ids, execute=True)
        print(f"Patient count: {result['results'][0]['patient_count']}")

    finally:
        await client.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### Node.js Client

```javascript
const { spawn } = require('child_process');
const readline = require('readline');

class OMOPMCPClient {
    constructor(serverPath = 'uv run python -m omop_mcp.server --stdio') {
        this.serverPath = serverPath.split(' ');
        this.process = null;
        this.requestId = 1;
    }

    async start() {
        return new Promise((resolve, reject) => {
            this.process = spawn(this.serverPath[0], this.serverPath.slice(1), {
                stdio: ['pipe', 'pipe', 'pipe']
            });

            this.rl = readline.createInterface({
                input: this.process.stdout,
                output: null
            });

            // Initialize MCP connection
            const initRequest = {
                jsonrpc: "2.0",
                id: this.requestId++,
                method: "initialize",
                params: {
                    protocolVersion: "2024-11-05",
                    capabilities: { tools: {} },
                    clientInfo: {
                        name: "omop-mcp-node-client",
                        version: "1.0.0"
                    }
                }
            };

            this.sendRequest(initRequest).then(resolve).catch(reject);
        });
    }

    async sendRequest(request) {
        return new Promise((resolve, reject) => {
            const requestJson = JSON.stringify(request) + '\n';
            this.process.stdin.write(requestJson);

            this.rl.once('line', (line) => {
                try {
                    const response = JSON.parse(line);
                    resolve(response);
                } catch (error) {
                    reject(error);
                }
            });
        });
    }

    async discoverConcepts(clinicalText, options = {}) {
        const request = {
            jsonrpc: "2.0",
            id: this.requestId++,
            method: "tools/call",
            params: {
                name: "discover_concepts",
                arguments: {
                    clinical_text: clinicalText,
                    domain: options.domain,
                    vocabulary: options.vocabulary,
                    standard_only: options.standardOnly ?? true,
                    limit: options.limit ?? 50
                }
            }
        };

        const response = await this.sendRequest(request);
        return response.result;
    }

    async queryOMOP(queryType, conceptIds, options = {}) {
        const request = {
            jsonrpc: "2.0",
            id: this.requestId++,
            method: "tools/call",
            params: {
                name: "query_omop",
                arguments: {
                    query_type: queryType,
                    concept_ids: conceptIds,
                    domain: options.domain ?? "Condition",
                    backend: options.backend ?? "bigquery",
                    execute: options.execute ?? true,
                    limit: options.limit ?? 1000
                }
            }
        };

        const response = await this.sendRequest(request);
        return response.result;
    }

    async stop() {
        if (this.process) {
            this.process.kill();
        }
        if (this.rl) {
            this.rl.close();
        }
    }
}

// Usage example
async function main() {
    const client = new OMOPMCPClient();

    try {
        await client.start();

        // Discover concepts
        const concepts = await client.discoverConcepts("diabetes", {
            domain: "Condition",
            limit: 10
        });

        console.log(`Found ${concepts.concepts.length} diabetes concepts`);

        // Query patient counts
        const conceptIds = concepts.concepts.slice(0, 5).map(c => c.concept_id);
        const result = await client.queryOMOP("count", conceptIds, {
            execute: true
        });

        console.log(`Patient count: ${result.results[0].patient_count}`);

    } finally {
        await client.stop();
    }
}

main().catch(console.error);
```

## Available Tools

### Core Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `discover_concepts` | Search ATHENA for OMOP concepts | `clinical_text`, `domain`, `vocabulary`, `standard_only`, `limit` |
| `get_concept_relationships` | Get concept relationships | `concept_id`, `relationship_id` |
| `query_omop` | Execute analytical queries | `query_type`, `concept_ids`, `domain`, `backend`, `execute`, `limit` |
| `generate_cohort_sql` | Generate cohort SQL | `exposure_concept_ids`, `outcome_concept_ids`, `pre_outcome_days`, `backend`, `validate` |

### New Direct SQL Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_information_schema` | Get database schema | `table_name`, `backend` |
| `select_query` | Execute direct SQL | `sql`, `validate`, `execute`, `backend`, `limit` |

## Available Resources

| Resource | URI Pattern | Description |
|----------|-------------|-------------|
| Concept Details | `omop://concept/{concept_id}` | Cacheable concept information |
| Concept Search | `athena://search?query={q}&domain={d}` | Paginated concept search |
| Backend Capabilities | `backend://capabilities` | Available backends and features |

## Available Prompts

| Prompt | Arguments | Description |
|--------|-----------|-------------|
| `cohort/sql` | `exposure`, `outcome`, `time_window`, `dialect` | SQL generation guidance |
| `analysis/discovery` | `question`, `domains` | Concept discovery workflow |
| `query/multi-step` | `concept_ids`, `domain` | Multi-step query execution |

## Authentication

### OAuth2.1 Support

For production deployments, enable OAuth2.1 authentication:

```bash
# Environment variables
OAUTH_ISSUER=https://your-auth-provider.com
OAUTH_AUDIENCE=omop-mcp-api
```

### Client Authentication

Include Bearer token in requests:

```python
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

async with session.post(url, json=payload, headers=headers) as response:
    return await response.json()
```

## Error Handling

### Common Error Types

```python
class MCPError(Exception):
    """Base MCP error."""
    pass

class ToolExecutionError(MCPError):
    """Tool execution failed."""
    pass

class ValidationError(MCPError):
    """Input validation failed."""
    pass

class AuthenticationError(MCPError):
    """Authentication failed."""
    pass
```

### Error Response Format

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "error": {
        "code": -32603,
        "message": "Internal error",
        "data": {
            "type": "ValidationError",
            "details": "Query exceeds cost limit: $2.50 > $1.00"
        }
    }
}
```

## Performance Optimization

### Connection Pooling

```python
import aiohttp

async def create_session():
    connector = aiohttp.TCPConnector(
        limit=100,  # Total connection pool size
        limit_per_host=30,  # Per-host connection limit
        ttl_dns_cache=300,  # DNS cache TTL
        use_dns_cache=True
    )

    timeout = aiohttp.ClientTimeout(
        total=30,  # Total timeout
        connect=10,  # Connection timeout
        sock_read=20  # Socket read timeout
    )

    return aiohttp.ClientSession(
        connector=connector,
        timeout=timeout
    )
```

### Caching

```python
import asyncio
from functools import lru_cache
from typing import Dict, Any

class CachedOMOPClient:
    def __init__(self, client: OMOPMCPClient):
        self.client = client
        self._cache = {}

    async def discover_concepts_cached(
        self,
        clinical_text: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Cached concept discovery."""
        cache_key = f"concepts:{clinical_text}:{hash(frozenset(kwargs.items()))}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        result = await self.client.discover_concepts(clinical_text, **kwargs)
        self._cache[cache_key] = result

        return result
```

## Testing

### Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_discover_concepts():
    client = OMOPMCPClient()

    with patch.object(client, '_send_request') as mock_send:
        mock_send.return_value = {
            "result": {
                "concepts": [
                    {"concept_id": 201826, "concept_name": "Type 2 diabetes"}
                ]
            }
        }

        result = await client.discover_concepts("diabetes")

        assert len(result["concepts"]) == 1
        assert result["concepts"][0]["concept_id"] == 201826
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_end_to_end_workflow():
    client = OMOPMCPClient()

    try:
        await client.start()

        # Discover concepts
        concepts = await client.discover_concepts("diabetes")
        assert len(concepts["concepts"]) > 0

        # Query database
        concept_ids = [c["concept_id"] for c in concepts["concepts"][:5]]
        result = await client.query_omop("count", concept_ids, execute=True)

        assert "results" in result
        assert len(result["results"]) > 0

    finally:
        await client.stop()
```

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install UV
RUN pip install uv

# Copy project
COPY . .

# Install dependencies
RUN uv pip install -e ".[dev]"

# Expose port
EXPOSE 8000

# Start server
CMD ["uv", "run", "python", "-m", "omop_mcp.server", "--http", "--port", "8000"]
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: omop-mcp-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: omop-mcp-server
  template:
    metadata:
      labels:
        app: omop-mcp-server
    spec:
      containers:
      - name: omop-mcp
        image: omop-mcp:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: omop-secrets
              key: openai-api-key
        - name: BACKEND_TYPE
          value: "bigquery"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: omop-mcp-service
spec:
  selector:
    app: omop-mcp-server
  ports:
  - port: 8000
    targetPort: 8000
  type: LoadBalancer
```

## Next Steps

- Explore the [Claude Desktop Integration](claude-desktop.md) for desktop usage
- Check out the [LibreChat + Ollama Integration](librechat-ollama.md) for local deployment
- Read the [API Reference](../api/tools.md) for detailed tool documentation
- Review the [SQL Validation Guide](../sql-validation.md) for security features
