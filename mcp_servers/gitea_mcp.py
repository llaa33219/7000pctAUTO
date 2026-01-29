"""
Gitea MCP Server for 7000%AUTO
Provides Gitea repository management functionality
"""

import base64
import logging
import os
from typing import Optional, Dict, Any

import httpx
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("Gitea Server")

GITEA_TOKEN = os.getenv("GITEA_TOKEN", "")
GITEA_URL = os.getenv("GITEA_URL", "https://7000pct.gitea.bloupla.net")
GITEA_USERNAME = os.getenv("GITEA_USERNAME", "")


def get_api_base_url() -> str:
    """Get the Gitea API base URL"""
    return f"{GITEA_URL.rstrip('/')}/api/v1"


def get_auth_headers() -> Dict[str, str]:
    """Get authentication headers for Gitea API"""
    return {
        "Authorization": f"token {GITEA_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def get_gitea_username() -> str:
    """Get Gitea username from env or fetch from API"""
    if GITEA_USERNAME:
        return GITEA_USERNAME
    
    if not GITEA_TOKEN:
        return ""
    
    try:
        async with httpx.AsyncClient(
            base_url=get_api_base_url(),
            headers=get_auth_headers(),
            timeout=30.0,
        ) as client:
            response = await client.get("/user")
            if response.status_code == 200:
                return response.json().get("login", "")
    except Exception as e:
        logger.error(f"Failed to get Gitea username: {e}")
    
    return ""


@mcp.tool()
async def create_repo(name: str, description: str, private: bool = False) -> dict:
    """
    Create a new Gitea repository.
    
    Args:
        name: Repository name (kebab-case recommended)
        description: Repository description
        private: Whether the repo should be private (default False)
    
    Returns:
        Dictionary with repository URL and details
    """
    if not GITEA_TOKEN:
        return {"success": False, "error": "Gitea token not configured"}
    
    try:
        async with httpx.AsyncClient(
            base_url=get_api_base_url(),
            headers=get_auth_headers(),
            timeout=30.0,
        ) as client:
            response = await client.post(
                "/user/repos",
                json={
                    "name": name,
                    "description": description,
                    "private": private,
                    "auto_init": True,
                    "default_branch": "main",
                }
            )
            
            if response.status_code in (200, 201):
                repo_data = response.json()
                logger.info(f"Created repository: {repo_data.get('html_url')}")
                
                return {
                    "success": True,
                    "repo": {
                        "name": repo_data.get("name"),
                        "full_name": repo_data.get("full_name"),
                        "url": repo_data.get("html_url"),
                        "clone_url": repo_data.get("clone_url"),
                        "description": repo_data.get("description"),
                    }
                }
            else:
                error_msg = response.json().get("message", response.text)
                logger.error(f"Gitea API error: {error_msg}")
                return {"success": False, "error": error_msg}
    
    except Exception as e:
        logger.error(f"Error creating repo: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def push_files(repo: str, files: dict, message: str, branch: str = "main") -> dict:
    """
    Push multiple files to a Gitea repository.
    
    Args:
        repo: Repository name (username/repo or just repo name)
        files: Dictionary of {path: content} for files to push
        message: Commit message
        branch: Target branch (default "main")
    
    Returns:
        Dictionary with commit details
    """
    if not GITEA_TOKEN:
        return {"success": False, "error": "Gitea token not configured"}
    
    try:
        # Determine owner and repo name
        if "/" in repo:
            owner, repo_name = repo.split("/", 1)
        else:
            owner = await get_gitea_username()
            repo_name = repo
        
        if not owner:
            return {"success": False, "error": "Could not determine repository owner"}
        
        pushed_files = []
        last_commit = None
        
        async with httpx.AsyncClient(
            base_url=get_api_base_url(),
            headers=get_auth_headers(),
            timeout=30.0,
        ) as client:
            for file_path, content in files.items():
                # Check if file exists to determine if we need to update or create
                check_response = await client.get(f"/repos/{owner}/{repo_name}/contents/{file_path}")
                
                file_data = {
                    "content": base64.b64encode(content.encode()).decode(),
                    "message": message,
                    "branch": branch,
                }
                
                if check_response.status_code == 200:
                    # File exists, need to include SHA for update
                    existing = check_response.json()
                    file_data["sha"] = existing.get("sha")
                    response = await client.put(
                        f"/repos/{owner}/{repo_name}/contents/{file_path}",
                        json=file_data
                    )
                else:
                    # File doesn't exist, create it
                    response = await client.post(
                        f"/repos/{owner}/{repo_name}/contents/{file_path}",
                        json=file_data
                    )
                
                if response.status_code in (200, 201):
                    result = response.json()
                    last_commit = result.get("commit", {})
                    pushed_files.append(file_path)
                else:
                    error_msg = response.json().get("message", response.text)
                    logger.error(f"Failed to push {file_path}: {error_msg}")
        
        if pushed_files:
            logger.info(f"Pushed {len(pushed_files)} files to {owner}/{repo_name}")
            return {
                "success": True,
                "commit": {
                    "sha": last_commit.get("sha", "") if last_commit else "",
                    "message": message,
                    "url": f"{GITEA_URL}/{owner}/{repo_name}/commit/{last_commit.get('sha', '')}" if last_commit else ""
                },
                "files_pushed": pushed_files
            }
        else:
            return {"success": False, "error": "No files were pushed"}
    
    except Exception as e:
        logger.error(f"Error pushing files: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def create_release(
    repo: str,
    tag: str,
    name: str,
    body: str,
    draft: bool = False,
    prerelease: bool = False
) -> dict:
    """
    Create a release on Gitea.
    
    Args:
        repo: Repository name
        tag: Tag name (e.g., "v1.0.0")
        name: Release name
        body: Release notes/body
        draft: Whether this is a draft release
        prerelease: Whether this is a prerelease
    
    Returns:
        Dictionary with release URL
    """
    if not GITEA_TOKEN:
        return {"success": False, "error": "Gitea token not configured"}
    
    try:
        # Determine owner and repo name
        if "/" in repo:
            owner, repo_name = repo.split("/", 1)
        else:
            owner = await get_gitea_username()
            repo_name = repo
        
        if not owner:
            return {"success": False, "error": "Could not determine repository owner"}
        
        async with httpx.AsyncClient(
            base_url=get_api_base_url(),
            headers=get_auth_headers(),
            timeout=30.0,
        ) as client:
            response = await client.post(
                f"/repos/{owner}/{repo_name}/releases",
                json={
                    "tag_name": tag,
                    "name": name,
                    "body": body,
                    "draft": draft,
                    "prerelease": prerelease,
                    "target_commitish": "main",
                }
            )
            
            if response.status_code in (200, 201):
                release_data = response.json()
                logger.info(f"Created release {tag} for {owner}/{repo_name}")
                
                return {
                    "success": True,
                    "release": {
                        "tag": tag,
                        "name": name,
                        "url": release_data.get("html_url", f"{GITEA_URL}/{owner}/{repo_name}/releases/tag/{tag}"),
                        "id": release_data.get("id"),
                    }
                }
            else:
                error_msg = response.json().get("message", response.text)
                logger.error(f"Gitea API error: {error_msg}")
                return {"success": False, "error": error_msg}
    
    except Exception as e:
        logger.error(f"Error creating release: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def setup_actions(repo: str, workflow_content: str, workflow_name: str = "ci.yml") -> dict:
    """
    Set up Gitea Actions workflow.
    
    Args:
        repo: Repository name
        workflow_content: YAML content for the workflow
        workflow_name: Workflow file name (default "ci.yml")
    
    Returns:
        Dictionary with workflow path
    """
    try:
        workflow_path = f".gitea/workflows/{workflow_name}"
        
        result = await push_files(
            repo=repo,
            files={workflow_path: workflow_content},
            message=f"Add Gitea Actions workflow: {workflow_name}"
        )
        
        if result.get("success"):
            return {
                "success": True,
                "workflow": {
                    "path": workflow_path,
                    "name": workflow_name
                }
            }
        return result
    
    except Exception as e:
        logger.error(f"Error setting up actions: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_repo_info(repo: str) -> dict:
    """
    Get repository information.
    
    Args:
        repo: Repository name
    
    Returns:
        Dictionary with repository details
    """
    if not GITEA_TOKEN:
        return {"success": False, "error": "Gitea token not configured"}
    
    try:
        # Determine owner and repo name
        if "/" in repo:
            owner, repo_name = repo.split("/", 1)
        else:
            owner = await get_gitea_username()
            repo_name = repo
        
        if not owner:
            return {"success": False, "error": "Could not determine repository owner"}
        
        async with httpx.AsyncClient(
            base_url=get_api_base_url(),
            headers=get_auth_headers(),
            timeout=30.0,
        ) as client:
            response = await client.get(f"/repos/{owner}/{repo_name}")
            
            if response.status_code == 200:
                repo_data = response.json()
                return {
                    "success": True,
                    "repo": {
                        "name": repo_data.get("name"),
                        "full_name": repo_data.get("full_name"),
                        "url": repo_data.get("html_url"),
                        "description": repo_data.get("description"),
                        "stars": repo_data.get("stars_count", 0),
                        "forks": repo_data.get("forks_count", 0),
                        "default_branch": repo_data.get("default_branch"),
                        "language": repo_data.get("language"),
                    }
                }
            else:
                error_msg = response.json().get("message", response.text)
                return {"success": False, "error": error_msg}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run()
