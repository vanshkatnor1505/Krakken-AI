"""
Realtime webpage opening/fetching tool for Krakken AI.

This tool fetches a live webpage and converts its HTML into
readable text for the AI.

Architecture:

    AI
     ↓
    ToolManager
     ↓
    OpenTool
     ↓
    Internet
     ↓
    HTML
     ↓
    Clean text
     ↓
    ToolResult
     ↓
    AI

The tool does NOT:

- open a browser window
- communicate with QML
- communicate with Groq
- decide when it should be used
- execute arbitrary local programs
"""

from __future__ import annotations

import html
import re
import ssl
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener

from core.tools.models import (
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from core.tools.tool import Tool, ToolError


# ============================================================
# HTML TEXT EXTRACTOR
# ============================================================


class _HTMLTextExtractor(HTMLParser):
    """
    Convert webpage HTML into readable text.

    This intentionally ignores:

        - scripts
        - styles
        - SVG
        - navigation metadata
        - comments
    """

    _IGNORED_TAGS = {
        "script",
        "style",
        "noscript",
        "svg",
        "canvas",
        "template",
        "head",
    }

    _BLOCK_TAGS = {
        "article",
        "aside",
        "blockquote",
        "br",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "section",
        "table",
        "tr",
        "ul",
    }

    def __init__(self) -> None:

        super().__init__(
            convert_charrefs=True
        )

        self.parts: list[str] = []

        self._ignored_depth = 0

    # --------------------------------------------------------
    # START TAG
    # --------------------------------------------------------

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:

        tag = tag.lower()

        if tag in self._IGNORED_TAGS:

            self._ignored_depth += 1

            return

        if self._ignored_depth > 0:

            return

        if tag in self._BLOCK_TAGS:

            self.parts.append(
                "\n"
            )

    # --------------------------------------------------------
    # END TAG
    # --------------------------------------------------------

    def handle_endtag(
        self,
        tag: str,
    ) -> None:

        tag = tag.lower()

        if tag in self._IGNORED_TAGS:

            if self._ignored_depth > 0:

                self._ignored_depth -= 1

            return

        if self._ignored_depth > 0:

            return

        if tag in self._BLOCK_TAGS:

            self.parts.append(
                "\n"
            )

    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    def handle_data(
        self,
        data: str,
    ) -> None:

        if self._ignored_depth > 0:

            return

        if not data.strip():

            return

        self.parts.append(
            data
        )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    def get_text(
        self,
    ) -> str:

        text = "".join(
            self.parts
        )

        text = html.unescape(
            text
        )

        # Normalize Windows/macOS line endings.

        text = text.replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )

        # Remove whitespace around newlines.

        text = re.sub(
            r"[ \t]+\n",
            "\n",
            text,
        )

        text = re.sub(
            r"\n[ \t]+",
            "\n",
            text,
        )

        # Collapse excessive blank lines.

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        # Collapse repeated spaces.

        text = re.sub(
            r"[ \t]{2,}",
            " ",
            text,
        )

        return text.strip()


# ============================================================
# OPEN TOOL
# ============================================================


class OpenTool(Tool):
    """
    Fetch and read a live webpage.

    Tool name:

        open_url
    """

    _USER_AGENT = (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36 "
        "KrakkenAI/2.0"
    )

    _TIMEOUT = 15

    # Prevent enormous webpages from flooding the model
    # context.

    _MAX_CONTENT_LENGTH = 60_000

    # Maximum downloaded bytes.

    _MAX_DOWNLOAD_BYTES = 2_000_000

    def __init__(
        self,
        logger: Any = None,
    ) -> None:

        self._logger = logger

    # ========================================================
    # DEFINITION
    # ========================================================

    @property
    def definition(
        self,
    ) -> ToolDefinition:

        return ToolDefinition(
            name="open_url",
            description=(
                "Open and read a live webpage from the "
                "internet. Use this after web_search when "
                "you need the actual contents of a result, "
                "or when the user provides a URL. Returns "
                "the webpage title, URL, and readable text."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": (
                            "The complete HTTP or HTTPS "
                            "URL to open."
                        ),
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": (
                            "Maximum number of webpage "
                            "characters to return. "
                            "Default is 60000."
                        ),
                        "minimum": 1000,
                        "maximum": 100000,
                    },
                },
                "required": [
                    "url",
                ],
            },
            category="web",
            requires_confirmation=False,
            metadata={
                "realtime": True,
                "network": True,
            },
        )

    # ========================================================
    # EXECUTION
    # ========================================================

    def execute(
        self,
        call: ToolCall,
    ) -> ToolResult:

        url = call.arguments.get(
            "url"
        )

        if not isinstance(
            url,
            str,
        ):

            raise ToolError(
                "URL must be a string."
            )

        url = url.strip()

        if not url:

            raise ToolError(
                "URL cannot be empty."
            )

        # ----------------------------------------------------
        # Normalize URL
        # ----------------------------------------------------

        if not re.match(
            r"^https?://",
            url,
            flags=re.IGNORECASE,
        ):

            url = (
                "https://"
                + url
            )

        # ----------------------------------------------------
        # Validate URL
        # ----------------------------------------------------

        parsed = urlparse(
            url
        )

        if parsed.scheme.lower() not in (
            "http",
            "https",
        ):

            raise ToolError(
                "Only HTTP and HTTPS URLs are supported."
            )

        if not parsed.netloc:

            raise ToolError(
                "Invalid URL: missing hostname."
            )

        max_chars = call.arguments.get(
            "max_chars",
            self._MAX_CONTENT_LENGTH,
        )

        try:

            max_chars = int(
                max_chars
            )

        except (
            TypeError,
            ValueError,
        ):

            max_chars = (
                self._MAX_CONTENT_LENGTH
            )

        max_chars = max(
            1000,
            min(
                max_chars,
                100_000,
            ),
        )

        self._log(
            f"Opening realtime URL: {url}"
        )

        try:

            html_content, final_url, content_type = (
                self._fetch(
                    url
                )
            )

            # ------------------------------------------------
            # Content type
            # ------------------------------------------------

            if (
                "text/html"
                not in content_type.lower()
                and "application/xhtml"
                not in content_type.lower()
            ):

                return ToolResult.success_result(
                    data={
                        "url": final_url,
                        "content_type": content_type,
                        "text": (
                            "The requested URL did not "
                            "return an HTML webpage."
                        ),
                        "realtime": True,
                    },
                    tool_name=self.name,
                    call_id=call.call_id,
                )

            # ------------------------------------------------
            # Extract text
            # ------------------------------------------------

            parser = _HTMLTextExtractor()

            parser.feed(
                html_content
            )

            text = parser.get_text()

            # ------------------------------------------------
            # Limit content
            # ------------------------------------------------

            truncated = (
                len(text)
                > max_chars
            )

            if truncated:

                text = text[
                    :max_chars
                ].rstrip()

                text += (
                    "\n\n"
                    "[Content truncated by Krakken AI.]"
                )

            title = self._extract_title(
                html_content
            )

            self._log(
                (
                    f"URL opened successfully: "
                    f"{final_url} "
                    f"characters={len(text)}"
                )
            )

            return ToolResult.success_result(
                data={
                    "url": final_url,
                    "title": title,
                    "content_type": content_type,
                    "text": text,
                    "characters": len(text),
                    "truncated": truncated,
                    "realtime": True,
                },
                tool_name=self.name,
                call_id=call.call_id,
            )

        except HTTPError as exc:

            self._log(
                (
                    f"HTTP error while opening "
                    f"{url}: {exc.code} {exc.reason}"
                ),
                error=True,
            )

            return ToolResult.failure_result(
                (
                    f"Website returned HTTP "
                    f"{exc.code}: {exc.reason}"
                ),
                tool_name=self.name,
                call_id=call.call_id,
            )

        except URLError as exc:

            self._log(
                (
                    f"Network error while opening "
                    f"{url}: {exc.reason}"
                ),
                error=True,
            )

            return ToolResult.failure_result(
                (
                    "Unable to reach the website. "
                    f"Network error: {exc.reason}"
                ),
                tool_name=self.name,
                call_id=call.call_id,
            )

        except Exception as exc:

            self._log(
                (
                    f"Failed to open URL "
                    f"{url}: {exc}"
                ),
                error=True,
            )

            return ToolResult.failure_result(
                (
                    f"Failed to open webpage: {exc}"
                ),
                tool_name=self.name,
                call_id=call.call_id,
            )

    # ========================================================
    # FETCH
    # ========================================================

    def _fetch(
        self,
        url: str,
    ) -> tuple[str, str, str]:

        request = Request(
            url,
            headers={
                "User-Agent": self._USER_AGENT,
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,*/*;q=0.8"
                ),
                "Accept-Language": (
                    "en-US,en;q=0.9"
                ),
            },
            method="GET",
        )

        ssl_context = (
            ssl.create_default_context()
        )

        opener = build_opener()

        with opener.open(
            request,
            timeout=self._TIMEOUT,
            context=ssl_context,
        ) as response:

            content_type = (
                response.headers.get(
                    "Content-Type",
                    "text/html",
                )
            )

            final_url = response.geturl()

            # ------------------------------------------------
            # Read with a hard upper bound.
            # ------------------------------------------------

            raw = response.read(
                self._MAX_DOWNLOAD_BYTES
            )

            charset = (
                response.headers.get_content_charset()
                or "utf-8"
            )

            text = raw.decode(
                charset,
                errors="replace",
            )

            return (
                text,
                final_url,
                content_type,
            )

    # ========================================================
    # TITLE
    # ========================================================

    @staticmethod
    def _extract_title(
        html_content: str,
    ) -> str:

        match = re.search(
            r"<title[^>]*>(.*?)</title>",
            html_content,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        if not match:

            return ""

        title = html.unescape(
            match.group(1)
        )

        title = re.sub(
            r"\s+",
            " ",
            title,
        )

        return title.strip()

    # ========================================================
    # LOGGING
    # ========================================================

    def _log(
        self,
        message: str,
        error: bool = False,
    ) -> None:

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