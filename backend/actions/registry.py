"""
Tool registry: central place to register and execute action tools.
"""
from __future__ import annotations

import logging
from typing import Callable, Awaitable

from gateway.contracts import ToolCallResult

logger = logging.getLogger(__name__)


class ToolSpec:
    """Definition of a single tool."""
    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable[..., Awaitable[ToolCallResult]],
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler

    def schema_text(self) -> str:
        params = ", ".join(f"{k}: {v}" for k, v in self.parameters.items())
        return f"- {self.name}({params}) — {self.description}"


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec):
        self._tools[spec.name] = spec
        logger.info(f"Registered tool: {spec.name}")

    def get_schemas_text(self) -> str:
        if not self._tools:
            return "No tools available."
        return "\n".join(spec.schema_text() for spec in self._tools.values())

    async def execute(self, tool_name: str, args: dict) -> ToolCallResult:
        spec = self._tools.get(tool_name)
        if not spec:
            return ToolCallResult(
                tool_name=tool_name,
                success=False,
                error=f"Unknown tool: {tool_name}",
            )
        try:
            result = await spec.handler(**args)
            return result
        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}")
            return ToolCallResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
            )

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _register_builtin_tools(_registry)
    return _registry


def _register_builtin_tools(registry: ToolRegistry):
    from actions.web_search import web_search_tool
    from actions.schedule_message import schedule_message_tool
    from actions.generate_image import generate_image_tool

    registry.register(web_search_tool)
    registry.register(schedule_message_tool)
    registry.register(generate_image_tool)
