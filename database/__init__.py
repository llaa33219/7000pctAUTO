"""
7000%AUTO Database Module
SQLAlchemy async models and database operations
"""

from .models import Base, Idea, Project, AgentLog, IdeaSource, ProjectStatus, LogType
from .db import (
    init_db, close_db, get_db, async_session_factory,
    create_idea, get_idea_by_id, get_unused_ideas, mark_idea_used,
    create_project, get_project_by_id, update_project_status, get_active_project,
    add_agent_log, get_recent_logs, get_project_logs, get_stats
)

__all__ = [
    # Models
    'Base', 'Idea', 'Project', 'AgentLog',
    # Enums
    'IdeaSource', 'ProjectStatus', 'LogType',
    # Lifecycle
    'init_db', 'close_db', 'get_db', 'async_session_factory',
    # Ideas
    'create_idea', 'get_idea_by_id', 'get_unused_ideas', 'mark_idea_used',
    # Projects
    'create_project', 'get_project_by_id', 'update_project_status', 'get_active_project',
    # Logs
    'add_agent_log', 'get_recent_logs', 'get_project_logs',
    # Stats
    'get_stats'
]
