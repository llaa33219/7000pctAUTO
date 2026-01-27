"""
7000%AUTO Database Models
SQLAlchemy 2.0 async models
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List
from sqlalchemy import String, Text, Boolean, Integer, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


class IdeaSource(str, PyEnum):
    """Sources for idea generation"""
    ARXIV = "arxiv"
    REDDIT = "reddit"
    X = "x"
    HN = "hn"
    PH = "ph"


class ProjectStatus(str, PyEnum):
    """Project workflow status"""
    IDEATION = "ideation"
    PLANNING = "planning"
    DEVELOPMENT = "development"
    TESTING = "testing"
    UPLOADING = "uploading"
    PROMOTING = "promoting"
    COMPLETED = "completed"
    FAILED = "failed"


class LogType(str, PyEnum):
    """Agent log types"""
    INFO = "info"
    ERROR = "error"
    OUTPUT = "output"


class Idea(Base):
    """Generated project ideas"""
    __tablename__ = "ideas"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    projects: Mapped[List["Project"]] = relationship("Project", back_populates="idea")
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "used": self.used
        }


class Project(Base):
    """Projects created from ideas"""
    __tablename__ = "projects"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idea_id: Mapped[int] = mapped_column(Integer, ForeignKey("ideas.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=ProjectStatus.IDEATION.value)
    github_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    x_post_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    plan_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    dev_test_iterations: Mapped[int] = mapped_column(Integer, default=0)
    current_agent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Relationships
    idea: Mapped["Idea"] = relationship("Idea", back_populates="projects")
    logs: Mapped[List["AgentLog"]] = relationship("AgentLog", back_populates="project", cascade="all, delete-orphan")
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "idea_id": self.idea_id,
            "name": self.name,
            "status": self.status,
            "github_url": self.github_url,
            "x_post_url": self.x_post_url,
            "plan_json": self.plan_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "dev_test_iterations": self.dev_test_iterations,
            "current_agent": self.current_agent
        }


class AgentLog(Base):
    """Logs from agent executions"""
    __tablename__ = "agent_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    log_type: Mapped[str] = mapped_column(String(20), default=LogType.INFO.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="logs")
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "agent_name": self.agent_name,
            "message": self.message,
            "log_type": self.log_type,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
