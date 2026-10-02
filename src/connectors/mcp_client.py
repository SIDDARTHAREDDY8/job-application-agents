"""Generic MCP client: plug ANY MCP server into the agents.

MCP (Model Context Protocol) servers expose tools over stdio or HTTP/SSE.
This wrapper lets agents call those tools without caring which server it is.

Examples
--------
Playwright MCP (browser automation via someone else's server):

    client = MCPClient.from_config({
        "command": "npx", "args": ["-y", "@playwright/mcp@latest"],
    })
    tools = client.list_tools_sync()
    client.call_tool_sync("browser_navigate", {"url": "https://example.com"})

Gmail MCP / custom tools work the same way - list_tools() tells you what the
server offers, then call_tool() invokes them.

Configure servers in .env as JSON:

    MCP_SERVERS={"playwright": {"command": "npx", "args": ["-y", "@playwright/mcp@latest"]},
                 "mytools": {"url": "http://localhost:8000/sse"}}
"""

from __future__ import annotations
import asyncio
import json
import os
from typing import Any


class MCPClient:
    """One connection to one MCP server (stdio or SSE)."""

    def __init__(self, name: str = "mcp", command: str | None = None,
                 args: list[str] | None = None, env: dict[str, str] | None = None,
                 url: str | None = None):
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env
        self.url = url
        self._session = None
        self._stack = None

    # ------------------------------------------------------------------ config
    @classmethod
    def from_config(cls, name: str, cfg: dict[str, Any]) -> "MCPClient":
        return cls(name=name, command=cfg.get("command"), args=cfg.get("args"),
                   env=cfg.get("env"), url=cfg.get("url"))

    @classmethod
    def from_env(cls, name: str) -> "MCPClient":
        """Read one server from MCP_SERVERS JSON in .env."""
        servers = json.loads(os.getenv("MCP_SERVERS", "{}"))
        if name not in servers:
            raise KeyError(f"MCP server '{name}' not in MCP_SERVERS. "
                           f"Available: {sorted(servers)}")
        return cls.from_config(name, servers[name])

    @classmethod
    def all_from_env(cls) -> dict[str, "MCPClient"]:
        servers = json.loads(os.getenv("MCP_SERVERS", "{}"))
        return {n: cls.from_config(n, c) for n, c in servers.items()}

    # ------------------------------------------------------------------ lifecycle
    async def connect(self) -> "MCPClient":
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            from mcp.client.sse import sse_client
        except ImportError as e:
            raise ImportError("MCP support needs: pip install mcp") from e

        from contextlib import AsyncExitStack
        stack = AsyncExitStack()
        self._stack = stack
        if self.url:
            read, write = await stack.enter_async_context(sse_client(self.url))
        else:
            if not self.command:
                raise ValueError(f"MCP server '{self.name}': need 'command' (stdio) or 'url' (SSE)")
            params = StdioServerParameters(command=self.command, args=self.args,
                                           env=self.env)
            read, write = await stack.enter_async_context(stdio_client(params))
        self._session = await stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        return self

    async def close(self) -> None:
        if getattr(self, "_stack", None):
            await self._stack.aclose()
            self._stack = None
            self._session = None

    async def _ensure(self):
        if self._session is None:
            await self.connect()
        return self._session

    # ------------------------------------------------------------------ tools
    async def list_tools(self) -> list[dict[str, Any]]:
        s = await self._ensure()
        tools = await s.list_tools()
        return [{"name": t.name, "description": t.description,
                 "inputSchema": t.inputSchema} for t in tools.tools]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        s = await self._ensure()
        result = await s.call_tool(tool_name, arguments)
        # Flatten MCP content blocks to plain values
        out = []
        for block in getattr(result, "content", []):
            if getattr(block, "type", None) == "text":
                out.append(block.text)
            else:
                out.append(str(block))
        return "\n".join(out) if out else result

    # ------------------------------------------------------------------ sync sugar
    def _run(self, coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        raise RuntimeError(
            "MCPClient sync helpers can't run inside an existing event loop; "
            "use the async methods (connect/list_tools/call_tool) instead."
        )

    def list_tools_sync(self) -> list[dict[str, Any]]:
        return self._run(self.list_tools())

    def call_tool_sync(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        return self._run(self.call_tool(tool_name, arguments))

    def describe_sync(self) -> str:
        """One-line-per-tool summary, handy for stuffing into an agent prompt."""
        lines = []
        for t in self.list_tools_sync():
            lines.append(f"- {t['name']}: {(t['description'] or '').strip()[:120]}")
        return f"MCP server '{self.name}' tools:\n" + "\n".join(lines)
