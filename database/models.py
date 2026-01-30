"""
7000%AUTO Database Models
SQLAlchemy ORM models for projects, ideas, and logs
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, Text, ForeignKey, JSON, Boolean, Integer, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


class IdeaSource(str, Enum):
    """Sources for project ideas"""
    ARXIV = "arxiv"
    REDDIT = "reddit"
    X = "x"
    HN = "hn"
    PH = "ph"
    SYSTEM = "system"


class ProjectStatus(str, Enum):
    """Project workflow status"""
    IDEATION = "ideation"
    PLANNING = "planning"
    DEVELOPMENT = "development"
    TESTING = "testing"
    UPLOADING = "uploading"
    PROMOTING = "promoting"
    COMPLETED = "completed"
    FAILED = "failed"


class LogType(str, Enum):
    """Types of agent logs"""
    INFO = "info"
    ERROR = "error"
    OUTPUT = "output"
    DEBUG = "debug"


class Idea(Base):
    """Generated project ideas"""
    __tablename__ = "ideas"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20))  # arxiv, reddit, x, hn, ph
    used: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class Project(Base):
    """Projects being developed"""
    __tablename__ = "projects"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    idea_id: Mapped[int] = mapped_column(ForeignKey("ideas.id"))
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default=ProjectStatus.IDEATION.value)
    idea_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Submitted idea data from MCP
    plan_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    test_result_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Submitted test result from Tester MCP
    implementation_status_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Submitted status from Developer MCP
    gitea_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    x_post_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ci_result_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # CI/CD result from Tester
    upload_status_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Upload status from Uploader
    ci_test_iterations: Mapped[int] = mapped_column(default=0)  # Uploader-Tester-Developer CI loop iterations
    dev_test_iterations: Mapped[int] = mapped_column(default=0)
    current_agent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)


class AgentLog(Base):
    """Logs from agent activities"""
    __tablename__ = "agent_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    agent_name: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text)
    log_type: Mapped[str] = mapped_column(String(20), default=LogType.INFO.value)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
