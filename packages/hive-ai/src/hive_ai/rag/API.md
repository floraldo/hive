## RAG API for Autonomous Agents

Direct HTTP API providing RAG knowledge base access for autonomous agents in the Hive platform.

### Quick Start

#### 1. Start the Server

```bash
# Start with default settings (port 8765)
python scripts/rag/start_api.py

# Custom port
python scripts/rag/start_api.py --port 9000

# Production mode
python scripts/rag/start_api.py --production --workers 4
```

#### 2. Verify Health

```bash
curl http://localhost:8765/health
```

Expected response:
```json
{
  "status": "healthy",
  "index_available": true,
  "total_chunks": 16000,
  "last_indexed": "2025-10-02T20:58:26.598990",
  "uptime_seconds": 123.45
}
```

#### 3. Query the Knowledge Base

```bash
curl -X POST http://localhost:8765/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I use the logging system?",
    "session_id": "agent-1",
    "max_results": 10,
    "formatting_style": "instructional"
  }'
```

### API Endpoints

#### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "index_available": true,
  "total_chunks": 16000,
  "last_indexed": "2025-10-02T20:58:26.598990",
  "uptime_seconds": 123.45
}
```

#### `POST /query`

Query the RAG knowledge base.

**Request:**
```json
{
  "query": "How do I create a new component?",
  "session_id": "agent-1",
  "max_results": 10,
  "formatting_style": "instructional",
  "include_metadata": true,
  "stream": false
}
```

**Parameters:**
- `query` (required): Natural language question about the codebase
- `session_id` (optional): Session ID for conversation continuity and caching
- `max_results` (optional, default 10): Maximum number of chunks to retrieve (1-50)
- `formatting_style` (optional, default "instructional"): Response format
  - `instructional`: Pedagogical format with explanations
  - `structured`: Organized by file/module
  - `minimal`: Compact, context-only format
  - `markdown`: Rich markdown with syntax highlighting
- `include_metadata` (optional, default true): Include chunk metadata in response
- `stream` (optional, default false): Stream response for responsive interaction

**Response:**
```json
{
  "query": "How do I create a new component?",
  "formatted_context": "To create a new component in the Hive platform:\n\n1. Use the component template...",
  "chunks": [
    {
      "content": "...",
      "metadata": {
        "file_path": "packages/hive-ai/src/...",
        "chunk_id": "chunk_123",
        "score": 0.95,
        "start_line": 45,
        "end_line": 72
      }
    }
  ],
  "metadata": {
    "total_results": 10,
    "session_id": "agent-1",
    "formatting_style": "instructional",
    "cache_hit": false
  },
  "performance_ms": 145.67,
  "timestamp": "2025-10-02T21:15:30.123456"
}
```

#### `GET /stats`

Get API usage statistics.

**Response:**
```json
{
  "uptime_seconds": 3600.0,
  "total_queries": 250,
  "queries_per_minute": 4.17,
  "index_available": true
}
```

#### `POST /reload-index`

Reload the RAG index from disk (useful after incremental indexing).

**Response:**
```json
{
  "status": "success",
  "message": "Index reloaded successfully"
}
```

### Integration with Autonomous Agents

#### Tool Specification (Claude/GPT)

```json
{
  "name": "query_codebase",
  "description": "Query the Hive codebase knowledge base for information about code, architecture, patterns, and best practices. Returns formatted context with relevant code examples and documentation.",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Natural language question about the codebase"
      },
      "session_id": {
        "type": "string",
        "description": "Session ID for conversation continuity (optional)"
      }
    },
    "required": ["query"]
  }
}
```

#### Python Agent Example

```python
import httpx
from typing import Dict, Any

class RAGAgent:
    """Agent with RAG knowledge base access."""

    def __init__(self, base_url: str = "http://localhost:8765"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url)
        self.session_id = "agent-" + str(id(self))

    async def query_codebase(
        self,
        query: str,
        max_results: int = 10,
        formatting_style: str = "instructional",
    ) -> Dict[str, Any]:
        """
        Query the codebase knowledge base.

        Args:
            query: Natural language question
            max_results: Maximum number of results
            formatting_style: Response format style

        Returns:
            Query response with formatted context
        """
        response = await self.client.post(
            "/query",
            json={
                "query": query,
                "session_id": self.session_id,
                "max_results": max_results,
                "formatting_style": formatting_style,
            },
        )
        response.raise_for_status()
        return response.json()

    async def get_context(self, query: str) -> str:
        """
        Get formatted context for a query.

        Returns just the formatted context string.
        """
        result = await self.query_codebase(query)
        return result["formatted_context"]


# Usage
async def main():
    agent = RAGAgent()

    # Query the knowledge base
    result = await agent.query_codebase(
        query="How do I implement a new validator in the golden rules system?",
        max_results=15,
        formatting_style="instructional",
    )

    print(result["formatted_context"])
    print(f"\nQuery took: {result['performance_ms']}ms")
    print(f"Cache hit: {result['metadata']['cache_hit']}")
```

#### JavaScript/TypeScript Agent Example

```typescript
interface QueryRequest {
  query: string;
  session_id?: string;
  max_results?: number;
  formatting_style?: "instructional" | "structured" | "minimal" | "markdown";
}

interface QueryResponse {
  query: string;
  formatted_context: string;
  chunks: any[];
  metadata: {
    total_results: number;
    session_id: string;
    formatting_style: string;
    cache_hit: boolean;
  };
  performance_ms: number;
  timestamp: string;
}

class RAGAgent {
  private baseUrl: string;
  private sessionId: string;

  constructor(baseUrl: string = "http://localhost:8765") {
    this.baseUrl = baseUrl;
    this.sessionId = `agent-${Date.now()}`;
  }

  async queryCodebase(request: QueryRequest): Promise<QueryResponse> {
    const response = await fetch(`${this.baseUrl}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...request,
        session_id: request.session_id || this.sessionId,
      }),
    });

    if (!response.ok) {
      throw new Error(`Query failed: ${response.statusText}`);
    }

    return response.json();
  }

  async getContext(query: string): Promise<string> {
    const result = await this.queryCodebase({ query });
    return result.formatted_context;
  }
}

// Usage
const agent = new RAGAgent();
const result = await agent.queryCodebase({
  query: "How do I use the event bus system?",
  max_results: 10,
  formatting_style: "instructional",
});

console.log(result.formatted_context);
```

#### Shell/Bash Agent Example

```bash
#!/bin/bash
# RAG query from bash script

RAG_API="http://localhost:8765"
SESSION_ID="bash-agent-$$"

query_codebase() {
    local query="$1"
    local max_results="${2:-10}"

    curl -s -X POST "${RAG_API}/query" \
        -H "Content-Type: application/json" \
        -d @- <<EOF
{
  "query": "${query}",
  "session_id": "${SESSION_ID}",
  "max_results": ${max_results},
  "formatting_style": "minimal"
}
EOF
}

# Usage
CONTEXT=$(query_codebase "How do I run tests?" | jq -r '.formatted_context')
echo "$CONTEXT"
```

### Session Management

The API supports session-based caching for conversation continuity:

```python
# Agent maintains session
agent = RAGAgent()  # Creates unique session_id

# First query (cold)
result1 = await agent.query_codebase("What is the logging system?")
# cache_hit: false, performance_ms: 150

# Related follow-up query (warm cache)
result2 = await agent.query_codebase("How do I configure logging?")
# cache_hit: true, performance_ms: 45
```

Session benefits:
- **Faster follow-up queries**: Cached embeddings and results
- **Context continuity**: Related queries benefit from previous context
- **Performance**: 60-80% reduction in latency for cached queries

### Performance Characteristics

**Typical Performance**:
- Cold query (no cache): 100-200ms
- Warm query (cache hit): 30-60ms
- P95 latency target: <150ms
- Streaming mode: First chunk <50ms

**Scaling**:
- Single worker: 100-200 queries/minute
- 4 workers (production): 400-800 queries/minute
- Memory footprint: ~500MB (index + embeddings)

### Error Handling

**503 Service Unavailable**: Index not available
```json
{
  "detail": "RAG index not available - run indexing first: python scripts/rag/index_hive_codebase.py"
}
```

**500 Internal Server Error**: Query execution failed
```json
{
  "detail": "Query failed: <error message>"
}
```

**Graceful Degradation**: If the index is unavailable, the health check will report `"status": "degraded"`, and query requests will return 503.

### Development Workflow

#### 1. Start Server in Development Mode

```bash
python scripts/rag/start_api.py
# Auto-reloads on code changes
```

#### 2. Test with Interactive Docs

Navigate to http://localhost:8765/docs for Swagger UI.

#### 3. Monitor Performance

```bash
watch -n 5 'curl -s http://localhost:8765/stats'
```

#### 4. Reload Index After Incremental Indexing

```bash
# Run incremental indexing
python scripts/rag/incremental_index.py

# Reload API index
curl -X POST http://localhost:8765/reload-index
```

### Production Deployment

#### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY packages/hive-ai /app/packages/hive-ai
COPY data/rag_index /app/data/rag_index

RUN pip install fastapi uvicorn sentence-transformers faiss-cpu

EXPOSE 8765

CMD ["uvicorn", "hive_ai.rag.api:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "4"]
```

#### Systemd Service

```ini
[Unit]
Description=Hive RAG API
After=network.target

[Service]
Type=simple
User=hive
WorkingDirectory=/opt/hive
ExecStart=/usr/bin/python3 scripts/rag/start_api.py --production --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

### Security Considerations

**Current Implementation**: Development/Internal use only

**For Production**:
1. Add API key authentication
2. Implement rate limiting
3. Add request validation and sanitization
4. Enable CORS with specific origins
5. Use HTTPS/TLS

Example with API key:
```python
from fastapi import Security, HTTPException
from fastapi.security.api_key import APIKeyHeader

API_KEY = "your-secret-key"
api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

# Apply to endpoints
@app.post("/query", dependencies=[Depends(verify_api_key)])
async def query_rag(request: QueryRequest):
    ...
```

### Troubleshooting

**"RAG index not available"**:
```bash
# Run full indexing first
python scripts/rag/index_hive_codebase.py
```

**Port already in use**:
```bash
# Use different port
python scripts/rag/start_api.py --port 9000
```

**Slow queries**:
- Check index size: Should be ~16,000 chunks
- Monitor memory usage: Should be <1GB
- Verify session_id usage for caching
- Check logs for errors

**Import errors**:
```bash
# Install dependencies
pip install fastapi uvicorn sentence-transformers faiss-cpu
```

### Next Steps

1. **Test the API**: Start server and query from your agents
2. **Integrate with agents**: Add `query_codebase` tool to your autonomous agents
3. **Monitor performance**: Track query latency and cache hit rates
4. **Expand capabilities**: Add file-specific queries, code generation support
