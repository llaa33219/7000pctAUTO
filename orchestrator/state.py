"""
Project State Management for 7000%AUTO
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Any


class AgentType(str, Enum):
    """Agent types in the workflow"""
    IDEATOR = "ideator"
    PLANNER = "planner"
    DEVELOPER = "developer"
    TESTER = "tester"
    UPLOADER = "uploader"
    EVANGELIST = "evangelist"


@dataclass
class ProjectState:
    """State of a project in the workflow"""
    project_id: int
    current_agent: Optional[str] = None
    status: str = "ideation"
    idea: Optional[Dict[str, Any]] = None
    plan: Optional[Dict[str, Any]] = None
    dev_test_iterations: int = 0
    github_url: Optional[str] = None
    x_post_url: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "current_agent": self.current_agent,
            "status": self.status,
            "idea": self.idea,
            "plan": self.plan,
            "dev_test_iterations": self.dev_test_iterations,
            "github_url": self.github_url,
            "x_post_url": self.x_post_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "errors": self.errors
        }


class StateManager:
    """Manages project states"""
    
    def __init__(self):
        self._states: Dict[int, ProjectState] = {}
        self._active_project_id: Optional[int] = None
        self._lock = asyncio.Lock()
    
    async def get_state(self, project_id: int) -> Optional[ProjectState]:
        """Get state for a project"""
        async with self._lock:
            return self._states.get(project_id)
    
    async def create_state(self, project_id: int) -> ProjectState:
        """Create new project state"""
        async with self._lock:
            state = ProjectState(project_id=project_id)
            self._states[project_id] = state
            return state
    
    async def update_state(
        self,
        project_id: int,
        current_agent: Optional[str] = None,
        status: Optional[str] = None,
        idea: Optional[Dict] = None,
        plan: Optional[Dict] = None,
        dev_test_iterations: Optional[int] = None,
        github_url: Optional[str] = None,
        x_post_url: Optional[str] = None,
        error: Optional[str] = None
    ) -> Optional[ProjectState]:
        """Update project state"""
        async with self._lock:
            state = self._states.get(project_id)
            if not state:
                return None
            
            if current_agent is not None:
                state.current_agent = current_agent
            if status is not None:
                state.status = status
            if idea is not None:
                state.idea = idea
            if plan is not None:
                state.plan = plan
            if dev_test_iterations is not None:
                state.dev_test_iterations = dev_test_iterations
            if github_url is not None:
                state.github_url = github_url
            if x_post_url is not None:
                state.x_post_url = x_post_url
            if error is not None:
                state.errors.append(error)
            
            state.updated_at = datetime.utcnow()
            return state
    
    async def get_active_project_id(self) -> Optional[int]:
        """Get currently active project ID"""
        async with self._lock:
            return self._active_project_id
    
    async def set_active_project(self, project_id: Optional[int]):
        """Set active project"""
        async with self._lock:
            self._active_project_id = project_id
    
    async def get_active_state(self) -> Optional[ProjectState]:
        """Get state of active project"""
        project_id = await self.get_active_project_id()
        if project_id is None:
            return None
        return await self.get_state(project_id)
    
    async def get_all_states(self) -> List[ProjectState]:
        """Get all project states"""
        async with self._lock:
            return list(self._states.values())
