"""
7000%AUTO Web Dashboard Application

FastAPI application providing a read-only dashboard view of the autonomous AI system.
Features real-time log streaming via SSE and comprehensive system monitoring.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select, func, desc

# Import from project modules (not main to avoid circular imports)
from config import settings
from database import (
    get_db,
    Project,
    ProjectStatus,
    AgentLog,
    LogType,
)
from orchestrator import WorkflowOrchestrator
from orchestrator.state import AgentType


# =============================================================================
# Dashboard FastAPI Application
# =============================================================================

dashboard_app = FastAPI(
    title="7000%AUTO Dashboard",
    description="Read-only monitoring dashboard for the AI automation system",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
)

# CORS for development
dashboard_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# =============================================================================
# Agent Pipeline Definition
# =============================================================================

AGENT_PIPELINE = [
    AgentType.IDEATOR,
    AgentType.PLANNER,
    AgentType.DEVELOPER,
    AgentType.TESTER,
    AgentType.UPLOADER,
    AgentType.EVANGELIST,
]

AGENTS = {
    AgentType.IDEATOR: {
        "name": "Ideator",
        "description": "Generates innovative project ideas and concepts",
        "tools": ["search"],
    },
    AgentType.PLANNER: {
        "name": "Planner",
        "description": "Creates detailed project plans and task breakdowns",
        "tools": ["search", "database"],
    },
    AgentType.DEVELOPER: {
        "name": "Developer",
        "description": "Implements code and technical solutions",
        "tools": ["search", "github", "database"],
    },
    AgentType.TESTER: {
        "name": "Tester",
        "description": "Tests implementations and ensures quality",
        "tools": ["search", "github", "database"],
    },
    AgentType.UPLOADER: {
        "name": "Uploader",
        "description": "Manages code deployment and repository operations",
        "tools": ["github", "database"],
    },
    AgentType.EVANGELIST: {
        "name": "Evangelist",
        "description": "Promotes projects and engages with the community",
        "tools": ["x_api", "search", "database"],
    },
}


# =============================================================================
# Response Models
# =============================================================================

class SystemStatus(BaseModel):
    """Current system status."""
    orchestrator_running: bool
    active_project: Optional[dict] = None
    current_agent: Optional[str] = None
    stats: dict


class ProjectSummary(BaseModel):
    """Project summary for listing."""
    id: str
    name: str
    status: str
    current_agent: Optional[str]
    repo_url: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]


class IdeaSummary(BaseModel):
    """Idea summary from projects."""
    project_id: str
    project_name: str
    idea: dict
    created_at: datetime


# =============================================================================
# Template Loading
# =============================================================================

def get_dashboard_html() -> str:
    """Load and return the dashboard HTML template."""
    template_path = Path(__file__).parent / "templates" / "dashboard.html"
    if template_path.exists():
        return template_path.read_text()
    return """
<!DOCTYPE html>
<html>
<head>
    <title>7000%AUTO Dashboard</title>
    <style>
        body { font-family: system-ui, sans-serif; margin: 40px; background: #1a1a2e; color: #eee; }
        h1 { color: #00d4ff; }
        .status { padding: 20px; background: #16213e; border-radius: 8px; margin: 20px 0; }
        .healthy { border-left: 4px solid #00ff88; }
        .loading { border-left: 4px solid #ffaa00; }
    </style>
</head>
<body>
    <h1>🤖 7000%AUTO Dashboard</h1>
    <div class="status healthy">
        <h2>System Status</h2>
        <p>Dashboard is running. Connect to <a href="/dashboard/api/status" style="color: #00d4ff;">/dashboard/api/status</a> for live data.</p>
    </div>
    <div class="status loading">
        <h2>API Endpoints</h2>
        <ul>
            <li><a href="/dashboard/api/status" style="color: #00d4ff;">GET /api/status</a> - System status</li>
            <li><a href="/dashboard/api/projects" style="color: #00d4ff;">GET /api/projects</a> - List projects</li>
            <li><a href="/dashboard/api/ideas" style="color: #00d4ff;">GET /api/ideas</a> - List ideas</li>
            <li><a href="/dashboard/api/agents" style="color: #00d4ff;">GET /api/agents</a> - List agents</li>
            <li><a href="/dashboard/api/logs/stream" style="color: #00d4ff;">GET /api/logs/stream</a> - SSE log stream</li>
        </ul>
    </div>
</body>
</html>
"""


# =============================================================================
# Helper to get orchestrator reference
# =============================================================================

def get_orchestrator() -> Optional[WorkflowOrchestrator]:
    """
    Get the orchestrator instance from the main module.
    Returns None if not available (avoids circular import at module load time).
    """
    try:
        import main
        return getattr(main, 'orchestrator', None)
    except (ImportError, AttributeError):
        return None


# =============================================================================
# API Endpoints
# =============================================================================

@dashboard_app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the main dashboard HTML page."""
    return HTMLResponse(content=get_dashboard_html())


@dashboard_app.get("/health")
async def health_check():
    """Health check endpoint."""
    db_status = "healthy"
    try:
        async with get_db() as session:
            await session.execute(select(func.count()).select_from(Project))
    except RuntimeError:
        # Database not initialized yet - this is OK during startup
        db_status = "initializing"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    orchestrator = get_orchestrator()
    orchestrator_status = "running" if (orchestrator and orchestrator.is_running) else "stopped"
    
    return {
        "status": "healthy" if db_status in ("healthy", "initializing") else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
        "orchestrator": orchestrator_status,
        "version": "1.0.0"
    }


@dashboard_app.get("/api/status")
async def get_system_status():
    """Get current system status including active project and stats."""
    orchestrator = get_orchestrator()
    
    try:
        async with get_db() as session:
            # Get active project (in progress)
            active_statuses = [
                ProjectStatus.IDEATION.value,
                ProjectStatus.PLANNING.value,
                ProjectStatus.DEVELOPMENT.value,
                ProjectStatus.TESTING.value,
                ProjectStatus.UPLOADING.value,
                ProjectStatus.PROMOTING.value,
            ]
            
            result = await session.execute(
                select(Project)
                .where(Project.status.in_(active_statuses))
                .order_by(Project.updated_at.desc())
                .limit(1)
            )
            active_project = result.scalar_one_or_none()
            
            # Get stats
            total_result = await session.execute(select(func.count()).select_from(Project))
            total_projects = total_result.scalar() or 0
            
            completed_result = await session.execute(
                select(func.count())
                .select_from(Project)
                .where(Project.status == ProjectStatus.COMPLETED.value)
            )
            completed_projects = completed_result.scalar() or 0
            
            failed_result = await session.execute(
                select(func.count())
                .select_from(Project)
                .where(Project.status == ProjectStatus.FAILED.value)
            )
            failed_projects = failed_result.scalar() or 0
            
            # Get dev-tester iteration count from logs
            iteration_result = await session.execute(
                select(func.count())
                .select_from(AgentLog)
                .where(AgentLog.agent_name == "tester")
            )
            tester_iterations = iteration_result.scalar() or 0
            
            active_project_data = None
            if active_project:
                active_project_data = {
                    "id": active_project.id,
                    "name": active_project.name,
                    "status": active_project.status.value if hasattr(active_project.status, 'value') else active_project.status,
                    "created_at": active_project.created_at.isoformat() if active_project.created_at else None,
                    "updated_at": active_project.updated_at.isoformat() if active_project.updated_at else None,
                }
            
            return {
                "orchestrator_running": orchestrator.is_running if orchestrator else False,
                "active_project": active_project_data,
                "stats": {
                    "total_projects": total_projects,
                    "completed_projects": completed_projects,
                    "failed_projects": failed_projects,
                    "in_progress": total_projects - completed_projects - failed_projects,
                    "dev_tester_iterations": tester_iterations,
                }
            }
    except RuntimeError:
        # Database not initialized yet
        return {
            "orchestrator_running": orchestrator.is_running if orchestrator else False,
            "active_project": None,
            "stats": {
                "total_projects": 0,
                "completed_projects": 0,
                "failed_projects": 0,
                "in_progress": 0,
                "dev_tester_iterations": 0,
            },
            "database_status": "initializing"
        }


@dashboard_app.get("/api/projects")
async def list_projects(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None
):
    """List all projects with pagination."""
    try:
        async with get_db() as session:
            query = select(Project)
            count_query = select(func.count()).select_from(Project)
            
            if status:
                query = query.where(Project.status == status)
                count_query = count_query.where(Project.status == status)
            
            # Get total count
            total_result = await session.execute(count_query)
            total = total_result.scalar() or 0
            
            # Get paginated results
            offset = (page - 1) * per_page
            query = query.order_by(desc(Project.created_at)).offset(offset).limit(per_page)
            
            result = await session.execute(query)
            projects = result.scalars().all()
            
            return {
                "projects": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "status": p.status.value if hasattr(p.status, 'value') else p.status,
                        "github_url": p.github_url,
                        "x_post_url": p.x_post_url,
                        "created_at": p.created_at.isoformat() if p.created_at else None,
                        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                    }
                    for p in projects
                ],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page if per_page > 0 else 0
                }
            }
    except RuntimeError:
        return {"projects": [], "pagination": {"page": 1, "per_page": per_page, "total": 0, "pages": 0}, "database_status": "initializing"}


@dashboard_app.get("/api/projects/{project_id}")
async def get_project(project_id: int):
    """Get detailed information for a single project."""
    try:
        async with get_db() as session:
            result = await session.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()
            
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            # Get logs for this project
            logs_result = await session.execute(
                select(AgentLog)
                .where(AgentLog.project_id == project_id)
                .order_by(desc(AgentLog.created_at))
                .limit(50)
            )
            logs = logs_result.scalars().all()
            
            return {
                "id": project.id,
                "idea_id": project.idea_id,
                "name": project.name,
                "status": project.status.value if hasattr(project.status, 'value') else project.status,
                "plan_json": project.plan_json,
                "github_url": project.github_url,
                "x_post_url": project.x_post_url,
                "dev_test_iterations": project.dev_test_iterations,
                "created_at": project.created_at.isoformat() if project.created_at else None,
                "updated_at": project.updated_at.isoformat() if project.updated_at else None,
                "logs": [
                    {
                        "id": log.id,
                        "agent_name": log.agent_name,
                        "message": log.message,
                        "log_type": log.log_type.value if hasattr(log.log_type, 'value') else log.log_type,
                        "created_at": log.created_at.isoformat() if log.created_at else None,
                    }
                    for log in logs
                ]
            }
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Database not initialized")


@dashboard_app.get("/api/ideas")
async def list_ideas(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100)
):
    """List all generated ideas."""
    from database import Idea
    
    try:
        async with get_db() as session:
            query = select(Idea)
            count_query = select(func.count()).select_from(Idea)
            
            # Get total count
            total_result = await session.execute(count_query)
            total = total_result.scalar() or 0
            
            # Get paginated results
            offset = (page - 1) * per_page
            query = query.order_by(desc(Idea.created_at)).offset(offset).limit(per_page)
            
            result = await session.execute(query)
            ideas = result.scalars().all()
            
            return {
                "ideas": [
                    {
                        "id": idea.id,
                        "title": idea.title,
                        "description": idea.description,
                        "source": idea.source.value if hasattr(idea.source, 'value') else idea.source,
                        "used": idea.used,
                        "created_at": idea.created_at.isoformat() if idea.created_at else None,
                    }
                    for idea in ideas
                ],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page if per_page > 0 else 0
                }
            }
    except RuntimeError:
        return {"ideas": [], "pagination": {"page": 1, "per_page": per_page, "total": 0, "pages": 0}, "database_status": "initializing"}


@dashboard_app.get("/api/logs/stream")
async def stream_logs():
    """SSE endpoint for real-time agent log streaming."""
    
    async def event_generator() -> AsyncGenerator[dict, None]:
        """Generate SSE events from agent logs."""
        last_log_id: Optional[int] = None
        
        while True:
            try:
                orchestrator = get_orchestrator()
                
                async with get_db() as session:
                    # Get new logs since last check
                    query = select(AgentLog).order_by(desc(AgentLog.created_at)).limit(10)
                    
                    if last_log_id:
                        query = select(AgentLog).where(
                            AgentLog.id > last_log_id
                        ).order_by(AgentLog.created_at).limit(10)
                    
                    result = await session.execute(query)
                    logs = result.scalars().all()
                    
                    for log in logs:
                        log_data = {
                            "id": log.id,
                            "project_id": log.project_id,
                            "agent_name": log.agent_name,
                            "message": log.message,
                            "log_type": log.log_type.value if hasattr(log.log_type, 'value') else str(log.log_type),
                            "timestamp": log.created_at.isoformat() if log.created_at else None,
                        }
                        
                        yield {
                            "event": "log",
                            "data": json.dumps({
                                "type": log.log_type.value if hasattr(log.log_type, 'value') else "info",
                                "log": log_data
                            })
                        }
                        
                        last_log_id = log.id
                    
                    # Send current system status
                    yield {
                        "event": "status",
                        "data": json.dumps({
                            "orchestrator_running": orchestrator.is_running if orchestrator else False,
                            "timestamp": datetime.utcnow().isoformat(),
                        })
                    }
                    
            except RuntimeError:
                # Database not initialized
                yield {
                    "event": "status",
                    "data": json.dumps({
                        "orchestrator_running": False,
                        "database_status": "initializing",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                }
            except Exception as e:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": str(e)})
                }
            
            # Wait before checking for new logs
            await asyncio.sleep(2)
    
    return EventSourceResponse(event_generator())


@dashboard_app.get("/api/agents")
async def list_agents():
    """List all agents in the pipeline."""
    return {
        "agents": [
            {
                "id": agent_type.value,
                "name": AGENTS[agent_type]["name"],
                "description": AGENTS[agent_type]["description"],
                "tools": AGENTS[agent_type]["tools"],
                "order": idx + 1
            }
            for idx, agent_type in enumerate(AGENT_PIPELINE)
        ],
        "pipeline": [agent.value for agent in AGENT_PIPELINE]
    }


# Alias for mounting
app = dashboard_app
