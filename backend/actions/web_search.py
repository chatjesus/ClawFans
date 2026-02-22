"""
Web search tool: performs a web search and returns summarized results.
Uses DuckDuckGo as a free, no-API-key search backend.
"""
import httpx
import logging

from gateway.contracts import ToolCallResult
from actions.registry import ToolSpec

logger = logging.getLogger(__name__)


async def _web_search(query: str, max_results: int = 5) -> ToolCallResult:
    """Execute a web search via DuckDuckGo HTML endpoint."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()
            from html.parser import HTMLParser

            class DDGParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.results = []
                    self._in_result = False
                    self._current = {}

                def handle_starttag(self, tag, attrs):
                    attrs_dict = dict(attrs)
                    if tag == "a" and "result__a" in attrs_dict.get("class", ""):
                        self._in_result = True
                        self._current = {"url": attrs_dict.get("href", ""), "title": ""}
                    if tag == "a" and "result__snippet" in attrs_dict.get("class", ""):
                        self._current["snippet"] = ""

                def handle_data(self, data):
                    if self._in_result and "title" in self._current:
                        self._current["title"] += data.strip()

                def handle_endtag(self, tag):
                    if tag == "a" and self._in_result:
                        if self._current.get("title"):
                            self.results.append(self._current)
                        self._in_result = False

            parser = DDGParser()
            parser.feed(resp.text)

            results = parser.results[:max_results]
            if not results:
                return ToolCallResult(
                    tool_name="web_search",
                    success=True,
                    output=f"No results found for: {query}",
                )

            output_lines = [f"Search results for '{query}':"]
            for i, r in enumerate(results, 1):
                output_lines.append(f"{i}. {r.get('title', 'No title')} — {r.get('url', '')}")

            return ToolCallResult(
                tool_name="web_search",
                success=True,
                output="\n".join(output_lines),
            )

    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return ToolCallResult(
            tool_name="web_search",
            success=False,
            error=str(e),
        )


web_search_tool = ToolSpec(
    name="web_search",
    description="Search the web for real-time information",
    parameters={"query": "string (search query)"},
    handler=_web_search,
)
