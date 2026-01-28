"""
OpenCode SDK Client Wrapper for 7000%AUTO
Uses OpenCode SDK (opencode-ai) for AI agent interactions.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any, AsyncIterator, List

from config import settings

logger = logging.getLogger(__name__)

# Agent system prompts cache
_AGENT_PROMPTS: Dict[str, str] = {}

# OpenCode configuration cache
_OPENCODE_CONFIG: Optional[Dict[str, Any]] = None

# Pre-compiled regex patterns for performance
_FRONTMATTER_PATTERN = re.compile(r'^---\s*\n.*?\n---\s*\n', re.DOTALL)
_VALID_AGENT_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


def _load_opencode_config() -> Dict[str, Any]:
    """Load opencode.json configuration"""
    global _OPENCODE_CONFIG
    if _OPENCODE_CONFIG is not None:
        return _OPENCODE_CONFIG
    
    config_path = Path("opencode.json")
    if config_path.exists():
        try:
            _OPENCODE_CONFIG = json.loads(config_path.read_text(encoding="utf-8"))
            return _OPENCODE_CONFIG
        except Exception as e:
            logger.warning(f"Failed to load opencode.json: {e}")
    
    # Default configuration with proper provider object format
    _OPENCODE_CONFIG = {
        "provider": {
            "minimax": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "MiniMax",
                "options": {
                    "baseURL": "https://api.minimax.chat/v1",
                    "apiKey": "{env:MINIMAX_API_KEY}"
                },
                "models": {
                    "MiniMax-M2.1": {
                        "name": "MiniMax M2.1"
                    }
                }
            }
        },
        "model": "minimax/MiniMax-M2.1"
    }
    return _OPENCODE_CONFIG


def _remove_yaml_frontmatter(content: str) -> str:
    """Remove YAML frontmatter (---...---) from markdown content"""
    return _FRONTMATTER_PATTERN.sub('', content).strip()


def _load_agent_prompt(agent_name: str) -> str:
    """Load agent system prompt from .opencode/agent/{agent_name}.md"""
    if agent_name in _AGENT_PROMPTS:
        return _AGENT_PROMPTS[agent_name]
    
    # Validate agent name to prevent path traversal
    if not _VALID_AGENT_NAME_PATTERN.match(agent_name):
        logger.warning(f"Invalid agent name format: {agent_name}")
        fallback = f"You are {agent_name}, an AI assistant. Complete the task given to you."
        _AGENT_PROMPTS[agent_name] = fallback
        return fallback
    
    agent_path = Path(f".opencode/agent/{agent_name}.md")
    if agent_path.exists():
        content = agent_path.read_text(encoding="utf-8")
        # Remove YAML frontmatter if present
        content = _remove_yaml_frontmatter(content)
        _AGENT_PROMPTS[agent_name] = content
        return content
    
    # Fallback generic prompt
    fallback = f"You are {agent_name}, an AI assistant. Complete the task given to you."
    _AGENT_PROMPTS[agent_name] = fallback
    return fallback


class OpenCodeError(Exception):
    """Base exception for OpenCode client errors"""
    pass


class OpenCodeClient:
    """
    Client for AI agent interactions using OpenCode SDK.
    
    This client wraps the opencode-ai SDK to provide session management
    and message handling for the 7000%AUTO agent pipeline.
    
    Agents are specified via the 'mode' parameter in session.chat(),
    which corresponds to agents defined in opencode.json under the 'agent' key.
    The 'system' parameter provides a fallback prompt from .opencode/agent/*.md files.
    Each agent in opencode.json has its own model, prompt, tools, and permissions.
    """
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.OPENCODE_BASE_URL
        self._client: Optional[Any] = None
        self._sessions: Dict[str, Dict[str, Any]] = {}
        
        # Load configuration from opencode.json
        config = _load_opencode_config()
        
        # Extract provider_id and model_id from config
        # model format is "provider/model" (e.g., "minimax/MiniMax-M2.1")
        model_str = config.get("model", "minimax/MiniMax-M2.1")
        if "/" in model_str:
            self.provider_id, self.model_id = model_str.split("/", 1)
        else:
            # Fallback: get first provider from provider object, or default to minimax
            provider_config = config.get("provider", {})
            if isinstance(provider_config, dict) and provider_config:
                self.provider_id = next(iter(provider_config.keys()))
            else:
                self.provider_id = "minimax"
            self.model_id = model_str
    
    async def _get_client(self):
        """Get or create AsyncOpencode client"""
        if self._client is None:
            try:
                from opencode_ai import AsyncOpencode
                
                client_kwargs = {}
                if self.base_url:
                    client_kwargs["base_url"] = self.base_url
                
                self._client = AsyncOpencode(**client_kwargs)
                logger.info(f"OpenCode client initialized (base_url: {self.base_url or 'default'})")
            except ImportError:
                raise OpenCodeError("opencode-ai package not installed. Run: pip install opencode-ai")
            except Exception as e:
                raise OpenCodeError(f"Failed to initialize OpenCode client: {e}")
        
        return self._client
    
    async def _close_client(self):
        """Close the OpenCode client"""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception as e:
                logger.warning(f"Error closing OpenCode client: {e}")
            finally:
                self._client = None
    
    async def create_session(self, agent_name: str) -> str:
        """
        Create a new session for an agent.
        
        Args:
            agent_name: Name of the agent (e.g., "ideator", "planner")
            
        Returns:
            Session ID string
        """
        try:
            client = await self._get_client()
            
            # Create session via OpenCode SDK
            # Pass extra_body={} to send empty JSON body (server expects JSON even if empty)
            session = await client.session.create(extra_body={})
            session_id = session.id
            
            # Store session metadata including agent name and prompt
            system_prompt = _load_agent_prompt(agent_name)
            self._sessions[session_id] = {
                "agent": agent_name,
                "system_prompt": system_prompt,
                "opencode_session": session,
            }
            
            logger.info(f"Created session {session_id} for agent {agent_name}")
            return session_id
            
        except OpenCodeError:
            raise
        except Exception as e:
            server_url = self.base_url or "default"
            logger.error(f"Failed to create session for agent {agent_name}: {e}")
            raise OpenCodeError(
                f"Failed to create session (is OpenCode server running at {server_url}?): {e}"
            )
    
    async def send_message(self, session_id: str, message: str) -> Dict[str, Any]:
        """
        Send a message and get response from OpenCode.
        
        Args:
            session_id: Session ID from create_session
            message: User message to send
            
        Returns:
            Dict with "content" (raw response) and "parsed" (extracted JSON)
        """
        if session_id not in self._sessions:
            raise OpenCodeError(f"Session {session_id} not found")
        
        session_data = self._sessions[session_id]
        agent_name = session_data["agent"]
        
        try:
            client = await self._get_client()
            
            logger.info(f"Sending message to session {session_id} (agent: {agent_name})")
            
            # Build message parts
            parts: List[Dict[str, Any]] = [
                {"type": "text", "text": message}
            ]
            
            # Enable all MCP tools for the agent
            # This allows agents to use search, github, x_api, database tools
            tools: Dict[str, bool] = {"*": True}
            
            # Send chat message via OpenCode SDK
            # - mode: specifies agent/mode to use (maps to agents in opencode.json)
            # - system: provides fallback system prompt if mode isn't recognized
            # - tools: enables MCP server tools defined in opencode.json
            # OpenCode server loads agent config from opencode.json based on mode
            response = await client.session.chat(
                session_id,
                model_id=self.model_id,
                provider_id=self.provider_id,
                parts=parts,
                mode=agent_name,  # Specify agent mode from opencode.json
                system=session_data["system_prompt"],  # Fallback system prompt
                tools=tools,
            )
            
            # Check for errors in the response
            if hasattr(response, 'error') and response.error:
                error_msg = str(response.error)
                logger.error(f"OpenCode response error: {error_msg}")
                raise OpenCodeError(f"Agent error: {error_msg}")
            
            # Extract content from response
            content = self._extract_response_content(response)
            
            logger.info(f"Received response for session {session_id} ({len(content)} chars)")
            
            return {
                "content": content,
                "parsed": self.parse_json_from_response(content)
            }
            
        except OpenCodeError:
            raise
        except Exception as e:
            server_url = self.base_url or "default"
            logger.error(f"Failed to send message to session {session_id}: {e}")
            raise OpenCodeError(
                f"Failed to send message (is OpenCode server running at {server_url}?): {e}"
            )
    
    def _extract_response_content(self, response: Any) -> str:
        """
        Extract text content from OpenCode AssistantMessage response.
        
        The response structure may vary, so we try multiple approaches.
        Based on SDK investigation, AssistantMessage has:
        - id, cost, mode, api_model_id, path, provider_id, role, session_id,
          system, time, tokens, error, summary
        - The text content is typically in path.parts
        """
        # First, check path.parts which is the primary location for content
        if hasattr(response, 'path'):
            path = response.path
            if hasattr(path, 'parts'):
                content = self._extract_parts_content(path.parts)
                if content:
                    logger.debug("Extracted content from response.path.parts")
                    return content
        
        # Try direct parts attribute
        if hasattr(response, 'parts'):
            parts = response.parts
            if isinstance(parts, list):
                texts = []
                for part in parts:
                    if isinstance(part, dict) and part.get('type') == 'text':
                        texts.append(part.get('text', ''))
                    elif hasattr(part, 'text'):
                        texts.append(str(part.text))
                if texts:
                    logger.debug("Extracted content from response.parts")
                    return '\n'.join(texts)
        
        # Try content attribute
        if hasattr(response, 'content'):
            content = response.content
            if content:
                logger.debug("Extracted content from response.content")
                return str(content)
        
        # Try text attribute
        if hasattr(response, 'text'):
            text = response.text
            if text:
                logger.debug("Extracted content from response.text")
                return str(text)
        
        # Fallback: convert response to string via model_dump
        if hasattr(response, 'model_dump'):
            logger.debug("Falling back to model_dump for content extraction")
            dump = response.model_dump()
            # Try to extract text from the dumped structure
            if 'path' in dump and 'parts' in dump['path']:
                parts = dump['path']['parts']
                texts = [p.get('text', '') for p in parts if p.get('type') == 'text']
                if texts:
                    return '\n'.join(texts)
            return json.dumps(dump, indent=2)
        
        logger.warning("Could not extract structured content, using str()")
        return str(response)
    
    def _extract_parts_content(self, parts: Any) -> str:
        """Extract text content from message parts"""
        if not parts:
            return ""
        
        texts = []
        for part in parts:
            if isinstance(part, dict):
                if part.get('type') == 'text':
                    texts.append(part.get('text', ''))
            elif hasattr(part, 'text'):
                texts.append(str(part.text))
            elif hasattr(part, 'content'):
                texts.append(str(part.content))
        
        return '\n'.join(texts)
    
    async def stream_response(self, session_id: str, message: str) -> AsyncIterator[str]:
        """
        Stream response from agent.
        
        Args:
            session_id: Session ID from create_session
            message: User message to send
            
        Yields:
            Response text chunks
        """
        if session_id not in self._sessions:
            raise OpenCodeError(f"Session {session_id} not found")
        
        session_data = self._sessions[session_id]
        
        try:
            client = await self._get_client()
            
            # Build message parts
            parts: List[Dict[str, Any]] = [
                {"type": "text", "text": message}
            ]
            
            # Enable all MCP tools
            tools: Dict[str, bool] = {"*": True}
            
            # Use streaming response with mode parameter
            async with client.session.with_streaming_response.chat(
                session_id,
                model_id=self.model_id,
                provider_id=self.provider_id,
                parts=parts,
                mode=session_data["agent"],  # Specify agent mode from opencode.json
                system=session_data["system_prompt"],  # Fallback system prompt
                tools=tools,
            ) as response:
                async for chunk in response.iter_text():
                    if chunk:
                        yield chunk
                        
        except OpenCodeError:
            raise
        except Exception as e:
            server_url = self.base_url or "default"
            logger.error(f"Failed to stream response for session {session_id}: {e}")
            raise OpenCodeError(
                f"Failed to stream response (is OpenCode server running at {server_url}?): {e}"
            )
    
    async def close_session(self, session_id: str):
        """
        Close a session.
        
        Args:
            session_id: Session ID to close
        """
        if session_id in self._sessions:
            try:
                client = await self._get_client()
                await client.session.delete(session_id)
            except Exception as e:
                logger.warning(f"Error deleting session {session_id}: {e}")
            finally:
                del self._sessions[session_id]
                logger.info(f"Closed session {session_id}")
    
    async def close(self):
        """Close the client and all sessions"""
        # Close all sessions
        session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            await self.close_session(session_id)
        
        # Close the client
        await self._close_client()
    
    @staticmethod
    def parse_json_from_response(content: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from agent response.
        
        Tries multiple patterns to find and parse JSON:
        1. JSON in code blocks (```json ... ``` or ``` ... ```)
        2. JSON object directly in content ({ ... })
        3. Entire content as JSON
        
        Args:
            content: Response content string
            
        Returns:
            Parsed JSON dict or None if no valid JSON found
        """
        if not content:
            return None
        
        # Try to find JSON in code blocks (```json ... ``` or ``` ... ```)
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON object directly in content
        # Look for { ... } pattern
        json_obj_match = re.search(r'\{[\s\S]*\}', content)
        if json_obj_match:
            try:
                return json.loads(json_obj_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # Try to parse the whole content as JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        return None
