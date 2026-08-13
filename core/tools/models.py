"""
Data models used by the Krakken AI tool system.

These models define the communication contracts between:

    AI
      ↓
    ToolManager
      ↓
    Tool
      ↓
    ToolResult
      ↓
    AI

The models contain no tool execution logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ============================================================
# TOOL CALL
# ============================================================


@dataclass(slots=True)
class ToolCall:
    """
    Represents a request to execute a tool.

    A ToolCall is produced by the AI/tool-calling layer and
    consumed by ToolManager.
    """

    name: str

    arguments: dict[str, Any] = field(
        default_factory=dict
    )

    call_id: str | None = None


# ============================================================
# TOOL RESULT
# ============================================================


@dataclass(slots=True)
class ToolResult:
    """
    Represents the result returned by a tool.

    Tools should return ToolResult instead of exposing their
    internal implementation details to the rest of Krakken AI.
    """

    success: bool

    data: Any = None

    error: str | None = None

    tool_name: str | None = None

    call_id: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    # --------------------------------------------------------
    # Factory helpers
    # --------------------------------------------------------

    @classmethod
    def success_result(
        cls,
        data: Any = None,
        *,
        tool_name: str | None = None,
        call_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        """
        Create a successful tool result.
        """

        return cls(
            success=True,
            data=data,
            error=None,
            tool_name=tool_name,
            call_id=call_id,
            metadata=metadata or {},
        )

    @classmethod
    def failure_result(
        cls,
        error: str,
        *,
        tool_name: str | None = None,
        call_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        """
        Create a failed tool result.
        """

        return cls(
            success=False,
            data=None,
            error=error,
            tool_name=tool_name,
            call_id=call_id,
            metadata=metadata or {},
        )


# ============================================================
# TOOL DEFINITION
# ============================================================


@dataclass(slots=True)
class ToolDefinition:
    """
    Describes a tool to the AI system.

    This is metadata only.

    It allows the AI layer to understand:

        - what the tool is called
        - what it does
        - what arguments it accepts
    """

    name: str

    description: str

    parameters: dict[str, Any] = field(
        default_factory=dict
    )

    category: str | None = None

    requires_confirmation: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )