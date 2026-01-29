"""
7000%AUTO Web Dashboard
Real-time monitoring dashboard for the autonomous AI system.
Read-only interface with SSE streaming for live updates.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict, Any, List
from collections import deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse


# =============================================================================
# Global Event System for SSE
# =============================================================================

class EventBroadcaster:
    """
    Broadcasts events to all connected SSE clients.
    Thread-safe event distribution system.
    """
    
    def __init__(self, max_history: int = 100):
        self._subscribers: List[asyncio.Queue] = []
        self._history: deque = deque(maxlen=max_history)
        self._lock = asyncio.Lock()
        self._current_state: Dict[str, Any] = {}
    
    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to events. Returns a queue to receive events."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers.append(queue)
            # Send recent history to new subscriber
            for event in self._history:
                await queue.put(event)
        return queue
    
    async def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from events."""
        async with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)
    
    async def broadcast(self, event: Dict[str, Any]):
        """Broadcast an event to all subscribers."""
        event["timestamp"] = datetime.utcnow().isoformat()
        async with self._lock:
            self._history.append(event)
            dead_subscribers = []
            for q in self._subscribers:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    dead_subscribers.append(q)
            for dead in dead_subscribers:
                self._subscribers.remove(dead)
        
        # Update current state tracking
        if event.get("type") in ("agent_started", "status", "heartbeat"):
            self._current_state.update(event)
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get recent event history."""
        return list(self._history)


# Global event broadcaster
event_broadcaster = EventBroadcaster()


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="7000%AUTO Dashboard",
    description="Real-time monitoring dashboard for the AI automation system",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)

# CORS middleware
app.add_middleware(
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
    {"id": "ideator", "name": "Ideator", "icon": "💡", "description": "Generates innovative project ideas"},
    {"id": "planner", "name": "Planner", "icon": "📋", "description": "Creates detailed implementation plans"},
    {"id": "developer", "name": "Developer", "icon": "👨‍💻", "description": "Implements code and solutions"},
    {"id": "tester", "name": "Tester", "icon": "🧪", "description": "Tests and validates implementations"},
    {"id": "uploader", "name": "Uploader", "icon": "🚀", "description": "Uploads to Gitea repository"},
    {"id": "evangelist", "name": "Evangelist", "icon": "📣", "description": "Promotes on social media"},
]


# =============================================================================
# Template Loading
# =============================================================================

def get_dashboard_html() -> str:
    """Load and return the dashboard HTML template."""
    template_path = Path(__file__).parent / "templates" / "dashboard.html"
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return "<html><body><h1>Dashboard template not found</h1></body></html>"


# =============================================================================
# Helper Functions
# =============================================================================

def get_orchestrator():
    """Get the orchestrator instance from main module."""
    try:
        import main
        return getattr(main, 'orchestrator', None)
    except (ImportError, AttributeError):
        return None


async def get_system_status_async() -> Dict[str, Any]:
    """Get current system status (async version)."""
    orchestrator = get_orchestrator()
    
    status = {
        "orchestrator_running": False,
        "current_agent": None,
        "current_project": None,
        "dev_test_iterations": 0,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    if orchestrator:
        status["orchestrator_running"] = orchestrator.is_running
        
        if hasattr(orchestrator, 'state_manager'):
            try:
                active_state = await orchestrator.state_manager.get_active_state()
                if active_state:
                    status["current_agent"] = active_state.current_agent
                    status["current_project"] = {
                        "id": active_state.project_id,
                        "status": active_state.status,
                        "name": active_state.plan.get("project_name") if active_state.plan else None,
                    }
                    status["dev_test_iterations"] = active_state.dev_test_iterations
            except Exception:
                pass
    
    return status


async def get_database_stats() -> Dict[str, Any]:
    """Get statistics from database."""
    try:
        from database.db import get_db, get_stats
        from database.models import Project, AgentLog, ProjectStatus
        from sqlalchemy import select, func, desc
        
        async with get_db() as session:
            # Get stats
            stats = await get_stats(session)
            
            # Get recent logs
            result = await session.execute(
                select(AgentLog)
                .order_by(desc(AgentLog.created_at))
                .limit(50)
            )
            logs = result.scalars().all()
            
            # Get active project
            active_result = await session.execute(
                select(Project)
                .where(Project.status.notin_([
                    ProjectStatus.COMPLETED.value,
                    ProjectStatus.FAILED.value
                ]))
                .order_by(desc(Project.created_at))
                .limit(1)
            )
            active_project = active_result.scalar_one_or_none()
            
            return {
                "stats": stats,
                "recent_logs": [
                    {
                        "id": log.id,
                        "project_id": log.project_id,
                        "agent_name": log.agent_name,
                        "message": log.message,
                        "log_type": log.log_type,
                        "timestamp": log.created_at.isoformat() if log.created_at else None,
                    }
                    for log in logs
                ],
                "active_project": {
                    "id": active_project.id,
                    "name": active_project.name,
                    "status": active_project.status,
                    "current_agent": active_project.current_agent,
                    "dev_test_iterations": active_project.dev_test_iterations,
                } if active_project else None,
            }
    except Exception as e:
        return {
            "stats": {"total_ideas": 0, "total_projects": 0, "completed_projects": 0},
            "recent_logs": [],
            "active_project": None,
            "error": str(e),
        }


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the main dashboard HTML page."""
    return HTMLResponse(content=get_dashboard_html())


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/status")
async def get_status():
    """Get current system status and database stats."""
    system_status = await get_system_status_async()
    db_data = await get_database_stats()
    
    return {
        **system_status,
        **db_data,
        "agents": AGENT_PIPELINE,
    }


@app.get("/api/stream")
async def stream_events(request: Request):
    """SSE endpoint for real-time event streaming."""
    
    async def event_generator() -> AsyncGenerator[dict, None]:
        queue = await event_broadcaster.subscribe()
        
        try:
            # Send initial status
            status = await get_system_status_async()
            yield {
                "event": "status",
                "data": json.dumps(status),
            }
            
            # Send initial database data
            db_data = await get_database_stats()
            yield {
                "event": "init",
                "data": json.dumps(db_data),
            }
            
            # Stream events
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(queue.get(), timeout=5.0)
                    yield {
                        "event": event.get("type", "message"),
                        "data": json.dumps(event),
                    }
                except asyncio.TimeoutError:
                    # Send heartbeat/status update
                    status = await get_system_status_async()
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps(status),
                    }
                    
        finally:
            await event_broadcaster.unsubscribe(queue)
    
    return EventSourceResponse(event_generator())


@app.get("/api/logs")
async def get_logs():
    """Get recent logs from database."""
    db_data = await get_database_stats()
    return {
        "logs": db_data.get("recent_logs", []),
    }


@app.get("/api/agents")
async def get_agents():
    """Get agent pipeline definition."""
    return {
        "agents": AGENT_PIPELINE,
    }


# =============================================================================
# Event Broadcasting Helper
# =============================================================================

async def broadcast_event(event_type: str, agent: Optional[str] = None, 
                          message: str = "", data: Optional[Dict] = None):
    """
    Broadcast an event to all SSE clients.
    Called from the orchestrator to push real-time updates.
    """
    await event_broadcaster.broadcast({
        "type": event_type,
        "agent": agent,
        "message": message,
        "data": data or {},
    })


# Expose for external use
__all__ = ["app", "event_broadcaster", "broadcast_event"]
