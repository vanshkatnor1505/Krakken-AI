"""
Tool execution manager for Krakken AI.

The ToolManager coordinates tool execution between the AI/tool-calling
layer and the registered tools.

Architecture:

    AI
     ↓
    AIToolCall
     ↓
    ToolManager
     ↓
    ToolRegistry
     ↓
    Tool
     ↓
    ToolResult
     ↓
    AI

Responsibilities:

    - Execute individual tool calls
    - Convert AI tool calls into internal ToolCall objects
    - Resolve tools through ToolRegistry
    - Handle unknown tools
    - Respect tool confirmation requirements
    - Execute multiple tool calls
    - Return normalized ToolResult objects
    - Expose registered tool definitions

The ToolManager does NOT:

    - communicate with the AI provider
    - call the Groq SDK
    - register tools
    - implement tool behavior
    - communicate with QML
    - manage application UI
    - decide which tool the AI should use

Tool selection belongs to the AI layer.
Tool execution belongs here.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from core.ai.models import AIToolCall
from core.tools.models import (
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from core.tools.registry import (
    ToolRegistry,
    ToolRegistryError,
)

# ============================================================
# TOOL MANAGER ERROR
# ============================================================


class ToolManagerError(Exception):
    """
    Base exception for ToolManager failures.
    """


# ============================================================
# TOOL MANAGER
# ============================================================


class ToolManager:
    """
    Coordinates execution of Krakken AI tools.

    The ToolManager sits between the AI layer and the actual
    executable tools.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        logger: Any = None,
    ) -> None:

        if not isinstance(
            registry,
            ToolRegistry,
        ):
            raise ToolManagerError(
                "ToolManager requires a ToolRegistry."
            )

        self._registry = registry
        self._logger = logger

    # ========================================================
    # EXECUTE TOOL CALL
    # ========================================================

    def execute(
        self,
        call: ToolCall,
    ) -> ToolResult:
        """
        Execute a single ToolCall.

        Execution flow:

            ToolCall
                ↓
            ToolRegistry
                ↓
                Tool
                ↓
            Tool.run()
                ↓
            ToolResult
        """

        if not isinstance(
            call,
            ToolCall,
        ):
            return ToolResult.failure_result(
                "Tool call must be a ToolCall object."
            )

        name = call.name.strip()

        if not name:
            return ToolResult.failure_result(
                "Tool call name cannot be empty.",
                call_id=call.call_id,
            )

        # ----------------------------------------------------
        # Resolve tool
        # ----------------------------------------------------

        try:

            tool = self._registry.get(
                name
            )

        except ToolRegistryError as exc:

            self._log(
                f"Unknown tool requested: '{name}'",
                error=True,
            )

            return ToolResult.failure_result(
                str(exc),
                tool_name=name,
                call_id=call.call_id,
            )

        # ----------------------------------------------------
        # Confirmation
        # ----------------------------------------------------

        if tool.requires_confirmation:

            return self._handle_confirmation_required(
                call
            )

        # ----------------------------------------------------
        # Execute
        # ----------------------------------------------------

        self._log(
            f"Executing tool: '{name}'"
        )

        try:

            result = tool.run(
                call
            )

        except Exception as exc:

            self._log(
                f"Unexpected error while executing "
                f"tool '{name}': {exc}",
                error=True,
            )

            return ToolResult.failure_result(
                f"Tool '{name}' execution failed: {exc}",
                tool_name=name,
                call_id=call.call_id,
            )

        # ----------------------------------------------------
        # Defensive result validation
        # ----------------------------------------------------

        if not isinstance(
            result,
            ToolResult,
        ):

            self._log(
                f"Tool '{name}' returned an invalid result.",
                error=True,
            )

            return ToolResult.failure_result(
                f"Tool '{name}' returned an invalid result.",
                tool_name=name,
                call_id=call.call_id,
            )

        # ----------------------------------------------------
        # Preserve identity
        # ----------------------------------------------------

        if result.tool_name is None:

            result.tool_name = name

        if result.call_id is None:

            result.call_id = call.call_id

        if result.success:

            self._log(
                f"Tool '{name}' completed successfully."
            )

        else:

            self._log(
                f"Tool '{name}' completed with failure.",
                error=True,
            )

        return result

    # ========================================================
    # EXECUTE AI TOOL CALL
    # ========================================================

    def execute_ai_call(
        self,
        call: AIToolCall,
    ) -> ToolResult:
        """
        Execute an AI-generated tool call.

        Converts the AI-layer AIToolCall into the internal
        ToolCall model before execution.
        """

        if not isinstance(
            call,
            AIToolCall,
        ):
            return ToolResult.failure_result(
                "AI tool call must be an AIToolCall object."
            )

        name = call.name.strip()

        if not name:

            return ToolResult.failure_result(
                "AI tool call name cannot be empty.",
                call_id=call.call_id,
            )

        if not isinstance(
            call.arguments,
            dict,
        ):

            return ToolResult.failure_result(
                (
                    f"Arguments for tool '{name}' "
                    "must be a dictionary."
                ),
                tool_name=name,
                call_id=call.call_id,
            )

        tool_call = ToolCall(
            name=name,
            arguments=dict(
                call.arguments
            ),
            call_id=call.call_id,
        )

        return self.execute(
            tool_call
        )

    # ========================================================
    # EXECUTE MANY
    # ========================================================

    def execute_many(
        self,
        calls: Sequence[ToolCall],
    ) -> list[ToolResult]:
        """
        Execute multiple ToolCalls sequentially.

        Calls are executed in the order provided.
        """

        if not isinstance(
            calls,
            Sequence,
        ):

            raise ToolManagerError(
                "Tool calls must be provided as a sequence."
            )

        results: list[
            ToolResult
        ] = []

        for call in calls:

            results.append(
                self.execute(
                    call
                )
            )

        return results

    # ========================================================
    # EXECUTE MANY AI CALLS
    # ========================================================

    def execute_ai_calls(
        self,
        calls: Sequence[AIToolCall],
    ) -> list[ToolResult]:
        """
        Execute multiple AI-generated tool calls.
        """

        if not isinstance(
            calls,
            Sequence,
        ):

            raise ToolManagerError(
                "AI tool calls must be provided as a sequence."
            )

        results: list[
            ToolResult
        ] = []

        for call in calls:

            results.append(
                self.execute_ai_call(
                    call
                )
            )

        return results

    # ========================================================
    # DEFINITIONS
    # ========================================================

    def definitions(
        self,
    ) -> list[ToolDefinition]:
        """
        Return definitions of all registered tools.
        """

        return self._registry.definitions()

    # ========================================================
    # GET TOOL DEFINITIONS
    # ========================================================

    def get_tool_definitions(
        self,
    ) -> list[ToolDefinition]:
        """
        Return definitions of all registered tools.

        Compatibility API used by application services.
        """

        return self._registry.definitions()

    # ========================================================
    # TOOLS
    # ========================================================

    def tools(
        self,
    ) -> list[Any]:
        """
        Return a snapshot of all registered tools.
        """

        return self._registry.tools()

    # ========================================================
    # GET TOOLS
    # ========================================================

    def get_tools(
        self,
    ) -> list[Any]:
        """
        Return all registered tools.

        Compatibility API used by application services.
        """

        return self._registry.tools()

    # ========================================================
    # NAMES
    # ========================================================

    def names(
        self,
    ) -> list[str]:
        """
        Return the names of all registered tools.
        """

        return self._registry.names()

    # ========================================================
    # GET TOOL NAMES
    # ========================================================

    def get_tool_names(
        self,
    ) -> list[str]:
        """
        Return the names of all registered tools.

        Compatibility API used by AssistantService.
        """

        return self._registry.names()

    # ========================================================
    # CONTAINS
    # ========================================================

    def contains(
        self,
        name: str,
    ) -> bool:
        """
        Check whether a tool is registered.
        """

        return self._registry.contains(
            name
        )

    # ========================================================
    # HAS TOOL
    # ========================================================

    def has_tool(
        self,
        name: str,
    ) -> bool:
        """
        Compatibility alias for contains().
        """

        return self._registry.contains(
            name
        )

    # ========================================================
    # COUNT
    # ========================================================

    @property
    def count(
        self,
    ) -> int:
        """
        Return the number of registered tools.
        """

        return self._registry.count

    # ========================================================
    # VALIDATE
    # ========================================================

    def validate(
        self,
    ) -> None:
        """
        Validate the underlying ToolRegistry.

        Useful during application startup and diagnostics.
        """

        try:

            self._registry.validate()

        except ToolRegistryError as exc:

            raise ToolManagerError(
                f"Tool registry validation failed: {exc}"
            ) from exc

    # ========================================================
    # CONFIRMATION
    # ========================================================

    def _handle_confirmation_required(
        self,
        call: ToolCall,
    ) -> ToolResult:
        """
        Handle tools that require user confirmation.

        The actual confirmation UI/event mechanism will be
        implemented later through Krakken's application/event
        layer.

        For now, execution is safely blocked.
        """

        self._log(
            (
                f"Tool '{call.name}' requires "
                "user confirmation."
            )
        )

        return ToolResult.failure_result(
            (
                f"Tool '{call.name}' requires user "
                "confirmation before execution."
            ),
            tool_name=call.name,
            call_id=call.call_id,
            metadata={
                "requires_confirmation": True,
            },
        )

    # ========================================================
    # LOGGER
    # ========================================================

    def _log(
        self,
        message: str,
        error: bool = False,
    ) -> None:
        """
        Write a message to the optional logger.

        Logging failures are intentionally ignored so logging
        can never break tool execution.
        """

        if self._logger is None:
            return

        try:

            if error:

                self._logger.error(
                    message
                )

            else:

                self._logger.info(
                    message
                )

        except Exception:

            pass