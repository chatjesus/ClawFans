"""
Food Search Action — helps character find food delivery options.

角色可以帮用户搜索外卖/餐厅，返回相关结果供角色引用。
支持关键词 + 地区搜索，优先搜索美团/饿了么。
"""
import httpx
import logging
from html.parser import HTMLParser

from gateway.contracts import ToolCallResult
from actions.registry import ToolSpec

logger = logging.getLogger(__name__)


class _DDGParser(HTMLParser):
    """Parse DuckDuckGo HTML search results."""
    def __init__(self):
        super().__init__()
        self.results: list[dict] = []
        self._in_result = False
        self._current: dict = {}

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "a" and "result__a" in attrs_dict.get("class", ""):
            self._in_result = True
            self._current = {"url": attrs_dict.get("href", ""), "title": ""}

    def handle_data(self, data):
        if self._in_result and "title" in self._current:
            self._current["title"] += data.strip()

    def handle_endtag(self, tag):
        if tag == "a" and self._in_result:
            if self._current.get("title"):
                self.results.append(dict(self._current))
            self._in_result = False


async def _food_search(keyword: str, city: str = "") -> ToolCallResult:
    """
    Search for food delivery options.

    Args:
        keyword: Food type or restaurant name (e.g. "麻辣烫", "奶茶", "寿司")
        city:    City or district (e.g. "北京朝阳区", "上海静安区")
    """
    location = city.strip() if city else ""
    if location:
        query = f"{location} {keyword} 外卖 推荐 美团"
    else:
        query = f"{keyword} 外卖 推荐 美团"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
            )
            resp.raise_for_status()

        parser = _DDGParser()
        parser.feed(resp.text)
        results = parser.results[:5]

        if not results:
            return ToolCallResult(
                tool_name="food_search",
                success=True,
                output=f"没有找到关于「{keyword}」的外卖信息，建议直接在美团或饿了么App搜索。",
            )

        lines = [f"搜索「{query}」的结果："]
        for i, r in enumerate(results, 1):
            title = r.get("title", "").strip()
            url = r.get("url", "").strip()
            if title:
                lines.append(f"{i}. {title}")
                if url and ("meituan" in url or "ele.me" in url or "dianping" in url):
                    lines.append(f"   链接: {url}")

        # Add helpful app links
        encoded_kw = keyword.replace(" ", "+")
        lines.append(f"\n美团搜索链接: https://www.meituan.com/search/{encoded_kw}/")
        lines.append(f"饿了么搜索链接: https://www.ele.me/search?q={encoded_kw}")

        return ToolCallResult(
            tool_name="food_search",
            success=True,
            output="\n".join(lines),
        )

    except Exception as e:
        logger.error(f"food_search failed: {e}")
        return ToolCallResult(
            tool_name="food_search",
            success=False,
            error=str(e),
        )


food_search_tool = ToolSpec(
    name="food_search",
    description="Search for food delivery options, restaurants, or takeout near a location. Use when user asks to order food or find restaurants.",
    parameters={
        "keyword": "string (food type or dish name, e.g. '麻辣烫', '奶茶', '炸鸡')",
        "city": "string (optional, city/district e.g. '北京朝阳区')",
    },
    handler=_food_search,
)
