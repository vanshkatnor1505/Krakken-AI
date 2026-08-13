"""
Abstract tool interface for Krakken AI.

Every executable Krakken AI tool implements the Tool interface
defined in this module.

Architecture:

    AI
     ↓
    ToolCall
     ↓
    ToolManager
     ↓
    Tool
     ↓
    ToolResult

This module defines the execution contract only.

It does NOT:

- execute tools
- register tools
- manage tools
- communicate with QML
- call the AI provider
- contain tool-specific implementation
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.tools.models import (
    ToolCall,
    ToolDefinition,
    ToolResult,
)


# ============================================================
# TOOL ERROR
# ============================================================


class ToolError(Exception):
    """
    Base exception for tool-related failures.
    """


# ============================================================
# ABSTRACT TOOL
# ============================================================


class Tool(ABC):
    """
    Abstract base class for every Krakken AI tool.

    A concrete tool is responsible for:

        1. Describing itself
        2. Validating its arguments
        3. Executing its action
        4. Returning a ToolResult
    """

    # ========================================================
    # DEFINITION
    # ========================================================

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """
        Return the public definition of this tool.

        The definition is used by the AI/tool-calling layer
        to understand what this tool does and what arguments
        it accepts.
        """

        raise NotImplementedError

    # ========================================================
    # EXECUTION
    # ========================================================

    @abstractmethod
    def execute(
        self,
        call: ToolCall,
    ) -> ToolResult:
        """
        Execute a tool call.

        Concrete tools implement their actual behavior here.

        The method must return a ToolResult rather than exposing
        implementation-specific values to the rest of the system.
        """

        raise NotImplementedError

    # ========================================================
    # VALIDATION
    # ========================================================

    def validate(
        self,
        arguments: dict[str, Any],
    ) -> None:
        """
        Validate tool arguments.

        The default implementation performs basic validation.

        Concrete tools can override this method when they require
        more specific validation.
        """

        if not isinstance(
            arguments,
            dict,
        ):
            raise ToolError(
                f"Arguments for tool "
                f"'{self.name}' must be a dictionary."
            )

    # ========================================================
    # SAFE EXECUTION
    # ========================================================

    def run(
        self,
        call: ToolCall,
    ) -> ToolResult:
        """
        Safely execute a ToolCall.

        This method provides a common execution boundary around
        concrete tool implementations.

        Concrete tools normally implement execute(), not run().
        """

        try:

            if not isinstance(
                call,
                ToolCall,
            ):
                raise ToolError(
                    "Tool call must be a ToolCall object."
                )

            if call.name != self.name:

                raise ToolError(
                    f"Tool call targets "
                    f"'{call.name}', but this tool "
                    f"is '{self.name}'."
                )

            self.validate(
                call.arguments
            )

            result = self.execute(
                call
            )

            if not isinstance(
                result,
                ToolResult,
            ):
                raise ToolError(
                    f"Tool '{self.name}' returned "
                    f"an invalid result."
                )

            # ------------------------------------------------
            # Attach tool identity if the implementation did
            # not provide it.
            # ------------------------------------------------

            if result.tool_name is None:

                result.tool_name = self.name

            if result.call_id is None:

                result.call_id = call.call_id

            return result

        except ToolError as exc:

            return ToolResult.failure_result(
                str(exc),
                tool_name=self.name,
                call_id=call.call_id,
            )

        except Exception as exc:

            return ToolResult.failure_result(
                f"Tool '{self.name}' failed: {exc}",
                tool_name=self.name,
                call_id=call.call_id,
            )

    # ========================================================
    # PROPERTIES
    # ========================================================

    @property
    def name(self) -> str:
        """
        Return the tool's unique name.
        """

        return self.definition.name

    @property
    def description(self) -> str:
        """
        Return the tool description.
        """

        return self.definition.description

    @property
    def parameters(self) -> dict[str, Any]:
        """
        Return the tool's parameter schema.
        """

        return self.definition.parameters

    @property
    def category(self) -> str | None:
        """
        Return the tool category.
        """

        return self.definition.category

    @property
    def requires_confirmation(self) -> bool:
        """
        Whether this tool requires user confirmation before
        execution.

        The ToolManager will eventually use this flag when
        handling potentially destructive actions.
        """

        return self.definition.requires_confirmation