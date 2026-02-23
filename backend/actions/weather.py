"""
Weather Action — check current weather for a city.
"""
import httpx
import logging
from html.parser import HTMLParser

from gateway.contracts import ToolCallResult
from actions.registry import ToolSpec

logger = logging.getLogger(__name__)


async def _weather(city: str) -> ToolCallResult:
    """
    Get current weather for a city.
    Args:
        city: City name (e.g. "北京", "上海", "成都")
    """
    query = f"{city} 今天天气预报"
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
            )
            resp.raise_for_status()

        # Extract answer box if available
        class WeatherParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.snippets: list[str] = []
                self._in_snippet = False
                self._buf = ""

            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                cls = attrs_dict.get("class", "")
                if tag in ("div", "span", "a") and any(
                    k in cls for k in ["result__snippet", "result__body", "zci-wrapper"]
                ):
                    self._in_snippet = True
                    self._buf = ""

            def handle_data(self, data):
                if self._in_snippet:
                    self._buf += data

            def handle_endtag(self, tag):
                if self._in_snippet and tag in ("div", "span", "a"):
                    text = self._buf.strip()
                    if text and len(text) > 10:
                        self.snippets.append(text)
                    self._in_snippet = False

        parser = WeatherParser()
        parser.feed(resp.text)

        if parser.snippets:
            summary = parser.snippets[0][:300]
        else:
            summary = f"未能获取{city}的天气详情，请查看天气App或搜索「{city}天气」。"

        return ToolCallResult(
            tool_name="weather",
            success=True,
            output=f"{city}天气：{summary}",
        )

    except Exception as e:
        logger.error(f"weather check failed: {e}")
        return ToolCallResult(
            tool_name="weather",
            success=False,
            error=str(e),
        )


weather_tool = ToolSpec(
    name="weather",
    description="Check current weather for a city. Use when user asks about weather or what to wear.",
    parameters={
        "city": "string (city name, e.g. '北京', '上海', '成都')",
    },
    handler=_weather,
)
