"""
MCP Servers for 7000%AUTO
Provides external API access to AI agents via Model Context Protocol
"""

from .search_mcp import mcp as search_mcp
from .x_mcp import mcp as x_mcp
from .database_mcp import mcp as database_mcp
from .gitea_mcp import mcp as gitea_mcp

__all__ = ['search_mcp', 'x_mcp', 'database_mcp', 'gitea_mcp']
