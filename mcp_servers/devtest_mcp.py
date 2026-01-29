"""Developer-Tester Communication MCP Server for 7000%AUTO
Provides structured communication between Developer and Tester agents via MCP tools.

This enables Developer and Tester to share:
- Test results (PASS/FAIL with detailed bug reports)
- Implementation status (completed/fixing with file changes)
- Project context (plan, current iteration)
"""

import logging
from typing import Optional
from datetime import datetime

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("DevTest Communication Server")

# Database initialization flag for MCP server process
_db_ready = False


async def _init_db_if_needed():
    """Initialize database if not already initialized. MCP servers run in separate processes."""
    global _db_ready
    if not _db_ready:
        try:
            from database.db import init_db
            await init_db()
            _db_ready = True
            logger.info("Database initialized in DevTest MCP server")
        except Exception as e:
            logger.error(f"Failed to initialize database in DevTest MCP server: {e}")
            raise


@mcp.tool()
async def submit_test_result(
    project_id: int,
    status: str,
    summary: str,
    checks_performed: list[dict] = None,
    bugs: list[dict] = None,
    code_quality: dict = None,
    ready_for_upload: bool = False
) -> dict:
    """
    Submit test results after testing the implementation. Use this tool to report test outcomes.
    The Developer will read these results to fix any bugs.
    
    Args:
        project_id: The project ID being tested (required)
        status: Test status - "PASS" or "FAIL" (required)
        summary: Brief summary of test results (required)
        checks_performed: List of checks with {check, result, details} format
        bugs: List of bugs found with {id, severity, type, file, line, issue, error_message, suggestion} format
        code_quality: Quality assessment with {error_handling, documentation, test_coverage} ratings
        ready_for_upload: Whether the project is ready for upload (true only if PASS)
    
    Returns:
        Dictionary with success status
    
    Example for PASS:
        submit_test_result(
            project_id=1,
            status="PASS",
            summary="All tests passed successfully",
            checks_performed=[
                {"check": "linting", "result": "pass", "details": "No issues found"},
                {"check": "unit_tests", "result": "pass", "details": "15/15 tests passed"}
            ],
            ready_for_upload=True
        )
    
    Example for FAIL:
        submit_test_result(
            project_id=1,
            status="FAIL",
            summary="Found 2 critical issues",
            checks_performed=[
                {"check": "linting", "result": "pass", "details": "No issues"},
                {"check": "type_check", "result": "fail", "details": "3 type errors"}
            ],
            bugs=[
                {
                    "id": 1,
                    "severity": "critical",
                    "type": "type_error",
                    "file": "src/main.py",
                    "line": 42,
                    "issue": "Missing return type annotation",
                    "error_message": "error: Function is missing return type annotation",
                    "suggestion": "Add -> str return type"
                }
            ],
            ready_for_upload=False
        )
    """
    try:
        await _init_db_if_needed()
        from database.db import set_project_test_result_json
        
        # Validate status
        if status not in ("PASS", "FAIL"):
            return {"success": False, "error": "status must be 'PASS' or 'FAIL'"}
        
        # Build test result data
        test_result_data = {
            "status": status,
            "summary": summary,
            "checks_performed": checks_performed or [],
            "bugs": bugs or [],
            "code_quality": code_quality or {},
            "ready_for_upload": ready_for_upload and status == "PASS",
            "submitted_at": datetime.utcnow().isoformat(),
        }
        
        # Save to database
        success = await set_project_test_result_json(project_id, test_result_data)
        
        if success:
            logger.info(f"Test result submitted for project {project_id}: {status}")
            return {
                "success": True,
                "message": f"Test result '{status}' submitted successfully",
                "bugs_count": len(bugs) if bugs else 0
            }
        else:
            logger.error(f"Project {project_id} not found")
            return {"success": False, "error": f"Project {project_id} not found"}
    
    except Exception as e:
        logger.error(f"Error submitting test result: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_test_result(project_id: int) -> dict:
    """
    Get the latest test result for a project. Use this tool to see what the Tester found.
    
    Args:
        project_id: The project ID to get test results for (required)
    
    Returns:
        Dictionary with test result data including status, bugs, and suggestions
    """
    try:
        await _init_db_if_needed()
        from database.db import get_project_test_result_json
        
        test_result = await get_project_test_result_json(project_id)
        
        if test_result:
            return {
                "success": True,
                "test_result": test_result
            }
        else:
            return {
                "success": True,
                "test_result": None,
                "message": "No test result found for this project"
            }
    
    except Exception as e:
        logger.error(f"Error getting test result: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def submit_implementation_status(
    project_id: int,
    status: str,
    files_created: list[dict] = None,
    files_modified: list[dict] = None,
    dependencies_installed: list[str] = None,
    commands_run: list[str] = None,
    bugs_addressed: list[dict] = None,
    notes: str = None,
    ready_for_testing: bool = True
) -> dict:
    """
    Submit implementation status after coding or fixing bugs. Use this tool to inform the Tester.
    
    Args:
        project_id: The project ID being worked on (required)
        status: Status - "completed", "fixed", "in_progress", or "blocked" (required)
        files_created: List of files created with {path, lines, purpose} format
        files_modified: List of files modified with {path, changes} format
        dependencies_installed: List of installed dependencies
        commands_run: List of commands executed
        bugs_addressed: List of bugs fixed with {original_issue, fix_applied, file, line} format
        notes: Any important notes about the implementation
        ready_for_testing: Whether the code is ready for testing (default: True)
    
    Returns:
        Dictionary with success status
    
    Example for new implementation:
        submit_implementation_status(
            project_id=1,
            status="completed",
            files_created=[
                {"path": "src/main.py", "lines": 150, "purpose": "Main entry point"}
            ],
            dependencies_installed=["fastapi", "uvicorn"],
            ready_for_testing=True
        )
    
    Example for bug fix:
        submit_implementation_status(
            project_id=1,
            status="fixed",
            bugs_addressed=[
                {
                    "original_issue": "TypeError in parse_input()",
                    "fix_applied": "Added null check before processing",
                    "file": "src/parser.py",
                    "line": 42
                }
            ],
            ready_for_testing=True
        )
    """
    try:
        await _init_db_if_needed()
        from database.db import set_project_implementation_status_json
        
        # Validate status
        valid_statuses = ("completed", "fixed", "in_progress", "blocked")
        if status not in valid_statuses:
            return {"success": False, "error": f"status must be one of: {valid_statuses}"}
        
        # Build implementation status data
        implementation_data = {
            "status": status,
            "files_created": files_created or [],
            "files_modified": files_modified or [],
            "dependencies_installed": dependencies_installed or [],
            "commands_run": commands_run or [],
            "bugs_addressed": bugs_addressed or [],
            "notes": notes or "",
            "ready_for_testing": ready_for_testing,
            "submitted_at": datetime.utcnow().isoformat(),
        }
        
        # Save to database
        success = await set_project_implementation_status_json(project_id, implementation_data)
        
        if success:
            logger.info(f"Implementation status submitted for project {project_id}: {status}")
            return {
                "success": True,
                "message": f"Implementation status '{status}' submitted successfully"
            }
        else:
            logger.error(f"Project {project_id} not found")
            return {"success": False, "error": f"Project {project_id} not found"}
    
    except Exception as e:
        logger.error(f"Error submitting implementation status: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_implementation_status(project_id: int) -> dict:
    """
    Get the latest implementation status for a project. Use this tool to see what the Developer did.
    
    Args:
        project_id: The project ID to get implementation status for (required)
    
    Returns:
        Dictionary with implementation status data
    """
    try:
        await _init_db_if_needed()
        from database.db import get_project_implementation_status_json
        
        impl_status = await get_project_implementation_status_json(project_id)
        
        if impl_status:
            return {
                "success": True,
                "implementation_status": impl_status
            }
        else:
            return {
                "success": True,
                "implementation_status": None,
                "message": "No implementation status found for this project"
            }
    
    except Exception as e:
        logger.error(f"Error getting implementation status: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_project_context(project_id: int) -> dict:
    """
    Get full project context including idea, plan, and current dev-test state.
    Use this tool to understand the complete project situation.
    
    Args:
        project_id: The project ID to get context for (required)
    
    Returns:
        Dictionary with complete project context
    """
    try:
        await _init_db_if_needed()
        from database.db import (
            get_project_by_id,
            get_project_idea_json,
            get_project_plan_json,
            get_project_test_result_json,
            get_project_implementation_status_json
        )
        
        project = await get_project_by_id(project_id)
        if not project:
            return {"success": False, "error": f"Project {project_id} not found"}
        
        idea = await get_project_idea_json(project_id)
        plan = await get_project_plan_json(project_id)
        test_result = await get_project_test_result_json(project_id)
        impl_status = await get_project_implementation_status_json(project_id)
        
        return {
            "success": True,
            "project": {
                "id": project.id,
                "name": project.name,
                "status": project.status,
                "dev_test_iterations": project.dev_test_iterations,
                "current_agent": project.current_agent,
            },
            "idea": idea,
            "plan": plan,
            "test_result": test_result,
            "implementation_status": impl_status
        }
    
    except Exception as e:
        logger.error(f"Error getting project context: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def clear_devtest_state(project_id: int) -> dict:
    """
    Clear test result and implementation status for a new dev-test iteration.
    Use this at the start of each iteration to reset state.
    
    Args:
        project_id: The project ID to clear state for (required)
    
    Returns:
        Dictionary with success status
    """
    try:
        await _init_db_if_needed()
        from database.db import clear_project_devtest_state
        
        success = await clear_project_devtest_state(project_id)
        
        if success:
            logger.info(f"DevTest state cleared for project {project_id}")
            return {"success": True, "message": "DevTest state cleared for new iteration"}
        else:
            return {"success": False, "error": f"Project {project_id} not found"}
    
    except Exception as e:
        logger.error(f"Error clearing devtest state: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run()
