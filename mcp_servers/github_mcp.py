"""
GitHub MCP Server for 7000%AUTO
Provides GitHub repository management functionality
"""

import base64
import logging
import os
from typing import Optional

from github import Github, GithubException
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("GitHub Server")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


def get_github() -> Optional[Github]:
    """Get authenticated GitHub client"""
    if not GITHUB_TOKEN:
        return None
    return Github(GITHUB_TOKEN)


@mcp.tool()
async def create_repo(name: str, description: str, private: bool = False) -> dict:
    """
    Create a new GitHub repository.
    
    Args:
        name: Repository name (kebab-case recommended)
        description: Repository description
        private: Whether the repo should be private (default False)
    
    Returns:
        Dictionary with repository URL and details
    """
    try:
        gh = get_github()
        if not gh:
            return {"success": False, "error": "GitHub token not configured"}
        
        user = gh.get_user()
        repo = user.create_repo(
            name=name,
            description=description,
            private=private,
            auto_init=True,
            has_issues=True,
            has_wiki=False,
            has_downloads=True
        )
        
        logger.info(f"Created repository: {repo.html_url}")
        
        return {
            "success": True,
            "repo": {
                "name": repo.name,
                "full_name": repo.full_name,
                "url": repo.html_url,
                "clone_url": repo.clone_url,
                "description": repo.description
            }
        }
    
    except GithubException as e:
        logger.error(f"GitHub API error: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error creating repo: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def push_files(repo: str, files: dict, message: str, branch: str = "main") -> dict:
    """
    Push multiple files to a GitHub repository.
    
    Args:
        repo: Repository name (username/repo or just repo name)
        files: Dictionary of {path: content} for files to push
        message: Commit message
        branch: Target branch (default "main")
    
    Returns:
        Dictionary with commit details
    """
    try:
        gh = get_github()
        if not gh:
            return {"success": False, "error": "GitHub token not configured"}
        
        # Get repository
        if "/" not in repo:
            user = gh.get_user()
            repo_obj = user.get_repo(repo)
        else:
            repo_obj = gh.get_repo(repo)
        
        # Get the branch reference
        try:
            ref = repo_obj.get_git_ref(f"heads/{branch}")
            base_sha = ref.object.sha
        except GithubException:
            # Branch doesn't exist, create from default branch
            default_branch = repo_obj.default_branch
            ref = repo_obj.get_git_ref(f"heads/{default_branch}")
            base_sha = ref.object.sha
        
        # Create blobs for each file
        tree_elements = []
        for path, content in files.items():
            blob = repo_obj.create_git_blob(content, "utf-8")
            tree_elements.append({
                "path": path,
                "mode": "100644",
                "type": "blob",
                "sha": blob.sha
            })
        
        # Create tree
        base_tree = repo_obj.get_git_tree(base_sha)
        tree = repo_obj.create_git_tree(tree_elements, base_tree)
        
        # Create commit
        parent = repo_obj.get_git_commit(base_sha)
        commit = repo_obj.create_git_commit(message, tree, [parent])
        
        # Update reference
        ref.edit(commit.sha)
        
        logger.info(f"Pushed {len(files)} files to {repo_obj.full_name}")
        
        return {
            "success": True,
            "commit": {
                "sha": commit.sha,
                "message": message,
                "url": f"{repo_obj.html_url}/commit/{commit.sha}"
            },
            "files_pushed": list(files.keys())
        }
    
    except GithubException as e:
        logger.error(f"GitHub API error: {e}")
        return {"success": False, "error": str(e)}
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
    Create a release on GitHub.
    
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
    try:
        gh = get_github()
        if not gh:
            return {"success": False, "error": "GitHub token not configured"}
        
        if "/" not in repo:
            user = gh.get_user()
            repo_obj = user.get_repo(repo)
        else:
            repo_obj = gh.get_repo(repo)
        
        release = repo_obj.create_git_release(
            tag=tag,
            name=name,
            message=body,
            draft=draft,
            prerelease=prerelease
        )
        
        logger.info(f"Created release {tag} for {repo_obj.full_name}")
        
        return {
            "success": True,
            "release": {
                "tag": tag,
                "name": name,
                "url": release.html_url,
                "id": release.id
            }
        }
    
    except GithubException as e:
        logger.error(f"GitHub API error: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error creating release: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def setup_actions(repo: str, workflow_content: str, workflow_name: str = "ci.yml") -> dict:
    """
    Set up GitHub Actions workflow.
    
    Args:
        repo: Repository name
        workflow_content: YAML content for the workflow
        workflow_name: Workflow file name (default "ci.yml")
    
    Returns:
        Dictionary with workflow path
    """
    try:
        workflow_path = f".github/workflows/{workflow_name}"
        
        result = await push_files(
            repo=repo,
            files={workflow_path: workflow_content},
            message=f"Add GitHub Actions workflow: {workflow_name}"
        )
        
        if result["success"]:
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
    try:
        gh = get_github()
        if not gh:
            return {"success": False, "error": "GitHub token not configured"}
        
        if "/" not in repo:
            user = gh.get_user()
            repo_obj = user.get_repo(repo)
        else:
            repo_obj = gh.get_repo(repo)
        
        return {
            "success": True,
            "repo": {
                "name": repo_obj.name,
                "full_name": repo_obj.full_name,
                "url": repo_obj.html_url,
                "description": repo_obj.description,
                "stars": repo_obj.stargazers_count,
                "forks": repo_obj.forks_count,
                "default_branch": repo_obj.default_branch,
                "language": repo_obj.language
            }
        }
    
    except GithubException as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run()
