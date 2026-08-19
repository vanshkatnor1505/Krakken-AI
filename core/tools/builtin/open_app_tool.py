"""
Open apps and common web destinations for Krakken AI.
"""

from __future__ import annotations

import os
import re
import subprocess
import shutil
import webbrowser
from pathlib import Path
from typing import Any

from core.tools.models import ToolCall, ToolDefinition, ToolResult
from core.tools.tool import Tool, ToolError


class OpenAppTool(Tool):
    """
    Launch common desktop apps or open well-known web destinations.
    """

    _WEB_TARGETS = {
        "google": "https://www.google.com",
        "youtube": "https://www.youtube.com",
        "youtube music": "https://music.youtube.com",
        "youtubemusic": "https://music.youtube.com",
        "yt music": "https://music.youtube.com",
        "gmail": "https://mail.google.com",
        "google maps": "https://www.google.com/maps",
        "maps": "https://www.google.com/maps",
    }

    _VSCODE_CANDIDATES = (
        "code",
        "code.cmd",
    )

    def __init__(self, logger: Any = None) -> None:
        self._logger = logger

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="open_app",
            description=(
                "Open common desktop apps or web destinations. "
                "Use this for YouTube, YouTube Music, Google, Gmail, Maps, "
                "and desktop apps like VS Code."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": (
                            "App or destination to open, such as youtube, "
                            "youtube music, google, or vscode."
                        ),
                    },
                    "query": {
                        "type": "string",
                        "description": (
                            "Optional search query to pass to supported "
                            "web destinations."
                        ),
                    },
                },
                "required": ["target"],
            },
            category="system",
            requires_confirmation=False,
        )

    def execute(self, call: ToolCall) -> ToolResult:
        target = call.arguments.get("target")
        query = call.arguments.get("query")

        if not isinstance(target, str):
            raise ToolError("Target must be a string.")

        target = target.strip().lower()
        if not target:
            raise ToolError("Target cannot be empty.")

        if isinstance(query, str):
            query = query.strip()
        else:
            query = ""

        self._log(f"Opening target: {target!r}, query: {query!r}")

        try:
            if self._looks_like_url(target):
                url = self._prepare_url(target, query)
                self._open_web(url)
                return ToolResult.success_result(
                    data={"target": target, "url": url, "opened": True},
                    tool_name=self.name,
                    call_id=call.call_id,
                )

            if target in self._WEB_TARGETS:
                url = self._prepare_web_target(target, query)
                self._open_web(url)
                return ToolResult.success_result(
                    data={"target": target, "url": url, "opened": True},
                    tool_name=self.name,
                    call_id=call.call_id,
                )

            if target in ("vscode", "vs code", "visual studio code"):
                self._launch_vscode()
                return ToolResult.success_result(
                    data={"target": target, "opened": True},
                    tool_name=self.name,
                    call_id=call.call_id,
                )

            raise ToolError(
                "Unsupported app target. Try youtube, youtube music, google, or vscode."
            )

        except Exception as exc:
            self._log(f"Open app failed: {exc}", error=True)
            return ToolResult.failure_result(
                str(exc),
                tool_name=self.name,
                call_id=call.call_id,
            )

    def _prepare_web_target(self, target: str, query: str) -> str:
        base = self._WEB_TARGETS[target]

        if not query:
            return base

        if target == "google":
            return f"{base}/search?q={self._encode_query(query)}"

        if target in ("youtube",):
            return f"{base}/results?search_query={self._encode_query(query)}"

        if target in ("youtube music", "youtubemusic", "yt music"):
            return f"{base}/search?q={self._encode_query(query)}"

        if target in ("gmail", "google maps", "maps"):
            return base

        return base

    def _prepare_url(self, target: str, query: str) -> str:
        if not query:
            return target if target.startswith(("http://", "https://")) else f"https://{target}"
        return f"https://www.google.com/search?q={self._encode_query(query)}"

    def _open_web(self, url: str) -> None:
        if os.name == "nt":
            try:
                os.startfile(url)  # type: ignore[attr-defined]
                return
            except Exception:
                pass

        if webbrowser.open(url, new=2):
            return

        raise ToolError(f"Unable to open web destination: {url}")

    def _launch_vscode(self) -> None:
        command = self._find_vscode_command()
        if command is None:
            raise ToolError("VS Code executable not found.")

        subprocess.Popen(
            [command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            shell=False,
        )

    def _find_vscode_command(self) -> str | None:
        for command in self._VSCODE_CANDIDATES:
            resolved = shutil.which(command)
            if resolved:
                return resolved

        localappdata = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("ProgramFiles", "")
        candidates = [
            Path(localappdata) / "Programs" / "Microsoft VS Code" / "Code.exe",
            Path(program_files) / "Microsoft VS Code" / "Code.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None

    @staticmethod
    def _encode_query(query: str) -> str:
        from urllib.parse import quote_plus

        return quote_plus(query)

    @staticmethod
    def _looks_like_url(target: str) -> bool:
        return bool(re.match(r"^https?://", target, flags=re.IGNORECASE))

    def _log(self, message: str, error: bool = False) -> None:
        if self._logger is None:
            return
        try:
            if error:
                self._logger.error(message)
            else:
                self._logger.info(message)
        except Exception:
            pass
