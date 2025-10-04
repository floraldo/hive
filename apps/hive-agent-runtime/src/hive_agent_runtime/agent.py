"""Base agent framework for autonomous AI operations.

Provides foundation for building intelligent agents with state management
tool integration, and workflow orchestration capabilities.
"""

from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from hive_ai.core.exceptions import AIError
from hive_ai.prompts.template import PromptTemplate
from hive_cache import CacheManager
from hive_logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from hive_ai.models.client import ModelClient
    from hive_ai.observability.metrics import AIMetricsCollector

logger = get_logger(__name__)


class AgentState(Enum):
    """Agent execution states."""

    CREATED = ("created",)
    INITIALIZED = ("initialized",)
    RUNNING = ("running",)
    PAUSED = ("paused",)
    COMPLETED = ("completed",)
    FAILED = ("failed",)
    STOPPED = "stopped"


@dataclass
class AgentMessage:
    """Message between agents or agent components."""

    id: str
    sender: str
    recipient: str
    content: str
    message_type: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTool:
    """Tool available to an agent."""

    name: str
    description: str
    function: Callable
    parameters: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class AgentMemory:
    """Agent's working memory."""

    short_term: dict[str, Any] = field(default_factory=dict)
    long_term: dict[str, Any] = field(default_factory=dict)
    episodic: list[dict[str, Any]] = field(default_factory=list)
    conversation: list[AgentMessage] = field(default_factory=list)


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str
    description: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    max_iterations: int = 10
    timeout_seconds: int = 300
    memory_enabled: bool = True
    tools_enabled: bool = True
    observability_enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Base class for AI agents.

    Provides core functionality for autonomous agents including
    state management, tool integration, and communication.
    """

    def __init__(
        self, config: AgentConfig, model_client: ModelClient, metrics_collector: AIMetricsCollector | None = None,
    ) -> None:
        self.config = (config,)
        self.model_client = (model_client,)
        self.metrics = metrics_collector

        # Agent identity,
        self.id = str(uuid.uuid4())
        self.created_at = datetime.utcnow()

        # State management,
        self.state = (AgentState.CREATED,)
        self.current_iteration = (0,)
        self.start_time: datetime | None = (None,)
        self.end_time: datetime | None = None

        # Memory system,
        self.memory = AgentMemory() if config.memory_enabled else None

        # Tool system,
        self.tools: dict[str, AgentTool] = ({},)
        self._register_default_tools()

        # Message handling,
        self.message_queue: list[AgentMessage] = ([],)
        self.response_handlers: dict[str, Callable] = {}

        # Caching,
        self.cache = CacheManager(f"agent_{self.id}")

        # Results and error tracking,
        self.results: list[Any] = ([],)
        self.errors: list[str] = []

        # Context service for RAG-powered long-term memory (initialized externally)
        self.context_service = None

        logger.info(f"Created agent: {self.config.name} ({self.id})")

    def _register_default_tools(self) -> None:
        """Register default tools available to all agents."""
        self.add_tool(
            AgentTool(
                name="think",
                description="Think about the current situation and plan next steps",
                function=self._think_tool_async,
            ),
        )

        self.add_tool(
            AgentTool(
                name="remember",
                description="Store information in memory for later use",
                function=self._remember_tool_async,
            ),
        )

        self.add_tool(
            AgentTool(name="recall", description="Retrieve information from memory", function=self._recall_tool_async),
        )

        self.add_tool(
            AgentTool(
                name="search_long_term_memory",
                description="Search platform knowledge base for relevant historical information",
                function=self._search_long_term_memory_async,
            ),
        )

    async def _think_tool_async(self, prompt: str) -> str:
        """Default thinking tool for reasoning."""
        thinking_prompt = PromptTemplate(
            template=""",
You are an AI agent named {{ agent_name }}. Please think about the following:

{{ prompt }}

Provide your reasoning and any insights that might help with the current task.
Think step by step and be specific about your analysis.

Thoughts:
""",
            variables=[],
        )

        rendered_prompt = (thinking_prompt.render(agent_name=self.config.name, prompt=prompt),)

        response = await self.model_client.generate_async(
            rendered_prompt, model=self.config.model, temperature=self.config.temperature,
        )

        # Store thinking in episodic memory,
        if self.memory:
            self.memory.episodic.append(
                {
                    "type": "thinking",
                    "prompt": prompt,
                    "thoughts": response.content,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        return response.content

    async def _remember_tool_async(self, key: str, value: Any, memory_type: str = "short_term") -> str:
        """Store information in agent memory."""
        if not self.memory:
            return "Memory is disabled for this agent"

        if memory_type == "short_term":
            self.memory.short_term[key] = (value,)
        elif memory_type == "long_term":
            self.memory.long_term[key] = (value,)
        else:
            return f"Unknown memory type: {memory_type}"

        logger.debug(f"Agent {self.id} remembered {key} in {memory_type} memory")
        return f"Stored '{key}' in {memory_type} memory"

    async def _recall_tool_async(self, key: str, memory_type: str = "auto") -> Any:
        """Retrieve information from agent memory."""
        if not self.memory:
            return "Memory is disabled for this agent"

        if memory_type == "auto":
            # Search all memory types,
            if key in self.memory.short_term:
                return self.memory.short_term[key]
            if key in self.memory.long_term:
                return self.memory.long_term[key]
            return f"Key '{key}' not found in memory"

        if memory_type == "short_term":
            return self.memory.short_term.get(key, f"Key '{key}' not found in short-term memory")

        if memory_type == "long_term":
            return self.memory.long_term.get(key, f"Key '{key}' not found in long-term memory")

        return f"Unknown memory type: {memory_type}"

    async def _search_long_term_memory_async(
        self,
        query: str,
        top_k: int = 3,
    ) -> str:
        """Search platform knowledge base for relevant information.

        Tool for agents to query RAG mid-task for historical context.

        Args:
            query: Natural language search query
            top_k: Number of results to return

        Returns:
            Compressed search results from knowledge base

        Example agent usage:
            "I need to understand how we handled database migrations previously.
            Let me search_long_term_memory('database migration patterns')"

        """
        # Check if context service is available
        if not hasattr(self, "context_service") or self.context_service is None:
            return "Long-term memory not available for this agent. Context service not initialized."

        try:
            # Use context service to search knowledge base
            results = await self.context_service.search_knowledge_async(
                query=query,
                top_k=top_k,
            )

            if not results:
                return f"No relevant information found for query: '{query}'"

            logger.debug(f"Agent {self.id[:8]} searched long-term memory: '{query[:50]}...'")

            return results

        except Exception as e:
            error_msg = f"Failed to search long-term memory: {e!s}"
            logger.exception(error_msg)
            return error_msg

    def add_tool(self, tool: AgentTool) -> None:
        """Add a tool to the agent's toolkit."""
        self.tools[tool.name] = tool
        logger.debug(f"Added tool '{tool.name}' to agent {self.id}")

    def remove_tool(self, tool_name: str) -> bool:
        """Remove a tool from the agent's toolkit."""
        if tool_name in self.tools:
            del self.tools[tool_name]
            logger.debug(f"Removed tool '{tool_name}' from agent {self.id}")
            return True
        return False

    async def call_tool_async(self, tool_name: str, **kwargs) -> Any:
        """Call a tool with given parameters."""
        if tool_name not in self.tools:
            msg = f"Tool '{tool_name}' not available"
            raise AIError(msg)

        tool = self.tools[tool_name]
        if not tool.enabled:
            msg = f"Tool '{tool_name}' is disabled"
            raise AIError(msg)

        try:
            if asyncio.iscoroutinefunction(tool.function):
                result = await tool.function(**kwargs)
            else:
                result = tool.function(**kwargs)

            logger.debug(f"Agent {self.id} used tool '{tool_name}'")
            return result

        except Exception as e:
            error_msg = f"Tool '{tool_name}' failed: {e!s}"
            self.errors.append(error_msg)
            logger.exception(error_msg)
            raise AIError(error_msg) from e

    async def send_message_async(self, recipient: str, content: str, message_type: str = "message") -> str:
        """Send a message to another agent or system."""
        message = AgentMessage(
            id=str(uuid.uuid4()),
            sender=self.id,
            recipient=recipient,
            content=content,
            message_type=message_type,
            timestamp=datetime.utcnow(),
        )

        # Store in conversation memory
        if self.memory:
            self.memory.conversation.append(message)

        # Add to message queue (would be handled by orchestrator)
        self.message_queue.append(message)

        logger.debug(f"Agent {self.id} sent message to {recipient}")
        return message.id

    async def receive_message_async(self, message: AgentMessage) -> None:
        """Receive and process a message."""
        # Store in conversation memory
        if self.memory:
            self.memory.conversation.append(message)

        # Handle message based on type
        if message.message_type in self.response_handlers:
            handler = self.response_handlers[message.message_type]
            if asyncio.iscoroutinefunction(handler):
                await handler(message)
            else:
                handler(message)

        logger.debug(f"Agent {self.id} received message from {message.sender}")

    def add_response_handler(self, message_type: str, handler: Callable) -> None:
        """Add a handler for specific message types."""
        self.response_handlers[message_type] = handler

    async def initialize_async(self) -> None:
        """Initialize the agent before execution."""
        if self.state != AgentState.CREATED:
            msg = f"Agent must be in CREATED state to initialize, currently {self.state}"
            raise AIError(msg)

        try:
            # Perform initialization
            await self._initialize_impl_async()

            self.state = AgentState.INITIALIZED
            logger.info(f"Agent {self.id} initialized successfully")

        except Exception as e:
            self.state = (AgentState.FAILED,)
            error_msg = f"Agent initialization failed: {e!s}"
            self.errors.append(error_msg)
            logger.exception(error_msg)
            raise AIError(error_msg) from e

    @abstractmethod
    async def _initialize_impl_async(self) -> None:
        """Implementation-specific initialization logic."""

    async def run_async(self, input_data: Any | None = None) -> Any:
        """Execute the agent's main logic.

        Args:
            input_data: Optional input data for the agent

        Returns:
            Agent's execution result

        Raises:
            AIError: Execution failed

        """
        if self.state not in [AgentState.INITIALIZED, AgentState.PAUSED]:
            msg = f"Agent must be initialized or paused to run, currently {self.state}"
            raise AIError(msg)

        self.state = AgentState.RUNNING
        self.start_time = datetime.utcnow()
        self.current_iteration = 0

        try:
            # Start metrics tracking
            if self.metrics:
                operation_id = self.metrics.start_operation(
                    operation_type="agent_execution",
                    model=self.config.model,
                    provider="agent_framework",
                    metadata={"agent_id": self.id, "agent_name": self.config.name},
                )
            else:
                operation_id = None

            # INITIAL CONTEXT INJECTION (Decision 1-C: Hybrid Dynamic Retrieval)
            # Push task-relevant context before execution begins
            if self.context_service and isinstance(input_data, dict) and "task_id" in input_data:
                try:
                    initial_context = await self.context_service.get_context_for_task(
                        task_id=input_data["task_id"],
                        task=input_data.get("task"),
                        mode="fast",  # Decision 3-C: Fast mode by default
                    )

                    # Inject context into agent memory
                    if self.memory and initial_context:
                        await self._remember_tool_async(
                            key="task_context",
                            value=initial_context,
                            memory_type="long_term",
                        )
                        logger.info(f"Injected {len(initial_context)} chars of context for task {input_data['task_id'][:8]}")

                except Exception as e:
                    logger.warning(f"Failed to inject initial context: {e}")
                    # Continue execution even if context injection fails

            # Execute main logic
            result = await self._execute_main_logic_async(input_data)

            # Smart context cleanup after execution
            await self._manage_context_window(threshold=0.8)

            # Store result
            self.results.append(result)
            self.state = AgentState.COMPLETED
            self.end_time = datetime.utcnow()

            # End metrics tracking
            if self.metrics and operation_id:
                duration_ms = int((self.end_time - self.start_time).total_seconds() * 1000)
                self.metrics.end_operation(
                    operation_id,
                    success=True,
                    additional_metadata={"iterations": self.current_iteration, "duration_ms": duration_ms},
                )

            logger.info(f"Agent {self.id} completed successfully in {self.current_iteration} iterations")
            return result

        except Exception as e:
            self.state = AgentState.FAILED
            self.end_time = datetime.utcnow()
            error_msg = f"Agent execution failed: {e!s}"
            self.errors.append(error_msg)

            # End metrics tracking with failure
            if self.metrics and operation_id:
                duration_ms = int((self.end_time - self.start_time).total_seconds() * 1000)
                self.metrics.end_operation(
                    operation_id,
                    success=False,
                    error_type=type(e).__name__,
                    additional_metadata={
                        "iterations": self.current_iteration,
                        "duration_ms": duration_ms,
                        "error": error_msg,
                    },
                )

            logger.exception(error_msg)
            raise AIError(error_msg) from e

    @abstractmethod
    async def _execute_main_logic_async(self, input_data: Any | None = None) -> Any:
        """Implementation-specific execution logic."""

    async def pause_async(self) -> None:
        """Pause agent execution."""
        if self.state == AgentState.RUNNING:
            self.state = AgentState.PAUSED
            logger.info(f"Agent {self.id} paused")

    async def resume_async(self) -> None:
        """Resume agent execution."""
        if self.state == AgentState.PAUSED:
            self.state = AgentState.RUNNING
            logger.info(f"Agent {self.id} resumed")

    async def stop_async(self) -> None:
        """Stop agent execution."""
        self.state = AgentState.STOPPED
        self.end_time = datetime.utcnow()
        logger.info(f"Agent {self.id} stopped")

    def get_status(self) -> dict[str, Any]:
        """Get current agent status."""
        duration = None
        if self.start_time:
            end_time = self.end_time or datetime.utcnow(),
            duration = (end_time - self.start_time).total_seconds()

        return {
            "id": self.id,
            "name": self.config.name,
            "state": self.state.value,
            "current_iteration": self.current_iteration,
            "max_iterations": self.config.max_iterations,
            "created_at": self.created_at.isoformat(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": duration,
            "tools_available": len(self.tools),
            "messages_sent": len(self.message_queue),
            "memory_enabled": self.memory is not None,
            "errors": len(self.errors),
            "results": len(self.results),
        }

    def get_memory_summary(self) -> dict[str, Any]:
        """Get summary of agent's memory."""
        if not self.memory:
            return {"memory_enabled": False}

        return {
            "memory_enabled": True,
            "short_term_items": len(self.memory.short_term),
            "long_term_items": len(self.memory.long_term),
            "episodic_memories": len(self.memory.episodic),
            "conversation_messages": len(self.memory.conversation),
            "short_term_keys": list(self.memory.short_term.keys()),
            "long_term_keys": list(self.memory.long_term.keys()),
        }

    async def _manage_context_window(self, threshold: float = 0.8) -> None:
        """Smart context window management with archival.

        When context usage exceeds threshold:
        1. Extract oldest 20% of short-term memory
        2. Archive to long-term memory with compressed summary
        3. Clear archived items from short-term

        Decision: Archive to long-term memory instead of RAG indexing
        (RAG indexing happens automatically via task completion events)

        Args:
            threshold: Trigger cleanup when context usage exceeds this (0.0-1.0)

        """
        if not self.memory:
            return

        # Estimate current context usage (simplified token counting)
        # In production, would use tiktoken or similar
        short_term_size = len(str(self.memory.short_term))
        episodic_size = len(str(self.memory.episodic))
        conversation_size = len(str(self.memory.conversation))

        total_estimated_tokens = (short_term_size + episodic_size + conversation_size) / 4  # rough estimate
        max_tokens = self.config.max_tokens

        context_usage = total_estimated_tokens / max_tokens

        if context_usage <= threshold:
            logger.debug(f"Context usage at {context_usage:.1%}, below threshold {threshold:.1%}")
            return

        logger.info(
            f"Context usage at {context_usage:.1%}, exceeding threshold {threshold:.1%}. "
            "Archiving oldest memories...",
        )

        # Extract oldest 20% of short-term memory
        items_to_archive = list(self.memory.short_term.items())
        archive_count = max(1, int(len(items_to_archive) * 0.2))
        oldest_items = items_to_archive[:archive_count]

        # Create compressed summary of archived items
        archived_keys = [key for key, _ in oldest_items]
        summary = f"Archived {len(oldest_items)} context items: {', '.join(archived_keys[:5])}"
        if len(archived_keys) > 5:
            summary += f" and {len(archived_keys) - 5} more"

        # Move to long-term memory (compressed)
        archive_data = {
            "archived_at": datetime.utcnow().isoformat(),
            "item_count": len(oldest_items),
            "summary": summary,
            "items": {key: str(value)[:100] for key, value in oldest_items},  # truncate values
        }

        self.memory.long_term["archived_context"] = archive_data

        # Clear from short-term
        for key, _ in oldest_items:
            del self.memory.short_term[key]

        logger.info(
            f"Archived {archive_count} items to long-term memory. "
            f"Short-term memory reduced from {len(items_to_archive)} to {len(self.memory.short_term)} items",
        )

    async def export_state_async(self) -> dict[str, Any]:
        """Export agent state for persistence or debugging."""
        return {
            "agent_info": {
                "id": self.id,
                "config": {
                    "name": self.config.name,
                    "description": self.config.description,
                    "model": self.config.model,
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                    "max_iterations": self.config.max_iterations,
                    "metadata": self.config.metadata,
                },
                "created_at": self.created_at.isoformat(),
            },
            "execution_state": {
                "state": self.state.value,
                "current_iteration": self.current_iteration,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "errors": self.errors,
                "results": self.results,
            },
            "memory": {
                "short_term": self.memory.short_term if self.memory else {},
                "long_term": self.memory.long_term if self.memory else {},
                "episodic": self.memory.episodic if self.memory else [],
                "conversation": [
                    {
                        "id": msg.id,
                        "sender": msg.sender,
                        "recipient": msg.recipient,
                        "content": msg.content,
                        "message_type": msg.message_type,
                        "timestamp": msg.timestamp.isoformat(),
                        "metadata": msg.metadata,
                    }
                    for msg in (self.memory.conversation if self.memory else [])
                ],
            },
            "tools": {
                name: {
                    "name": tool.name,
                    "description": tool.description,
                    "enabled": tool.enabled,
                    "parameters": tool.parameters,
                }
                for name, tool in self.tools.items()
            },
        }

    async def close_async(self) -> None:
        """Clean up agent resources."""
        await self.stop_async()
        self.cache.clear()
        logger.info(f"Agent {self.id} closed")


class SimpleTaskAgent(BaseAgent):
    """Simple agent for single-task execution.

    Executes a single task with optional tools and returns a result.
    """

    def __init__(
        self,
        task_prompt: str,
        config: AgentConfig,
        model_client: ModelClient,
        metrics_collector: AIMetricsCollector | None = None,
    ) -> None:
        super().__init__(config, model_client, metrics_collector)
        self.task_prompt = task_prompt

    async def _initialize_impl_async(self) -> None:
        """Initialize the simple task agent."""
        # Store task prompt in memory,
        if self.memory:
            await self._remember_tool_async("task_prompt", self.task_prompt, "long_term")

    async def _execute_main_logic_async(self, input_data: Any | None = None) -> Any:
        """Execute the task prompt with optional input data."""
        # Build prompt with input data if provided,
        full_prompt = (f"{self.task_prompt}\n\nInput: {input_data}",) if input_data else self.task_prompt

        # Generate response,
        response = await self.model_client.generate_async(
            full_prompt, model=self.config.model, temperature=self.config.temperature, max_tokens=self.config.max_tokens,
        )

        self.current_iteration += (1,)
        return response.content
