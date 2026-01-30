"""
7000%AUTO Database Operations
Async SQLAlchemy database setup and CRUD operations
"""

import logging
from typing import Optional, List
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, func

from .models import Base, Idea, Project, AgentLog, IdeaSource, ProjectStatus, LogType

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine = None
_session_factory = None


def async_session_factory():
    """Get the async session factory for direct use"""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _session_factory()


async def init_db(database_url: Optional[str] = None):
    """Initialize database engine and create tables"""
    global _engine, _session_factory
    
    if database_url is None:
        from config import settings
        database_url = settings.DATABASE_URL
    
    # Convert postgres:// to postgresql+asyncpg:// if needed
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://") and "+asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    _engine = create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True
    )
    
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    # Create tables
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database initialized successfully")


async def close_db():
    """Close database connection"""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connection closed")


@asynccontextmanager
async def get_db():
    """Get database session context manager"""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# =============================================================================
# Idea CRUD Operations
# =============================================================================

async def create_idea(
    title: str,
    description: str,
    source: str,
    session: Optional[AsyncSession] = None
) -> Idea:
    """Create a new idea"""
    async def _create(s: AsyncSession) -> Idea:
        idea = Idea(
            title=title,
            description=description,
            source=source if isinstance(source, str) else source.value
        )
        s.add(idea)
        await s.flush()
        await s.refresh(idea)
        return idea
    
    if session:
        return await _create(session)
    else:
        async with get_db() as s:
            return await _create(s)


async def get_idea_by_id(idea_id: int, session: Optional[AsyncSession] = None) -> Optional[Idea]:
    """Get idea by ID"""
    async def _get(s: AsyncSession) -> Optional[Idea]:
        result = await s.execute(select(Idea).where(Idea.id == idea_id))
        return result.scalar_one_or_none()
    
    if session:
        return await _get(session)
    else:
        async with get_db() as s:
            return await _get(s)


async def get_unused_ideas(
    limit: int = 10,
    source: Optional[str] = None,
    session: Optional[AsyncSession] = None
) -> List[Idea]:
    """Get unused ideas"""
    async def _get(s: AsyncSession) -> List[Idea]:
        query = select(Idea).where(Idea.used == False)
        if source:
            query = query.where(Idea.source == source)
        query = query.order_by(Idea.created_at.desc()).limit(limit)
        result = await s.execute(query)
        return list(result.scalars().all())
    
    if session:
        return await _get(session)
    else:
        async with get_db() as s:
            return await _get(s)


async def mark_idea_used(idea_id: int, session: Optional[AsyncSession] = None) -> bool:
    """Mark an idea as used"""
    async def _mark(s: AsyncSession) -> bool:
        result = await s.execute(select(Idea).where(Idea.id == idea_id))
        idea = result.scalar_one_or_none()
        if idea:
            idea.used = True
            return True
        return False
    
    if session:
        return await _mark(session)
    else:
        async with get_db() as s:
            return await _mark(s)


# =============================================================================
# Project CRUD Operations
# =============================================================================

async def create_project(
    idea_id: int,
    name: str,
    plan_json: Optional[dict] = None,
    session: Optional[AsyncSession] = None
) -> Project:
    """Create a new project"""
    async def _create(s: AsyncSession) -> Project:
        project = Project(
            idea_id=idea_id,
            name=name,
            plan_json=plan_json,
            status=ProjectStatus.IDEATION.value
        )
        s.add(project)
        await s.flush()
        await s.refresh(project)
        return project
    
    if session:
        return await _create(session)
    else:
        async with get_db() as s:
            return await _create(s)


async def get_project_by_id(project_id: int, session: Optional[AsyncSession] = None) -> Optional[Project]:
    """Get project by ID"""
    async def _get(s: AsyncSession) -> Optional[Project]:
        result = await s.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()
    
    if session:
        return await _get(session)
    else:
        async with get_db() as s:
            return await _get(s)


async def get_active_project(session: Optional[AsyncSession] = None) -> Optional[Project]:
    """Get the currently active project (not completed/failed)"""
    async def _get(s: AsyncSession) -> Optional[Project]:
        query = select(Project).where(
            Project.status.notin_([ProjectStatus.COMPLETED.value, ProjectStatus.FAILED.value])
        ).order_by(Project.created_at.desc()).limit(1)
        result = await s.execute(query)
        return result.scalar_one_or_none()
    
    if session:
        return await _get(session)
    else:
        async with get_db() as s:
            return await _get(s)


async def update_project_status(
    project_id: int,
    status: str,
    github_url: Optional[str] = None,
    x_post_url: Optional[str] = None,
    dev_test_iterations: Optional[int] = None,
    current_agent: Optional[str] = None,
    plan_json: Optional[dict] = None,
    idea_json: Optional[dict] = None,
    name: Optional[str] = None,
    session: Optional[AsyncSession] = None
) -> bool:
    """Update project status and optional fields"""
    async def _update(s: AsyncSession) -> bool:
        result = await s.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            project.status = status if isinstance(status, str) else status.value
            if github_url is not None:
                project.github_url = github_url
            if x_post_url is not None:
                project.x_post_url = x_post_url
            if dev_test_iterations is not None:
                project.dev_test_iterations = dev_test_iterations
            if current_agent is not None:
                project.current_agent = current_agent
            if plan_json is not None:
                project.plan_json = plan_json
            if idea_json is not None:
                project.idea_json = idea_json
            if name is not None:
                project.name = name
            return True
        return False
    
    if session:
        return await _update(session)
    else:
        async with get_db() as s:
            return await _update(s)


# =============================================================================
# AgentLog CRUD Operations
# =============================================================================

async def add_agent_log(
    project_id: int,
    agent_name: str,
    message: str,
    log_type: str = LogType.INFO.value,
    session: Optional[AsyncSession] = None
) -> AgentLog:
    """Add an agent log entry"""
    async def _add(s: AsyncSession) -> AgentLog:
        log = AgentLog(
            project_id=project_id,
            agent_name=agent_name,
            message=message,
            log_type=log_type if isinstance(log_type, str) else log_type.value
        )
        s.add(log)
        await s.flush()
        await s.refresh(log)
        return log
    
    if session:
        return await _add(session)
    else:
        async with get_db() as s:
            return await _add(s)


async def get_recent_logs(
    limit: int = 50,
    log_type: Optional[str] = None,
    session: Optional[AsyncSession] = None
) -> List[AgentLog]:
    """Get recent logs across all projects"""
    async def _get(s: AsyncSession) -> List[AgentLog]:
        query = select(AgentLog)
        if log_type:
            query = query.where(AgentLog.log_type == log_type)
        query = query.order_by(AgentLog.created_at.desc()).limit(limit)
        result = await s.execute(query)
        return list(result.scalars().all())
    
    if session:
        return await _get(session)
    else:
        async with get_db() as s:
            return await _get(s)


async def get_project_logs(
    project_id: int,
    limit: int = 100,
    log_type: Optional[str] = None,
    session: Optional[AsyncSession] = None
) -> List[AgentLog]:
    """Get logs for a specific project"""
    async def _get(s: AsyncSession) -> List[AgentLog]:
        query = select(AgentLog).where(AgentLog.project_id == project_id)
        if log_type:
            query = query.where(AgentLog.log_type == log_type)
        query = query.order_by(AgentLog.created_at.desc()).limit(limit)
        result = await s.execute(query)
        return list(result.scalars().all())
    
    if session:
        return await _get(session)
    else:
        async with get_db() as s:
            return await _get(s)


# =============================================================================
# Statistics
# =============================================================================

async def get_project_idea_json(project_id: int, session: Optional[AsyncSession] = None) -> Optional[dict]:
    """Get the submitted idea JSON for a project"""
    async def _get(s: AsyncSession) -> Optional[dict]:
        result = await s.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            return project.idea_json
        return None
    
    if session:
        return await _get(session)
    else:
        async with get_db() as s:
            return await _get(s)


async def get_project_plan_json(project_id: int, session: Optional[AsyncSession] = None) -> Optional[dict]:
    """Get the submitted plan JSON for a project"""
    async def _get(s: AsyncSession) -> Optional[dict]:
        result = await s.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            return project.plan_json
        return None
    
    if session:
        return await _get(session)
    else:
        async with get_db() as s:
            return await _get(s)


async def set_project_idea_json(project_id: int, idea_json: dict, session: Optional[AsyncSession] = None) -> bool:
    """Set the idea JSON for a project (called by MCP submit_idea)"""
    async def _set(s: AsyncSession) -> bool:
        result = await s.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            project.idea_json = idea_json
            return True
        return False
    
    if session:
        return await _set(session)
    else:
        async with get_db() as s:
            return await _set(s)


async def set_project_plan_json(project_id: int, plan_json: dict, session: Optional[AsyncSession] = None) -> bool:
    """Set the plan JSON for a project (called by MCP submit_plan)"""
    async def _set(s: AsyncSession) -> bool:
        result = await s.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            project.plan_json = plan_json
            return True
        return False
    
    if session:
        return await _set(session)
    else:
        async with get_db() as s:
            return await _set(s)


async def get_project_test_result_json(project_id: int, session: Optional[AsyncSession] = None) -> Optional[dict]:
    """Get the submitted test result JSON for a project"""
    async def _get(s: AsyncSession) -> Optional[dict]:
        result = await s.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            return project.test_result_json
        return None
    
    if session:
        return await _get(session)
    else:
        async with get_db() as s:
            return await _get(s)


async def set_project_test_result_json(project_id: int, test_result_json: dict, session: Optional[AsyncSession] = None) -> bool:
    """Set the test result JSON for a project (called by MCP submit_test_result)"""
    async def _set(s: AsyncSession) -> bool:
        result = await s.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            project.test_result_json = test_result_json
            return True
        return False
    
    if session:
        return await _set(session)
    else:
        async with get_db() as s:
            return await _set(s)


async def get_project_implementation_status_json(project_id: int, session: Optional[AsyncSession] = None) -> Optional[dict]:
    """Get the submitted implementation status JSON for a project"""
    async def _get(s: AsyncSession) -> Optional[dict]:
        result = await s.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            return project.implementation_status_json
        return None
    
    if session:
        return await _get(session)
    else:
        async with get_db() as s:
            return await _get(s)


async def set_project_implementation_status_json(project_id: int, implementation_status_json: dict, session: Optional[AsyncSession] = None) -> bool:
    """Set the implementation status JSON for a project (called by MCP submit_implementation_status)"""
    async def _set(s: AsyncSession) -> bool:
        result = await s.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            project.implementation_status_json = implementation_status_json
            return True
        return False
    
    if session:
        return await _set(session)
    else:
        async with get_db() as s:
            return await _set(s)


async def clear_project_devtest_state(project_id: int, session: Optional[AsyncSession] = None) -> bool:
    """Clear test result and implementation status for a new dev-test iteration"""
    async def _clear(s: AsyncSession) -> bool:
        result = await s.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            project.test_result_json = None
            project.implementation_status_json = None
            return True
        return False
    
    if session:
        return await _clear(session)
    else:
        async with get_db() as s:
            return await _clear(s)


async def get_stats(session: Optional[AsyncSession] = None) -> dict:
    """Get database statistics"""
    async def _get(s: AsyncSession) -> dict:
        ideas_count = await s.execute(select(func.count(Idea.id)))
        projects_count = await s.execute(select(func.count(Project.id)))
        completed_count = await s.execute(
            select(func.count(Project.id)).where(Project.status == ProjectStatus.COMPLETED.value)
        )
        
        return {
            "total_ideas": ideas_count.scalar() or 0,
            "total_projects": projects_count.scalar() or 0,
            "completed_projects": completed_count.scalar() or 0
        }
    
    if session:
        return await _get(session)
    else:
        async with get_db() as s:
            return await _get(s)
