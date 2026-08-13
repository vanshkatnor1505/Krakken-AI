"""
Tool registry for Krakken AI.

The ToolRegistry maintains the collection of tools available
to Krakken AI.

Responsibilities:

    - Register tools
    - Unregister tools
    - Look up tools by name
    - Check whether a tool exists
    - List registered tools
    - Expose tool definitions

The registry does NOT:

    - execute tools
    - call the AI provider
    - communicate with QML
    - manage EventBus events
    - decide which tool the AI should use

Tool execution belongs to ToolManager.
"""

from __future__ import annotations

from threading import RLock

from core.tools.models import ToolDefinition
from core.tools.tool import Tool


# ============================================================
# REGISTRY ERROR
# ============================================================


class ToolRegistryError(Exception):
    """
    Base exception for tool registry failures.
    """


# ============================================================
# TOOL REGISTRY
# ============================================================


class ToolRegistry:
    """
    Central registry of available Krakken AI tools.

    Each tool is identified by its unique tool name.

    Example:

        registry = ToolRegistry()

        registry.register(
            OpenBrowserTool()
        )

        tool = registry.get(
            "open_browser"
        )
    """

    def __init__(self) -> None:

        self._tools: dict[str, Tool] = {}

        self._lock = RLock()

    # ========================================================
    # REGISTER
    # ========================================================

    def register(
        self,
        tool: Tool,
    ) -> None:
        """
        Register a tool.

        Tool names must be unique.

        Registering another tool with an existing name raises
        ToolRegistryError instead of silently replacing the
        existing tool.
        """

        if not isinstance(
            tool,
            Tool,
        ):
            raise ToolRegistryError(
                "Only Tool instances can be registered."
            )

        name = tool.name.strip()

        if not name:

            raise ToolRegistryError(
                "Tool name cannot be empty."
            )

        with self._lock:

            if name in self._tools:

                raise ToolRegistryError(
                    f"Tool '{name}' is already registered."
                )

            self._tools[name] = tool

    # ========================================================
    # UNREGISTER
    # ========================================================

    def unregister(
        self,
        name: str,
    ) -> None:
        """
        Remove a registered tool.

        Raises ToolRegistryError if the tool does not exist.
        """

        name = self._normalize_name(
            name
        )

        with self._lock:

            if name not in self._tools:

                raise ToolRegistryError(
                    f"Tool '{name}' is not registered."
                )

            del self._tools[name]

    # ========================================================
    # GET
    # ========================================================

    def get(
        self,
        name: str,
    ) -> Tool:
        """
        Return a registered tool by name.

        Raises ToolRegistryError if the tool does not exist.
        """

        name = self._normalize_name(
            name
        )

        with self._lock:

            tool = self._tools.get(
                name
            )

        if tool is None:

            raise ToolRegistryError(
                f"Tool '{name}' is not registered."
            )

        return tool

    # ========================================================
    # TRY GET
    # ========================================================

    def try_get(
        self,
        name: str,
    ) -> Tool | None:
        """
        Return a registered tool if it exists.

        Unlike get(), this method does not raise an exception
        when the tool is missing.
        """

        name = self._normalize_name(
            name
        )

        with self._lock:

            return self._tools.get(
                name
            )

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

        name = self._normalize_name(
            name
        )

        with self._lock:

            return name in self._tools

    # ========================================================
    # COUNT
    # ========================================================

    @property
    def count(self) -> int:
        """
        Return the number of registered tools.
        """

        with self._lock:

            return len(
                self._tools
            )

    # ========================================================
    # TOOLS
    # ========================================================

    def tools(self) -> list[Tool]:
        """
        Return a snapshot of all registered tools.

        The returned list is independent from the registry's
        internal dictionary.
        """

        with self._lock:

            return list(
                self._tools.values()
            )

    # ========================================================
    # NAMES
    # ========================================================

    def names(self) -> list[str]:
        """
        Return the names of all registered tools.
        """

        with self._lock:

            return list(
                self._tools.keys()
            )

    # ========================================================
    # DEFINITIONS
    # ========================================================

    def definitions(self) -> list[ToolDefinition]:
        """
        Return the definitions of all registered tools.

        These definitions will eventually be provided to the
        AI/tool-calling layer.
        """

        with self._lock:

            tools = list(
                self._tools.values()
            )

        return [
            tool.definition
            for tool in tools
        ]

    # ========================================================
    # CLEAR
    # ========================================================

    def clear(self) -> None:
        """
        Remove all registered tools.
        """

        with self._lock:

            self._tools.clear()

    # ========================================================
    # VALIDATION
    # ========================================================

    def validate(self) -> None:
        """
        Validate the current registry.

        This checks that:

            - every registered tool is a Tool
            - every tool has a valid name
            - no duplicate names exist

        Normally registration already guarantees these
        conditions, but this method is useful during startup
        diagnostics.
        """

        with self._lock:

            tools = list(
                self._tools.values()
            )

        seen: set[str] = set()

        for tool in tools:

            if not isinstance(
                tool,
                Tool,
            ):

                raise ToolRegistryError(
                    "Registry contains an invalid tool."
                )

            name = tool.name.strip()

            if not name:

                raise ToolRegistryError(
                    "Registry contains a tool with "
                    "an empty name."
                )

            if name in seen:

                raise ToolRegistryError(
                    f"Duplicate tool name detected: "
                    f"'{name}'."
                )

            seen.add(name)

    # ========================================================
    # NAME NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_name(
        name: str,
    ) -> str:
        """
        Normalize a tool name before lookup.

        Tool names are intentionally case-sensitive at the
        definition level, but surrounding whitespace is ignored.
        """

        if not isinstance(
            name,
            str,
        ):

            raise ToolRegistryError(
                "Tool name must be a string."
            )

        name = name.strip()

        if not name:

            raise ToolRegistryError(
                "Tool name cannot be empty."
            )

        return name