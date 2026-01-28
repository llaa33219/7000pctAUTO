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
            
            prompt = """Search for trending topics and generate ONE innovative project idea.
            
            Use the search tools to find inspiration from:
            - arXiv papers
            - Reddit programming communities
            - Hacker News
            - Product Hunt
            
            Then check the database for existing ideas to avoid duplicates.
            
            Output your idea in the specified JSON format."""
            
            response = await self.client.send_message(session_id, prompt)
            await self.client.close_session(session_id)
            session_id = None
            
            content = response.get("content", "")
            if not content:
                raise Exception("Empty response from ideator agent")
            
            idea = self.client.parse_json_from_response(content)
            
            if idea:
                await self._log(project_id, "ideator", f"Generated idea: {idea.get('title', 'Unknown')}", "output")
                await self._emit_event(WorkflowEvent(
                    type=WorkflowEventType.AGENT_COMPLETED,
                    agent="ideator",
                    message="Idea generated successfully",
                    data=idea
                ))
                return idea
            
            raise Exception(f"Failed to parse idea from response (content length: {len(content)} chars)")
            
        except Exception as e:
            error_msg = str(e)
            # Provide more helpful error messages for common issues
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
            
            prompt = f"""Create a detailed implementation plan for this project idea:

{idea}

Research the best technologies and create a comprehensive plan including:
- Technology stack selection
- File structure
- Feature breakdown
- Implementation steps
- Testing strategy

Output your plan in the specified JSON format."""
            
            response = await self.client.send_message(session_id, prompt)
            await self.client.close_session(session_id)
            session_id = None
            
            content = response.get("content", "")
            if not content:
                raise Exception("Empty response from planner agent")
            
            plan = self.client.parse_json_from_response(content)
            
            if plan:
                await self._log(project_id, "planner", f"Created plan for: {plan.get('project_name', 'Unknown')}", "output")
                await self._emit_event(WorkflowEvent(
                    type=WorkflowEventType.AGENT_COMPLETED,
                    agent="planner",
                    message="Plan created successfully",
                    data=plan
                ))
                return plan
            
            raise Exception(f"Failed to parse plan from response (content length: {len(content)} chars)")
            
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
    
    async def run_developer(self, project_id: int, plan: Dict[str, Any], feedback: Optional[str] = None) -> bool:
        """Run the Developer agent to implement the project"""
        await self._emit_event(WorkflowEvent(
            type=WorkflowEventType.AGENT_STARTED,
            agent="developer",
            message="Starting implementation" if not feedback else "Fixing bugs"
        ))
        
        session_id = None
        try:
            session_id = await self.client.create_session("developer")
            
            if feedback:
                prompt = f"""Fix the following bugs reported by the Tester:

{feedback}

Make the necessary changes and ensure the code works correctly."""
            else:
                prompt = f"""Implement this project according to the plan:

{plan}

Create all files, install dependencies, and ensure the project is complete and working."""
            
            response = await self.client.send_message(session_id, prompt)
            await self.client.close_session(session_id)
            session_id = None
            
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
            
            prompt = """Test the implemented project:

1. Run linting and type checking
2. Run unit tests
3. Verify the build works
4. Check for obvious bugs

Output your results in the specified JSON format with status "PASS" or "FAIL"."""
            
            response = await self.client.send_message(session_id, prompt)
            await self.client.close_session(session_id)
            session_id = None
            
            result = self.client.parse_json_from_response(response.get("content", ""))
            
            if result:
                status = result.get("status", "FAIL")
                
                if status == "PASS":
                    await self._log(project_id, "tester", "All tests passed!", "output")
                    await self._emit_event(WorkflowEvent(
                        type=WorkflowEventType.TEST_PASSED,
                        agent="tester",
                        message="All tests passed"
                    ))
                else:
                    await self._log(project_id, "tester", f"Tests failed: {len(result.get('bugs', []))} issues found", "output")
                    await self._emit_event(WorkflowEvent(
                        type=WorkflowEventType.TEST_FAILED,
                        agent="tester",
                        message="Tests failed",
                        data=result
                    ))
                
                return result
            
            return {"status": "FAIL", "error": "Failed to parse test results"}
            
        except Exception as e:
            error_msg = str(e)
            if "API Error" in error_msg or "Auth" in error_msg:
                error_msg = f"{error_msg} - Please check your OPENCODE_API_KEY environment variable"
            
            await self._log(project_id, "tester", f"Error: {error_msg}", "error")
            return {"status": "FAIL", "error": error_msg}
        finally:
            if session_id:
                try:
                    await self.client.close_session(session_id)
                except Exception:
                    pass
    
    async def run_uploader(self, project_id: int, project_name: str) -> Optional[str]:
        """Run the Uploader agent to publish to GitHub"""
        await self._emit_event(WorkflowEvent(
            type=WorkflowEventType.AGENT_STARTED,
            agent="uploader",
            message="Uploading to GitHub"
        ))
        
        session_id = None
        try:
            session_id = await self.client.create_session("uploader")
            
            prompt = f"""Upload the project "{project_name}" to GitHub:

1. Create a new public repository
2. Write a comprehensive README
3. Set up GitHub Actions for CI/CD
4. Push all code
5. Create an initial release if appropriate

Output the repository URL when complete."""
            
            response = await self.client.send_message(session_id, prompt)
            await self.client.close_session(session_id)
            session_id = None
            
            result = self.client.parse_json_from_response(response.get("content", ""))
            github_url = result.get("repository", {}).get("url") if result else None
            
            if github_url:
                await self._log(project_id, "uploader", f"Uploaded to: {github_url}", "output")
                await self._emit_event(WorkflowEvent(
                    type=WorkflowEventType.AGENT_COMPLETED,
                    agent="uploader",
                    message="Upload completed",
                    data={"github_url": github_url}
                ))
                return github_url
            
            raise Exception("Failed to get GitHub URL from response")
            
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
            
            prompt = f"""Create an engaging X/Twitter post to promote this project:

Project: {project_info.get('title', 'Unknown')}
Description: {project_info.get('description', '')}
GitHub: {github_url}

Create a compelling tweet under 280 characters with emojis and hashtags."""
            
            response = await self.client.send_message(session_id, prompt)
            await self.client.close_session(session_id)
            session_id = None
            
            result = self.client.parse_json_from_response(response.get("content", ""))
            tweet_url = result.get("tweet", {}).get("url") if result else None
            
            if tweet_url:
                await self._log(project_id, "evangelist", f"Posted: {tweet_url}", "output")
                await self._emit_event(WorkflowEvent(
                    type=WorkflowEventType.AGENT_COMPLETED,
                    agent="evangelist",
                    message="Post created",
                    data={"tweet_url": tweet_url}
                ))
                return tweet_url
            
            # Even without URL, consider it done
            await self._log(project_id, "evangelist", "Promotional post created", "output")
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
            feedback = None
            
            while self._running:
                iteration += 1
                
                await self._emit_event(WorkflowEvent(
                    type=WorkflowEventType.ITERATION_STARTED,
                    message=f"Developer-Tester iteration {iteration}",
                    data={"iteration": iteration}
                ))
                
                await update_project_status(
                    project_id, "development",
                    current_agent="developer",
                    dev_test_iterations=iteration
                )
                
                # Developer
                success = await self.run_developer(project_id, plan, feedback)
                if not success:
                    continue  # Try again
                
                # Tester
                await update_project_status(project_id, "testing", current_agent="tester")
                test_result = await self.run_tester(project_id)
                
                if test_result.get("status") == "PASS":
                    break  # Exit loop - tests passed!
                
                # Tests failed - prepare feedback for next iteration
                bugs = test_result.get("bugs", [])
                feedback = f"Test iteration {iteration} failed. Bugs found:\n"
                for bug in bugs:
                    feedback += f"- {bug.get('file', 'unknown')}: {bug.get('issue', 'unknown issue')}\n"
                
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
                return {"success": False, "project_id": project_id, "error": "Uploader failed to upload to GitHub"}
            
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
