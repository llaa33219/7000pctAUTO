"""
7000%AUTO Database Module
"""

from .models import Base, Idea, Project, AgentLog, IdeaSource, ProjectStatus, LogType

from .db import (
    init_db,
    close_db,
    get_db,
    async_session_factory,
    # Idea operations
    create_idea,
    get_idea_by_id,
    get_unused_ideas,
    mark_idea_used,
    # Project operations
    create_project,
    get_project_by_id,
    get_active_project,
    update_project_status,
    get_project_idea_json,
    get_project_plan_json,
    set_project_idea_json,
    set_project_plan_json,
    # Logging
    add_agent_log,
    get_recent_logs,
    get_project_logs,
    # Stats
    get_stats,
)

__all__ = [
    # Models
    "Base",
    "Idea",
    "Project",
    "AgentLog",
    "IdeaSource",
    "ProjectStatus",
    "LogType",
    # DB operations
    "init_db",
    "close_db",
    "get_db",
    "async_session_factory",
    "create_idea",
    "get_idea_by_id",
    "get_unused_ideas",
    "mark_idea_used",
    "create_project",
    "get_project_by_id",
    "get_active_project",
    "update_project_status",
    "get_project_idea_json",
    "get_project_plan_json",
    "set_project_idea_json",
    "set_project_plan_json",
    "add_agent_log",
    "get_recent_logs",
    "get_project_logs",
    "get_stats",
]
