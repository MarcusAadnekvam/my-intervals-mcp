"""MCP server exposing Intervals.icu training data to Claude."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .client import IntervalsClient
from .tools import activities, athlete, calendar, wellness


def build() -> MCPServer:
    mcp = MCPServer("intervals-icu")
    client = IntervalsClient()
    for module in (athlete, activities, wellness, calendar):
        module.register(mcp, client)
    return mcp


def main() -> None:
    build().run()


if __name__ == "__main__":
    main()
