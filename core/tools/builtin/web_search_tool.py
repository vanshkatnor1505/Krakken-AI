"""
Realtime web search tool for Krakken AI.

This tool performs live internet searches and returns structured
search results to the AI/tool-calling layer.

Architecture:

    AI
     ↓
    ToolManager
     ↓
    WebSearchTool
     ↓
    Internet Search Engine
     ↓
    Search Results
     ↓
    ToolResult
     ↓
    AI

The tool does NOT:

- communicate with QML
- communicate directly with Groq
- decide whether it should be used
- maintain conversation history
- contain UI logic

The AI decides when to call this tool.
"""

from __future__ import annotations

import html
import re
import ssl
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urljoin, urlparse
from urllib.request import Request, urlopen

from core.tools.models import (
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from core.tools.tool import Tool, ToolError


# ============================================================
# SEARCH RESULT PARSER
# ============================================================


class _DuckDuckGoParser(HTMLParser):
    """
    Lightweight HTML parser for DuckDuckGo HTML results.

    We intentionally avoid external scraping dependencies so
    Krakken can perform realtime searches without requiring
    requests, BeautifulSoup, or another third-party package.
    """

    def __init__(self) -> None:

        super().__init__()

        self.results: list[dict[str, str]] = []

        self._current_result: dict[str, str] | None = None

        self._inside_result = False

        self._inside_title = False

        self._inside_snippet = False

        self._title_parts: list[str] = []

        self._snippet_parts: list[str] = []

    # --------------------------------------------------------
    # START TAG
    # --------------------------------------------------------

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:

        attributes = dict(attrs)

        classes = (
            attributes.get("class") or ""
        ).split()

        # DuckDuckGo result link.

        if (
            tag == "a"
            and "result__a" in classes
        ):

            href = attributes.get(
                "href"
            )

            if not href:

                return

            self._current_result = {
                "title": "",
                "url": href,
                "snippet": "",
            }

            self._inside_result = True

            self._inside_title = True

            self._title_parts = []

            self._snippet_parts = []

            return

        # Result snippet.

        if (
            self._inside_result
            and tag in ("a", "div")
            and "result__snippet" in classes
        ):

            self._inside_snippet = True

    # --------------------------------------------------------
    # END TAG
    # --------------------------------------------------------

    def handle_endtag(
        self,
        tag: str,
    ) -> None:

        if (
            self._inside_title
            and tag == "a"
        ):

            self._inside_title = False

            if self._current_result is not None:

                self._current_result["title"] = (
                    self._clean_text(
                        "".join(
                            self._title_parts
                        )
                    )
                )

            return

        if (
            self._inside_snippet
            and tag in ("a", "div")
        ):

            self._inside_snippet = False

            if self._current_result is not None:

                self._current_result["snippet"] = (
                    self._clean_text(
                        "".join(
                            self._snippet_parts
                        )
                    )
                )

                self.results.append(
                    self._current_result
                )

                self._current_result = None

                self._inside_result = False

    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    def handle_data(
        self,
        data: str,
    ) -> None:

        if self._inside_title:

            self._title_parts.append(
                data
            )

        elif self._inside_snippet:

            self._snippet_parts.append(
                data
            )

    # --------------------------------------------------------
    # TEXT CLEANING
    # --------------------------------------------------------

    @staticmethod
    def _clean_text(
        text: str,
    ) -> str:

        text = html.unescape(
            text
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()


# ============================================================
# BING FALLBACK PARSER
# ============================================================


class _BingParser(HTMLParser):
    """
    Lightweight parser for Bing HTML results.

    Used only when DuckDuckGo is unavailable.
    """

    def __init__(self) -> None:

        super().__init__()

        self.results: list[dict[str, str]] = []

        self._current: dict[str, str] | None = None

        self._inside_title = False

        self._inside_snippet = False

        self._title_parts: list[str] = []

        self._snippet_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:

        attributes = dict(attrs)

        classes = (
            attributes.get("class") or ""
        ).split()

        if (
            tag == "li"
            and "b_algo" in classes
        ):

            self._current = {
                "title": "",
                "url": "",
                "snippet": "",
            }

            return

        if self._current is None:

            return

        if (
            tag == "h2"
        ):

            self._inside_title = True

            self._title_parts = []

            return

        if (
            tag == "a"
            and self._inside_title
        ):

            href = attributes.get(
                "href"
            )

            if href:

                self._current["url"] = href

            return

        if (
            tag == "p"
        ):

            self._inside_snippet = True

            self._snippet_parts = []

    def handle_endtag(
        self,
        tag: str,
    ) -> None:

        if (
            self._inside_title
            and tag == "h2"
        ):

            self._inside_title = False

            if self._current is not None:

                self._current["title"] = (
                    self._clean_text(
                        "".join(
                            self._title_parts
                        )
                    )
                )

            return

        if (
            self._inside_snippet
            and tag == "p"
        ):

            self._inside_snippet = False

            if self._current is not None:

                self._current["snippet"] = (
                    self._clean_text(
                        "".join(
                            self._snippet_parts
                        )
                    )
                )

    def handle_data(
        self,
        data: str,
    ) -> None:

        if self._inside_title:

            self._title_parts.append(
                data
            )

        elif self._inside_snippet:

            self._snippet_parts.append(
                data
            )

    def handle_endtag_old(
        self,
        tag: str,
    ) -> None:
        pass

    @staticmethod
    def _clean_text(
        text: str,
    ) -> str:

        text = html.unescape(
            text
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()


# ============================================================
# WEB SEARCH TOOL
# ============================================================


class WebSearchTool(Tool):
    """
    Perform a realtime web search.

    Tool name:

        web_search
    """

    _USER_AGENT = (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36 "
        "KrakkenAI/2.0"
    )

    _DEFAULT_RESULTS = 5

    _MAX_RESULTS = 10

    _TIMEOUT = 12

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
            name="web_search",
            description=(
                "Search the live internet for current "
                "information. Use this when the user asks "
                "for recent, realtime, latest, current, "
                "news, prices, facts, websites, or information "
                "that may have changed since the model's "
                "knowledge cutoff. Returns search result "
                "titles, URLs, and snippets."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "The search query to send to "
                            "the internet."
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": (
                            "Maximum number of results "
                            "to return. Default is 5. "
                            "Maximum is 10."
                        ),
                        "minimum": 1,
                        "maximum": 10,
                    },
                },
                "required": [
                    "query",
                ],
            },
            category="web",
            requires_confirmation=False,
            metadata={
                "realtime": True,
                "network": True,
                "provider": "duckduckgo_with_bing_fallback",
            },
        )

    # ========================================================
    # EXECUTION
    # ========================================================

    def execute(
        self,
        call: ToolCall,
    ) -> ToolResult:

        query = call.arguments.get(
            "query"
        )

        if not isinstance(
            query,
            str,
        ):

            raise ToolError(
                "Search query must be a string."
            )

        query = query.strip()

        if not query:

            raise ToolError(
                "Search query cannot be empty."
            )

        max_results = call.arguments.get(
            "max_results",
            self._DEFAULT_RESULTS,
        )

        try:

            max_results = int(
                max_results
            )

        except (
            TypeError,
            ValueError,
        ):

            max_results = (
                self._DEFAULT_RESULTS
            )

        max_results = max(
            1,
            min(
                max_results,
                self._MAX_RESULTS,
            ),
        )

        self._log(
            f"Realtime web search: {query!r}"
        )

        # ----------------------------------------------------
        # DuckDuckGo
        # ----------------------------------------------------

        try:

            results = self._search_duckduckgo(
                query=query,
                max_results=max_results,
            )

            if results:

                return ToolResult.success_result(
                    data={
                        "query": query,
                        "results": results,
                        "result_count": len(
                            results
                        ),
                        "source": "DuckDuckGo",
                        "realtime": True,
                    },
                    tool_name=self.name,
                    call_id=call.call_id,
                )

        except Exception as exc:

            self._log(
                f"DuckDuckGo search failed: {exc}",
                error=True,
            )

        # ----------------------------------------------------
        # Bing fallback
        # ----------------------------------------------------

        try:

            results = self._search_bing(
                query=query,
                max_results=max_results,
            )

            if results:

                return ToolResult.success_result(
                    data={
                        "query": query,
                        "results": results,
                        "result_count": len(
                            results
                        ),
                        "source": "Bing",
                        "realtime": True,
                    },
                    tool_name=self.name,
                    call_id=call.call_id,
                )

        except Exception as exc:

            self._log(
                f"Bing search failed: {exc}",
                error=True,
            )

        return ToolResult.failure_result(
            (
                "Realtime web search failed. "
                "The available search engines did not "
                "return usable results."
            ),
            tool_name=self.name,
            call_id=call.call_id,
        )

    # ========================================================
    # DUCKDUCKGO SEARCH
    # ========================================================

    def _search_duckduckgo(
        self,
        query: str,
        max_results: int,
    ) -> list[dict[str, str]]:

        url = (
            "https://html.duckduckgo.com/html/?q="
            + quote_plus(query)
        )

        response = self._http_get(
            url
        )

        parser = _DuckDuckGoParser()

        parser.feed(
            response
        )

        results: list[dict[str, str]] = []

        for item in parser.results:

            title = item.get(
                "title",
                "",
            ).strip()

            result_url = item.get(
                "url",
                "",
            ).strip()

            snippet = item.get(
                "snippet",
                "",
            ).strip()

            if not title or not result_url:

                continue

            result_url = (
                self._normalize_search_url(
                    result_url
                )
            )

            if not result_url:

                continue

            results.append(
                {
                    "title": title,
                    "url": result_url,
                    "snippet": snippet,
                }
            )

            if len(results) >= max_results:

                break

        return results

    # ========================================================
    # BING SEARCH
    # ========================================================

    def _search_bing(
        self,
        query: str,
        max_results: int,
    ) -> list[dict[str, str]]:

        url = (
            "https://www.bing.com/search?q="
            + quote_plus(query)
        )

        response = self._http_get(
            url
        )

        parser = _BingParser()

        parser.feed(
            response
        )

        results: list[dict[str, str]] = []

        for item in parser.results:

            title = item.get(
                "title",
                "",
            ).strip()

            result_url = item.get(
                "url",
                "",
            ).strip()

            snippet = item.get(
                "snippet",
                "",
            ).strip()

            if not title or not result_url:

                continue

            results.append(
                {
                    "title": title,
                    "url": result_url,
                    "snippet": snippet,
                }
            )

            if len(results) >= max_results:

                break

        return results

    # ========================================================
    # HTTP
    # ========================================================

    def _http_get(
        self,
        url: str,
    ) -> str:

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

        with urlopen(
            request,
            timeout=self._TIMEOUT,
            context=ssl_context,
        ) as response:

            raw = response.read()

            charset = (
                response.headers.get_content_charset()
                or "utf-8"
            )

            return raw.decode(
                charset,
                errors="replace",
            )

    # ========================================================
    # URL NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_search_url(
        url: str,
    ) -> str:

        url = html.unescape(
            url
        )

        # DuckDuckGo sometimes returns a redirect URL.

        if (
            url.startswith(
                "//"
            )
        ):

            url = (
                "https:"
                + url
            )

        parsed = urlparse(
            url
        )

        if (
            parsed.scheme
            not in (
                "http",
                "https",
            )
        ):

            return ""

        return url

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
