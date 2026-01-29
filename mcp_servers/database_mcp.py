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


@mcp.tool()
async def submit_idea(
    project_id: int,
    title: str,
    description: str,
    source: str,
    tech_stack: list[str] = None,
    target_audience: str = None,
    key_features: list[str] = None,
    complexity: str = None,
    estimated_time: str = None,
    inspiration: str = None
) -> dict:
    """
    Submit a generated project idea. Use this tool to finalize and save your idea.
    The idea will be saved directly to the database for the given project.
    
    Args:
        project_id: The project ID to associate this idea with (required)
        title: Short project name (required)
        description: Detailed description of the project (required)
        source: Source of inspiration - arxiv, reddit, x, hn, or ph (required)
        tech_stack: List of technologies to use (e.g., ["python", "fastapi"])
        target_audience: Who would use this project
        key_features: List of key features
        complexity: low, medium, or high
        estimated_time: Estimated implementation time (e.g., "2-4 hours")
        inspiration: Brief note on what inspired this idea
    
    Returns:
        Dictionary with success status
    """
    try:
        from database.db import set_project_idea_json
        
        # Build the complete idea dict
        idea_data = {
            "title": title,
            "description": description,
            "source": source,
            "tech_stack": tech_stack or [],
            "target_audience": target_audience or "",
            "key_features": key_features or [],
            "complexity": complexity or "medium",
            "estimated_time": estimated_time or "",
            "inspiration": inspiration or "",
        }
        
        # Save to database
        success = await set_project_idea_json(project_id, idea_data)
        
        if success:
            logger.info(f"Idea submitted for project {project_id}: {title}")
            return {"success": True, "message": f"Idea '{title}' saved successfully"}
        else:
            logger.error(f"Project {project_id} not found")
            return {"success": False, "error": f"Project {project_id} not found"}
    
    except Exception as e:
        logger.error(f"Error submitting idea: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def submit_plan(
    project_id: int,
    project_name: str,
    overview: str,
    display_name: str = None,
    tech_stack: dict = None,
    file_structure: dict = None,
    features: list[dict] = None,
    implementation_steps: list[dict] = None,
    testing_strategy: dict = None,
    configuration: dict = None,
    error_handling: dict = None,
    readme_sections: list[str] = None
) -> dict:
    """
    Submit an implementation plan. Use this tool to finalize your project plan.
    The plan will be saved directly to the database for the given project.
    
    Args:
        project_id: The project ID to associate this plan with (required)
        project_name: kebab-case project name (required)
        overview: 2-3 sentence summary of what will be built (required)
        display_name: Human readable project name
        tech_stack: Technology stack details with language, runtime, framework, key_dependencies
        file_structure: File structure with root_files and directories
        features: List of features with name, priority, description, implementation_notes
        implementation_steps: Ordered list of implementation steps
        testing_strategy: Testing approach with unit_tests, integration_tests, test_files, test_commands
        configuration: Config details with env_variables and config_files
        error_handling: Error handling strategies
        readme_sections: List of README section titles
    
    Returns:
        Dictionary with success status
    """
    try:
        from database.db import set_project_plan_json
        
        # Build the complete plan dict
        plan_data = {
            "project_name": project_name,
            "display_name": display_name or project_name.replace("-", " ").title(),
            "overview": overview,
            "tech_stack": tech_stack or {},
            "file_structure": file_structure or {},
            "features": features or [],
            "implementation_steps": implementation_steps or [],
            "testing_strategy": testing_strategy or {},
            "configuration": configuration or {},
            "error_handling": error_handling or {},
            "readme_sections": readme_sections or []
        }
        
        # Save to database
        success = await set_project_plan_json(project_id, plan_data)
        
        if success:
            logger.info(f"Plan submitted for project {project_id}: {project_name}")
            return {"success": True, "message": f"Plan '{project_name}' saved successfully"}
        else:
            logger.error(f"Project {project_id} not found")
            return {"success": False, "error": f"Project {project_id} not found"}
    
    except Exception as e:
        logger.error(f"Error submitting plan: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run()
