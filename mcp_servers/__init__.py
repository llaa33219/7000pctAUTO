"""
MCP Servers for 7000%AUTO
Provides external API access to AI agents via Model Context Protocol
"""

from .search_mcp import mcp as search_mcp
from .x_mcp import mcp as x_mcp
from .database_mcp import mcp as database_mcp
from .github_mcp import mcp as github_mcp

__all__ = ['search_mcp', 'x_mcp', 'database_mcp', 'github_mcp']
