"""
Database MCP Server for 7000%AUTO
Provides database operations for idea management
"""

import asyncio
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("Database Server")


@mcp.tool()
async def get_previous_ideas(limit: int = 50) -> dict:
    """
    Get list of previously generated ideas.
    
    Args:
        limit: Maximum number of ideas to return (default 50)
    
    Returns:
        Dictionary with list of ideas
    """
    try:
        from database import get_db, Idea
        from sqlalchemy import select
        
        async with get_db() as session:
            query = select(Idea).order_by(Idea.created_at.desc()).limit(limit)
            result = await session.execute(query)
            ideas = result.scalars().all()
            
            return {
                "success": True,
                "ideas": [
                    {
                        "id": idea.id,
                        "title": idea.title,
                        "description": idea.description[:200],
                        "source": idea.source,
                        "used": idea.used
                    }
                    for idea in ideas
                ],
                "count": len(ideas)
            }
    
    except Exception as e:
        logger.error(f"Error getting previous ideas: {e}")
        return {"success": False, "error": str(e), "ideas": []}


@mcp.tool()
async def check_idea_exists(title: str) -> dict:
    """
    Check if a similar idea already exists.
    
    Args:
        title: Title to check for similarity
    
    Returns:
        Dictionary with exists flag and similar ideas if found
    """
    try:
        from database import get_db, Idea
        from sqlalchemy import select, func
        
        title_lower = title.lower()
        title_words = set(title_lower.split())
        
        async with get_db() as session:
            # Get all ideas for comparison
            query = select(Idea)
            result = await session.execute(query)
            ideas = result.scalars().all()
            
            similar = []
            for idea in ideas:
                idea_title_lower = idea.title.lower()
                idea_words = set(idea_title_lower.split())
                
                # Check exact match
                if title_lower == idea_title_lower:
                    similar.append({
                        "id": idea.id,
                        "title": idea.title,
                        "match_type": "exact"
                    })
                    continue
                
                # Check partial match (title contains or is contained)
                if title_lower in idea_title_lower or idea_title_lower in title_lower:
                    similar.append({
                        "id": idea.id,
                        "title": idea.title,
                        "match_type": "partial"
                    })
                    continue
                
                # Check word overlap (>50%)
                overlap = len(title_words & idea_words)
                total = len(title_words | idea_words)
                if total > 0 and overlap / total > 0.5:
                    similar.append({
                        "id": idea.id,
                        "title": idea.title,
                        "match_type": "similar"
                    })
            
            return {
                "success": True,
                "exists": len(similar) > 0,
                "similar_ideas": similar[:5],
                "count": len(similar)
            }
    
    except Exception as e:
        logger.error(f"Error checking idea existence: {e}")
        return {"success": False, "error": str(e), "exists": False}


@mcp.tool()
async def save_idea(title: str, description: str, source: str) -> dict:
    """
    Save a new idea to the database.
    
    Args:
        title: Idea title
        description: Idea description
        source: Source of the idea (arxiv, reddit, x, hn, ph)
    
    Returns:
        Dictionary with saved idea details
    """
    try:
        from database import create_idea
        
        idea = await create_idea(
            title=title,
            description=description,
            source=source
        )
        
        return {
            "success": True,
            "idea": {
                "id": idea.id,
                "title": idea.title,
                "description": idea.description,
                "source": idea.source,
                "created_at": idea.created_at.isoformat() if idea.created_at else None
            }
        }
    
    except Exception as e:
        logger.error(f"Error saving idea: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_database_stats() -> dict:
    """
    Get database statistics.
    
    Returns:
        Dictionary with database stats
    """
    try:
        from database import get_stats
        
        stats = await get_stats()
        
        return {
            "success": True,
            "stats": stats
        }
    
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run()
