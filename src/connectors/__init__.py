"""Connectors package: Gmail sending and generic MCP access."""
from .gmail import GmailSender
from .mcp_client import MCPClient

__all__ = ["GmailSender", "MCPClient"]
