"""
RAG API for Autonomous Agents.

FastAPI server providing direct access to the RAG knowledge base for
autonomous agents in the Hive platform. Designed for tool use by agents
in Cursor terminals and other autonomous workflows.

Features:
- Direct query endpoint for code-aware retrieval
- Streaming response support for responsive interaction
- Performance metrics and quality tracking
- Graceful degradation when index unavailable
- Session-based caching for conversation continuity

Usage:
    # Start server
    python -m uvicorn hive_ai.rag.api:app --reload --port 8765

    # Query from agent
    curl -X POST http://localhost:8765/query \\
         -H "Content-Type: application/json" \\
         -d '{"query": "How do I use the logging system?", "session_id": "agent-1"}'
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Note: These imports will work once hive packages are installed
try:
    from ..core.config import AIConfig
    from .context_formatter import ContextFormatter, FormattingStyle
    from .query_engine import QueryEngine
except ImportError:
    # Graceful degradation for development/testing
    AIConfig = None
    ContextFormatter = None
    FormattingStyle = None
    QueryEngine = None


# Request/Response Models
class QueryRequest(BaseModel):
    """Request model for RAG query."""

    query: str = Field(..., description="Natural language query about the codebase")
    session_id: str | None = Field(None, description="Session ID for conversation continuity")
    max_results: int = Field(10, ge=1, le=50, description="Maximum number of results to return")
    formatting_style: str = Field("instructional", description="Response formatting style")
    include_metadata: bool = Field(True, description="Include chunk metadata in response")
    stream: bool = Field(False, description="Stream response for responsive interaction")


class ChunkMetadata(BaseModel):
    """Metadata for a retrieved chunk."""

    file_path: str
    chunk_id: str
    score: float
    start_line: int | None = None
    end_line: int | None = None
    git_author: str | None = None
    last_modified: str | None = None


class QueryResponse(BaseModel):
    """Response model for RAG query."""

    query: str
    formatted_context: str
    chunks: list[dict[str, Any]]
    metadata: dict[str, Any]
    performance_ms: float
    timestamp: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    index_available: bool
    total_chunks: int
    last_indexed: str | None
    uptime_seconds: float


# Global state
class AppState:
    """Application state container."""

    def __init__(self):
        self.query_engine: QueryEngine | None = None
        self.context_formatter: ContextFormatter | None = None
        self.start_time: float = time.time()
        self.total_queries: int = 0
        self.index_available: bool = False


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager."""
    # Startup
    print("=" * 60)
    print("RAG API Starting...")
    print("=" * 60)

    # Initialize RAG components
    try:
        if QueryEngine and ContextFormatter:
            # Load configuration
            index_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "data" / "rag_index"

            # Initialize query engine
            app_state.query_engine = QueryEngine(index_dir=str(index_dir))

            # Initialize context formatter
            app_state.context_formatter = ContextFormatter()

            app_state.index_available = True
            print(f"✓ RAG index loaded from: {index_dir}")
        else:
            print("⚠ RAG modules not available - running in mock mode")
            app_state.index_available = False

    except Exception as e:
        print(f"⚠ Failed to initialize RAG components: {e}")
        print("  API will run in degraded mode (mock responses)")
        app_state.index_available = False

    print("✓ API ready at http://localhost:8765")
    print("=" * 60)

    yield

    # Shutdown
    print("RAG API shutting down...")


app = FastAPI(
    title="Hive RAG API",
    description="Direct RAG knowledge base access for autonomous agents",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns system status and index availability.
    """
    if app_state.index_available and app_state.query_engine:
        # Get index metadata
        metadata = app_state.query_engine._load_metadata(),
        total_chunks = metadata.get("total_chunks", 0)
        last_indexed = metadata.get("last_indexed_time")
    else:
        total_chunks = 0,
        last_indexed = None

    return HealthResponse(
        status="healthy" if app_state.index_available else "degraded",
        index_available=app_state.index_available,
        total_chunks=total_chunks,
        last_indexed=last_indexed,
        uptime_seconds=time.time() - app_state.start_time,
    )


@app.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest) -> QueryResponse | StreamingResponse:
    """
    Query the RAG knowledge base.

    This is the primary endpoint for autonomous agents to retrieve
    context-aware information about the codebase.

    Args:
        request: Query request with natural language question

    Returns:
        QueryResponse with formatted context and metadata

    Example:
        ```
        POST /query
        {
            "query": "How do I use the logging system?",
            "session_id": "agent-1",
            "max_results": 10,
            "formatting_style": "instructional"
        }
        ```
    """
    start_time = time.time()
    app_state.total_queries += 1

    # Check if index is available
    if not app_state.index_available or not app_state.query_engine:
        raise HTTPException(
            status_code=503,
            detail="RAG index not available - run indexing first: python scripts/rag/index_hive_codebase.py",
        )

    try:
        # Execute query
        results = await app_state.query_engine.query(
            query_text=request.query,
            max_results=request.max_results,
            session_id=request.session_id,
        )

        # Format context
        formatting_style_map = {
            "instructional": FormattingStyle.INSTRUCTIONAL,
            "structured": FormattingStyle.STRUCTURED,
            "minimal": FormattingStyle.MINIMAL,
            "markdown": FormattingStyle.MARKDOWN,
        }
        style = formatting_style_map.get(request.formatting_style, FormattingStyle.INSTRUCTIONAL)

        formatted_context = app_state.context_formatter.format(
            chunks=results["chunks"],
            query=request.query,
            style=style,
        )

        # Build response
        elapsed_ms = (time.time() - start_time) * 1000,

        response = QueryResponse(
            query=request.query,
            formatted_context=formatted_context,
            chunks=results["chunks"] if request.include_metadata else [],
            metadata={
                "total_results": len(results["chunks"]),
                "session_id": request.session_id,
                "formatting_style": request.formatting_style,
                "cache_hit": results.get("cache_hit", False),
            },
            performance_ms=round(elapsed_ms, 2),
            timestamp=datetime.now().isoformat(),
        )

        # Handle streaming if requested
        if request.stream:

            async def stream_response() -> AsyncIterator[str]:
                """Stream response chunks."""
                # Stream formatted context in chunks
                chunk_size = 100
                for i in range(0, len(formatted_context), chunk_size):
                    yield formatted_context[i : i + chunk_size]
                    await asyncio.sleep(0)  # Allow other tasks to run

            return StreamingResponse(
                stream_response(),
                media_type="text/plain",
            )

        return response

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Query failed: {str(e)}",
        )


@app.get("/stats")
async def get_stats() -> dict[str, Any]:
    """
    Get API usage statistics.

    Returns:
        Usage statistics including total queries and performance metrics
    """
    uptime = time.time() - app_state.start_time

    return {
        "uptime_seconds": round(uptime, 2),
        "total_queries": app_state.total_queries,
        "queries_per_minute": round((app_state.total_queries / uptime) * 60, 2) if uptime > 0 else 0,
        "index_available": app_state.index_available,
    }


@app.post("/reload-index")
async def reload_index() -> dict[str, str]:
    """
    Reload the RAG index from disk.

    Useful after running incremental indexing to pick up new changes
    without restarting the server.
    """
    try:
        if app_state.query_engine:
            # Reload index
            app_state.query_engine._load_index()
            return {"status": "success", "message": "Index reloaded successfully"}
        else:
            raise HTTPException(
                status_code=503,
                detail="Query engine not initialized",
            )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reload index: {str(e)}",
        )


# Example tool use for autonomous agents
AGENT_TOOL_SPEC = {
    "name": "query_codebase",
    "description": """Query the Hive codebase knowledge base for information about code,
    architecture, patterns, and best practices. Returns formatted context with relevant
    code examples and documentation.""",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language question about the codebase",
            },
            "session_id": {
                "type": "string",
                "description": "Session ID for conversation continuity (optional)",
            },
        },
        "required": ["query"],
    },
}


if __name__ == "__main__":
    import uvicorn

    print(__doc__)
    print("\nStarting RAG API server...")
    print("Access API docs at: http://localhost:8765/docs")

    uvicorn.run(
        "hive_ai.rag.api:app",
        host="0.0.0.0",
        port=8765,
        reload=True,
        log_level="info",
    )
