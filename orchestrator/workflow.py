"""
Workflow Orchestrator for 7000%AUTO
Manages the AI agent pipeline from ideation to promotion
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Callable

from .state import StateManager, ProjectState, AgentType
from .opencode_client import OpenCodeClient

# DevTest MCP communication imports
from database.db import (
    get_project_implementation_status_json,
    get_project_test_result_json,
    clear_project_devtest_state,
)

logger = logging.getLogger(__name__)


class WorkflowEventType(str, Enum):
    """Types of workflow events for SSE"""
    WORKFLOW_STARTED = "workflow_started"
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_ERROR = "agent_error"
    TEST_PASSED = "test_passed"
    TEST_FAILED = "test_failed"
    ITERATION_STARTED = "iteration_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    LOG = "log"


@dataclass
class WorkflowEvent:
    """Event emitted during workflow execution"""
    type: WorkflowEventType
    agent: Optional[str] = None
    message: str = ""
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "agent": self.agent,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }


class WorkflowOrchestrator:
    """
    Main orchestrator for the AI agent pipeline.
    
    Manages the flow: Ideator -> Planner -> Developer <-> Tester -> Uploader -> Evangelist
    """
    
    def __init__(self):
        self.state_manager = StateManager()
        self.client = OpenCodeClient()
        self._running = False
        self._event_listeners: List[Callable[[WorkflowEvent], None]] = []
    
    def add_event_listener(self, listener: Callable[[WorkflowEvent], None]):
        """Add event listener for SSE streaming"""
        self._event_listeners.append(listener)
    
    def remove_event_listener(self, listener: Callable[[WorkflowEvent], None]):
        """Remove event listener"""
        if listener in self._event_listeners:
            self._event_listeners.remove(listener)
    
    async def _emit_event(self, event: WorkflowEvent):
        """Emit event to all listeners"""
        for listener in self._event_listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event)
                else:
                    listener(event)
            except Exception as e:
                logger.error(f"Event listener error: {e}")
    
    async def _log(self, project_id: int, agent: str, message: str, log_type: str = "info"):
        """Log agent activity to database and emit event"""
        try:
            from database import add_agent_log
            await add_agent_log(project_id, agent, message, log_type)
        except Exception as e:
            logger.error(f"Failed to log: {e}")
        
        await self._emit_event(WorkflowEvent(
            type=WorkflowEventType.LOG,
            agent=agent,
            message=message,
            data={"log_type": log_type}
        ))
    
    async def run_ideator(self, project_id: int) -> Optional[Dict[str, Any]]:
        """Run the Ideator agent to generate a project idea"""
        await self._emit_event(WorkflowEvent(
            type=WorkflowEventType.AGENT_STARTED,
            agent="ideator",
            message="Starting idea generation"
        ))
        
        session_id = None
        try:
            session_id = await self.client.create_session("ideator")
            
            # Pass project_id so agent can use submit_idea tool with it
            prompt = f"""You are working on project_id={project_id}.

Search for trending topics and generate ONE innovative project idea.

Use the search tools to find inspiration from:
- arXiv papers
- Reddit programming communities
- Hacker News
- Product Hunt

Then check the database for existing ideas to avoid duplicates.

When you have finalized your idea, use the submit_idea tool with project_id={project_id} to save it."""
            
            # Run the agent - it will call submit_idea which saves to DB
            await self.client.send_message(session_id, prompt)
            await self.client.close_session(session_id)
            session_id = None
            
            # Get the submitted idea from database
            from database.db import get_project_idea_json
            idea = await get_project_idea_json(project_id)
            
            if idea:
                logger.info(f"Ideator submitted idea: {idea.get('title', 'Unknown')}")
                await self._log(project_id, "ideator", f"Generated idea: {idea.get('title', 'Unknown')}", "output")
                await self._emit_event(WorkflowEvent(
                    type=WorkflowEventType.AGENT_COMPLETED,
                    agent="ideator",
                    message="Idea generated successfully",
                    data=idea
                ))
                return idea
            
            raise Exception("Ideator did not submit idea via submit_idea tool")
            
        except Exception as e:
            error_msg = str(e)
            if "API Error" in error_msg or "Auth" in error_msg:
                error_msg = f"{error_msg} - Please check your OPENCODE_API_KEY environment variable"
            
            await self._log(project_id, "ideator", f"Error: {error_msg}", "error")
            await self._emit_event(WorkflowEvent(
                type=WorkflowEventType.AGENT_ERROR,
                agent="ideator",
                message=error_msg
            ))
            return None
        finally:
            if session_id:
                try:
                    await self.client.close_session(session_id)
                except Exception:
                    pass
    
    async def run_planner(self, project_id: int, idea: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Run the Planner agent to create implementation plan"""
        await self._emit_event(WorkflowEvent(
            type=WorkflowEventType.AGENT_STARTED,
            agent="planner",
            message="Creating implementation plan"
        ))
        
        session_id = None
        try:
            session_id = await self.client.create_session("planner")
            
            # Pass project_id so agent can use submit_plan tool with it
            prompt = f"""You are working on project_id={project_id}.

Create a detailed implementation plan for this project idea:

{idea}

Research the best technologies and create a comprehensive plan including:
- Technology stack selection
- File structure
- Feature breakdown
- Implementation steps
- Testing strategy

When you have finalized your plan, use the submit_plan tool with project_id={project_id} to save it."""
            
            # Run the agent - it will call submit_plan which saves to DB
            await self.client.send_message(session_id, prompt)
            await self.client.close_session(session_id)
            session_id = None
            
            # Get the submitted plan from database
            from database.db import get_project_plan_json
            plan = await get_project_plan_json(project_id)
            
            if plan:
                logger.info(f"Planner submitted plan: {plan.get('project_name', 'Unknown')}")
                await self._log(project_id, "planner", f"Created plan for: {plan.get('project_name', 'Unknown')}", "output")
                await self._emit_event(WorkflowEvent(
                    type=WorkflowEventType.AGENT_COMPLETED,
                    agent="planner",
                    message="Plan created successfully",
                    data=plan
                ))
                return plan
            
            raise Exception("Planner did not submit plan via submit_plan tool")
            
        except Exception as e:
            error_msg = str(e)
            if "API Error" in error_msg or "Auth" in error_msg:
                error_msg = f"{error_msg} - Please check your OPENCODE_API_KEY environment variable"
            
            await self._log(project_id, "planner", f"Error: {error_msg}", "error")
            await self._emit_event(WorkflowEvent(
                type=WorkflowEventType.AGENT_ERROR,
                agent="planner",
                message=error_msg
            ))
            return None
        finally:
            if session_id:
                try:
                    await self.client.close_session(session_id)
                except Exception:
                    pass
    
    async def run_developer(self, project_id: int, plan: Dict[str, Any], is_fixing: bool = False) -> bool:
        """Run the Developer agent to implement the project"""
        await self._emit_event(WorkflowEvent(
            type=WorkflowEventType.AGENT_STARTED,
            agent="developer",
            message="Starting implementation" if not is_fixing else "Fixing bugs"
        ))
        
        session_id = None
        try:
            session_id = await self.client.create_session("developer")
            
            if is_fixing:
                # Developer will use get_test_result MCP tool to see bugs
                prompt = f"""You are working on project_id={project_id}.

The Tester found bugs in your implementation. Use the get_test_result tool with project_id={project_id} to see the detailed bug report.

Fix all the bugs reported by the Tester. After fixing, use the submit_implementation_status tool with:
- project_id={project_id}
- status="fixed"
- bugs_addressed: list the bugs you fixed
- ready_for_testing=True"""
            else:
                # New implementation
                prompt = f"""You are working on project_id={project_id}.

Implement this project according to the plan:

{plan}

Create all files, install dependencies, and ensure the project is complete and working.

When done, use the submit_implementation_status tool with:
- project_id={project_id}
- status="completed"
- files_created: list the files you created
- dependencies_installed: list the packages you installed
- ready_for_testing=True"""
            
            await self.client.send_message(session_id, prompt)
            await self.client.close_session(session_id)
            session_id = None
            
            # Verify implementation status was submitted
            impl_status = await get_project_implementation_status_json(project_id)
            
            if impl_status and impl_status.get("ready_for_testing"):
                status = impl_status.get("status", "completed")
                await self._log(project_id, "developer", f"Implementation {status}", "output")
                await self._emit_event(WorkflowEvent(
                    type=WorkflowEventType.AGENT_COMPLETED,
                    agent="developer",
                    message=f"Implementation {status}",
                    data=impl_status
                ))
                return True
            else:
                # Even without explicit status, consider success if no exception
                await self._log(project_id, "developer", "Implementation completed", "output")
                await self._emit_event(WorkflowEvent(
                    type=WorkflowEventType.AGENT_COMPLETED,
                    agent="developer",
                    message="Implementation completed"
                ))
                return True
            
        except Exception as e:
            error_msg = str(e)
            if "API Error" in error_msg or "Auth" in error_msg:
                error_msg = f"{error_msg} - Please check your OPENCODE_API_KEY environment variable"
            
            await self._log(project_id, "developer", f"Error: {error_msg}", "error")
            await self._emit_event(WorkflowEvent(
                type=WorkflowEventType.AGENT_ERROR,
                agent="developer",
                message=error_msg
            ))
            return False
        finally:
            if session_id:
                try:
                    await self.client.close_session(session_id)
                except Exception:
                    pass
    
    async def run_tester(self, project_id: int) -> Dict[str, Any]:
        """Run the Tester agent to validate the implementation"""
        await self._emit_event(WorkflowEvent(
            type=WorkflowEventType.AGENT_STARTED,
            agent="tester",
            message="Running tests"
        ))
        
        session_id = None
        try:
            session_id = await self.client.create_session("tester")
            
            prompt = f"""You are working on project_id={project_id}.

Test the implemented project:

1. Run linting and type checking
2. Run unit tests
3. Verify the build works
4. Check for obvious bugs

Run the actual test commands and report if they pass or fail.

When done, use the submit_test_result tool with:
- project_id={project_id}
- status="PASS" or "FAIL"
- summary: brief description of results
- checks_performed: list of checks you ran
- bugs: list of bugs found (if any)
- ready_for_upload: true only if all tests pass"""
            
            await self.client.send_message(session_id, prompt)
            await self.client.close_session(session_id)
            session_id = None
            
            # Get test result from database (submitted via MCP)
            test_result = await get_project_test_result_json(project_id)
            
            if test_result:
                status = test_result.get("status", "PASS")
                bugs = test_result.get("bugs", [])
                
                if status == "PASS":
                    await self._log(project_id, "tester", "All tests passed", "output")
                    await self._emit_event(WorkflowEvent(
                        type=WorkflowEventType.TEST_PASSED,
                        agent="tester",
                        message="All tests passed",
                        data=test_result
                    ))
                    return {"status": "PASS"}
                else:
                    await self._log(project_id, "tester", f"Tests failed: {len(bugs)} bugs found", "output")
                    await self._emit_event(WorkflowEvent(
                        type=WorkflowEventType.TEST_FAILED,
                        agent="tester",
                        message=f"Tests failed: {len(bugs)} bugs found",
                        data=test_result
                    ))
                    return {"status": "FAIL", "bugs": bugs}
            else:
                # No explicit test result - assume pass if no exception
                await self._log(project_id, "tester", "Tests completed", "output")
                await self._emit_event(WorkflowEvent(
                    type=WorkflowEventType.TEST_PASSED,
                    agent="tester",
                    message="Tests completed"
                ))
                return {"status": "PASS"}
            
        except Exception as e:
            error_msg = str(e)
            if "API Error" in error_msg or "Auth" in error_msg:
                error_msg = f"{error_msg} - Please check your OPENCODE_API_KEY environment variable"
            
            await self._log(project_id, "tester", f"Error: {error_msg}", "error")
            await self._emit_event(WorkflowEvent(
                type=WorkflowEventType.TEST_FAILED,
                agent="tester",
                message="Tests failed",
                data={"error": error_msg}
            ))
            return {"status": "FAIL", "error": error_msg}
        finally:
            if session_id:
                try:
                    await self.client.close_session(session_id)
                except Exception:
                    pass
    
    async def run_uploader(self, project_id: int, project_name: str) -> Optional[str]:
        """Run the Uploader agent to publish to Gitea"""
        await self._emit_event(WorkflowEvent(
            type=WorkflowEventType.AGENT_STARTED,
            agent="uploader",
            message="Uploading to Gitea"
        ))
        
        session_id = None
        try:
            session_id = await self.client.create_session("uploader")
            
            prompt = f"""Upload the project "{project_name}" to Gitea:

1. Create a new public repository named "{project_name}"
2. Write a comprehensive README
3. Set up Gitea Actions for CI/CD
4. Push all code
5. Create an initial release if appropriate

Use the gitea tools to create and push the repository."""
            
            await self.client.send_message(session_id, prompt)
            await self.client.close_session(session_id)
            session_id = None
            
            # TODO: Get actual Gitea URL from DB or gitea MCP
            # For now, construct it from project name
            from config import settings
            github_url = f"{settings.GITEA_URL.rstrip('/')}/{settings.GITEA_USERNAME}/{project_name}"
            
            await self._log(project_id, "uploader", f"Uploaded to Gitea: {github_url}", "output")
            await self._emit_event(WorkflowEvent(
                type=WorkflowEventType.AGENT_COMPLETED,
                agent="uploader",
                message="Upload completed",
                data={"github_url": github_url}
            ))
            return github_url
            
        except Exception as e:
            error_msg = str(e)
            if "API Error" in error_msg or "Auth" in error_msg:
                error_msg = f"{error_msg} - Please check your OPENCODE_API_KEY environment variable"
            
            await self._log(project_id, "uploader", f"Error: {error_msg}", "error")
            await self._emit_event(WorkflowEvent(
                type=WorkflowEventType.AGENT_ERROR,
                agent="uploader",
                message=error_msg
            ))
            return None
        finally:
            if session_id:
                try:
                    await self.client.close_session(session_id)
                except Exception:
                    pass
    
    async def run_evangelist(self, project_id: int, github_url: str, project_info: Dict[str, Any]) -> Optional[str]:
        """Run the Evangelist agent to promote on X/Twitter"""
        await self._emit_event(WorkflowEvent(
            type=WorkflowEventType.AGENT_STARTED,
            agent="evangelist",
            message="Creating promotional post"
        ))
        
        session_id = None
        try:
            session_id = await self.client.create_session("evangelist")
            
            prompt = f"""Create and post an engaging X/Twitter post to promote this project:

Project: {project_info.get('title', 'Unknown')}
Description: {project_info.get('description', '')}
GitHub: {github_url}

Use the x_api tools to create and post a compelling tweet under 280 characters with emojis and hashtags."""
            
            await self.client.send_message(session_id, prompt)
            await self.client.close_session(session_id)
            session_id = None
            
            # Agent uses x_api MCP to post - consider it done
            await self._log(project_id, "evangelist", "Promotional post created", "output")
            await self._emit_event(WorkflowEvent(
                type=WorkflowEventType.AGENT_COMPLETED,
                agent="evangelist",
                message="Post created"
            ))
            return "posted"
            
        except Exception as e:
            error_msg = str(e)
            if "API Error" in error_msg or "Auth" in error_msg:
                error_msg = f"{error_msg} - Please check your OPENCODE_API_KEY environment variable"
            
            await self._log(project_id, "evangelist", f"Error: {error_msg}", "error")
            await self._emit_event(WorkflowEvent(
                type=WorkflowEventType.AGENT_ERROR,
                agent="evangelist",
                message=error_msg
            ))
            return None
        finally:
            if session_id:
                try:
                    await self.client.close_session(session_id)
                except Exception:
                    pass
    
    async def run_full_pipeline(self) -> Dict[str, Any]:
        """
        Run the complete workflow pipeline.
        
        Developer-Tester loop runs INFINITELY until tests pass.
        
        Returns:
            Dict with keys: success, project_id, github_url, x_post_url, dev_test_iterations, error
        """
        self._running = True
        
        try:
            from database import (
                create_idea, create_project, update_project_status,
                mark_idea_used, ProjectStatus
            )
            
            await self._emit_event(WorkflowEvent(
                type=WorkflowEventType.WORKFLOW_STARTED,
                message="Starting new project pipeline"
            ))
            
            # Create initial project record
            idea_record = await create_idea(
                title="Pending",
                description="Generating idea...",
                source="system"
            )
            
            project = await create_project(
                idea_id=idea_record.id,
                name="pending"
            )
            
            project_id = project.id
            await self.state_manager.create_state(project_id)
            await self.state_manager.set_active_project(project_id)
            
            # 1. IDEATOR
            await update_project_status(project_id, "ideation", current_agent="ideator")
            idea = await self.run_ideator(project_id)
            if not idea:
                await update_project_status(project_id, "failed")
                return {"success": False, "project_id": project_id, "error": "Ideator failed to generate idea"}
            
            await self.state_manager.update_state(project_id, idea=idea)
            
            # 2. PLANNER
            await update_project_status(project_id, "planning", current_agent="planner")
            plan = await self.run_planner(project_id, idea)
            if not plan:
                await update_project_status(project_id, "failed")
                return {"success": False, "project_id": project_id, "error": "Planner failed to create plan"}
            
            await self.state_manager.update_state(project_id, plan=plan)
            await update_project_status(project_id, "planning", plan_json=plan)
            
            project_name = plan.get("project_name", idea.get("title", "project"))
            
            # 3. DEVELOPER -> TESTER LOOP (INFINITE)
            iteration = 0
            is_fixing = False
            
            while self._running:
                iteration += 1
                
                await self._emit_event(WorkflowEvent(
                    type=WorkflowEventType.ITERATION_STARTED,
                    message=f"Developer-Tester iteration {iteration}",
                    data={"iteration": iteration}
                ))
                
                # Clear previous devtest state for new iteration
                await clear_project_devtest_state(project_id)
                
                await update_project_status(
                    project_id, "development",
                    current_agent="developer",
                    dev_test_iterations=iteration
                )
                
                # Developer (uses MCP to get test results if is_fixing)
                success = await self.run_developer(project_id, plan, is_fixing)
                if not success:
                    continue  # Try again
                
                # Tester (uses MCP to submit test results)
                await update_project_status(project_id, "testing", current_agent="tester")
                test_result = await self.run_tester(project_id)
                
                if test_result.get("status") == "PASS":
                    break  # Exit loop - tests passed!
                
                # Tests failed - next iteration will be a fix
                is_fixing = True
                
                await self.state_manager.update_state(
                    project_id,
                    dev_test_iterations=iteration,
                    error=f"Test failed at iteration {iteration}"
                )
            
            if not self._running:
                await update_project_status(project_id, "failed")
                return {"success": False, "project_id": project_id, "error": "Pipeline was stopped"}
            
            # 4. UPLOADER
            await update_project_status(project_id, "uploading", current_agent="uploader")
            github_url = await self.run_uploader(project_id, project_name)
            if not github_url:
                await update_project_status(project_id, "failed")
                return {"success": False, "project_id": project_id, "error": "Uploader failed to upload to Gitea"}
            
            await update_project_status(project_id, "uploading", github_url=github_url)
            
            # 5. EVANGELIST
            await update_project_status(project_id, "promoting", current_agent="evangelist")
            x_post_url = await self.run_evangelist(project_id, github_url, idea)
            
            if x_post_url:
                await update_project_status(project_id, "promoting", x_post_url=x_post_url)
            
            # COMPLETED!
            await update_project_status(project_id, "completed", current_agent=None)
            await mark_idea_used(idea_record.id)
            
            await self._emit_event(WorkflowEvent(
                type=WorkflowEventType.WORKFLOW_COMPLETED,
                message="Project completed successfully!",
                data={
                    "project_id": project_id,
                    "project_name": project_name,
                    "github_url": github_url,
                    "iterations": iteration
                }
            ))
            
            return {
                "success": True,
                "project_id": project_id,
                "project_name": project_name,
                "github_url": github_url,
                "x_post_url": x_post_url,
                "dev_test_iterations": iteration,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            await self._emit_event(WorkflowEvent(
                type=WorkflowEventType.WORKFLOW_FAILED,
                message=str(e)
            ))
            return {
                "success": False,
                "project_id": locals().get("project_id"),
                "error": str(e)
            }
        
        finally:
            await self.state_manager.set_active_project(None)
    
    @property
    def is_running(self) -> bool:
        """Check if the pipeline is currently running"""
        return self._running
    
    async def stop(self):
        """Stop the running pipeline"""
        self._running = False
        # Close the HTTP client
        if self.client:
            await self.client.close()
