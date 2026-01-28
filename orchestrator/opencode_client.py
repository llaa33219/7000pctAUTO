"""
OpenCode SDK Client Wrapper for 7000%AUTO
Uses OpenCode SDK (opencode-ai) for AI agent interactions.
"""

import asyncio
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
    
    async def send_message(self, session_id: str, message: str, timeout_seconds: int = 120) -> Dict[str, Any]:
        """
        Send a message and get response from OpenCode.
        
        Args:
            session_id: Session ID from create_session
            message: User message to send
            timeout_seconds: Maximum time to wait for agent completion (default 120s)
            
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
            
            # session.chat() returns immediately - agent may still be running
            # Check if response is complete by looking at time.completed
            # If not complete, poll until agent finishes
            await self._wait_for_completion(client, session_id, response, timeout_seconds)
            
            # Now fetch the actual message content
            content = await self._fetch_message_content(client, session_id)
            
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
    
    async def _wait_for_completion(
        self, 
        client: Any, 
        session_id: str, 
        initial_response: Any,
        timeout_seconds: int
    ) -> None:
        """
        Wait for agent to complete processing.
        
        The session.chat() method returns immediately with an AssistantMessage.
        If time.completed is None, the agent is still running.
        We need to poll session.messages() until the specific message is complete.
        
        Args:
            client: OpenCode client instance
            session_id: Session ID
            initial_response: Initial AssistantMessage from session.chat()
            timeout_seconds: Maximum time to wait for completion
        """
        # Get the message ID to track the specific message
        message_id = getattr(initial_response, 'id', None)
        
        # Check for error in initial response
        self._check_response_for_error(initial_response, "initial response")
        
        # Check if initial response is already complete
        time_info = getattr(initial_response, 'time', None)
        if time_info:
            completed = getattr(time_info, 'completed', None)
            if completed is not None:
                logger.debug(f"Session {session_id}: Agent already completed (message: {message_id})")
                return
        
        # Poll for completion
        poll_interval = 1.0  # seconds
        max_polls = int(timeout_seconds / poll_interval)
        
        logger.info(f"Session {session_id}: Agent still running (message: {message_id}), polling for completion...")
        
        for poll_count in range(max_polls):
            await asyncio.sleep(poll_interval)
            
            try:
                # Fetch messages to check completion status
                messages_response = await client.session.messages(session_id)
                
                if not messages_response:
                    continue
                
                # Find the specific message by ID, or fall back to last assistant message
                target_message = None
                
                for msg in reversed(messages_response):
                    info = getattr(msg, 'info', None)
                    if not info:
                        continue
                    
                    # Match by message ID if available
                    if message_id:
                        msg_id = getattr(info, 'id', None)
                        if msg_id == message_id:
                            target_message = msg
                            break
                    else:
                        # Fallback: match last assistant message
                        role = getattr(info, 'role', None)
                        if role == 'assistant':
                            target_message = msg
                            break
                
                if target_message:
                    info = getattr(target_message, 'info', None)
                    if info:
                        # Check for errors in the message
                        self._check_response_for_error(info, f"message {message_id}")
                        
                        # Check time.completed on the message info
                        time_info = getattr(info, 'time', None)
                        if time_info:
                            completed = getattr(time_info, 'completed', None)
                            if completed is not None:
                                logger.info(f"Session {session_id}: Agent completed after {poll_count + 1}s (message: {message_id})")
                                return
                
                # Log progress every 10 polls
                if (poll_count + 1) % 10 == 0:
                    logger.info(f"Session {session_id}: Still waiting... ({poll_count + 1}s elapsed)")
                    
            except OpenCodeError:
                # Re-raise OpenCodeError (API errors, etc.)
                raise
            except Exception as e:
                logger.warning(f"Session {session_id}: Error polling for completion: {e}")
                # Continue polling despite other errors
        
        # Timeout reached
        logger.warning(f"Session {session_id}: Timeout after {timeout_seconds}s waiting for agent completion")
        raise OpenCodeError(f"Agent timed out after {timeout_seconds} seconds")
    
    def _check_response_for_error(self, response: Any, context: str = "") -> None:
        """
        Check response object for error information and raise OpenCodeError if found.
        
        Args:
            response: Response object to check (could be message info or full response)
            context: Context string for error messages
            
        Raises:
            OpenCodeError: If an error is detected in the response
        """
        if response is None:
            return
        
        # Check for 'error' attribute directly
        error = getattr(response, 'error', None)
        if error:
            error_message = self._extract_error_message(error)
            if error_message:
                logger.error(f"API error detected in {context}: {error_message}")
                raise OpenCodeError(f"API Error: {error_message}")
        
        # Check via model_dump if available
        if hasattr(response, 'model_dump'):
            try:
                dump = response.model_dump()
                if isinstance(dump, dict) and 'error' in dump and dump['error']:
                    error_data = dump['error']
                    error_message = self._extract_error_message_from_dict(error_data)
                    if error_message:
                        logger.error(f"API error detected in {context} (from dump): {error_message}")
                        raise OpenCodeError(f"API Error: {error_message}")
            except Exception as e:
                logger.debug(f"Could not check model_dump for errors: {e}")
    
    def _extract_error_message(self, error: Any) -> Optional[str]:
        """
        Extract a human-readable error message from an error object.
        
        Args:
            error: Error object (could be ProviderAuthError, APIError, etc.)
            
        Returns:
            Error message string or None
        """
        if error is None:
            return None
        
        # Try to get error name/type
        error_name = getattr(error, 'name', None) or type(error).__name__
        
        # Try to get data.message or data.error
        data = getattr(error, 'data', None)
        if data:
            message = getattr(data, 'message', None) or getattr(data, 'error', None)
            if message:
                return f"{error_name}: {message}"
            # Try dict access
            if hasattr(data, 'get'):
                message = data.get('message') or data.get('error')
                if message:
                    return f"{error_name}: {message}"
        
        # Try direct message attribute
        message = getattr(error, 'message', None)
        if message:
            return f"{error_name}: {message}"
        
        # Check for common auth error patterns
        if 'Auth' in error_name or 'auth' in str(error).lower():
            return f"{error_name}: Authentication failed - check your MINIMAX_API_KEY"
        
        # Fallback to string representation
        error_str = str(error)
        if error_str and error_str != str(type(error)):
            # Truncate very long error messages
            if len(error_str) > 200:
                error_str = error_str[:200] + "..."
            return f"{error_name}: {error_str}"
        
        return error_name
    
    def _extract_error_message_from_dict(self, error_data: Any) -> Optional[str]:
        """
        Extract error message from a dict representation of an error.
        
        Args:
            error_data: Error data as dict
            
        Returns:
            Error message string or None
        """
        if not isinstance(error_data, dict):
            return str(error_data) if error_data else None
        
        error_name = error_data.get('name', 'Error')
        
        # Check for nested data
        data = error_data.get('data', {})
        if isinstance(data, dict):
            message = data.get('message') or data.get('error')
            if message:
                return f"{error_name}: {message}"
        
        # Direct message
        message = error_data.get('message') or error_data.get('error')
        if message:
            return f"{error_name}: {message}"
        
        # Check for auth errors
        if 'Auth' in error_name or 'ProviderAuth' in error_name:
            return f"{error_name}: Authentication failed - check your MINIMAX_API_KEY"
        
        return error_name if error_name != 'Error' else None

    async def _fetch_message_content(self, client: Any, session_id: str) -> str:
        """
        Fetch actual message content from session messages.
        
        The session.chat() method returns AssistantMessage which only contains metadata.
        To get actual text content, we need to call session.messages() and extract
        TextPart content from the last assistant message.
        
        Args:
            client: OpenCode client instance
            session_id: Session ID
            
        Returns:
            Extracted text content from the last assistant message
            
        Raises:
            OpenCodeError: If an API error is detected in the message
        """
        try:
            # Fetch all messages for the session
            messages_response = await client.session.messages(session_id)
            
            if not messages_response:
                logger.warning(f"No messages found for session {session_id}")
                return ""
            
            # Find the last assistant message (not user message)
            # messages_response is a list of SessionMessagesResponseItem
            # Each item has 'info' (Message with role) and 'parts' (List[Part])
            assistant_message = None
            for msg in reversed(messages_response):
                info = getattr(msg, 'info', None)
                if info:
                    role = getattr(info, 'role', None)
                    if role == 'assistant':
                        assistant_message = msg
                        break
            
            if not assistant_message:
                logger.warning(f"No assistant message found for session {session_id}")
                return ""
            
            # Check for errors in the assistant message info
            info = getattr(assistant_message, 'info', None)
            if info:
                self._check_response_for_error(info, f"session {session_id}")
            
            # Extract text from parts
            texts = []
            parts = getattr(assistant_message, 'parts', None) or []
            
            for part in parts:
                # Check if it's a TextPart (type == 'text')
                part_type = getattr(part, 'type', None)
                if part_type == 'text':
                    text = getattr(part, 'text', '')
                    if text:
                        texts.append(text)
            
            if texts:
                return '\n'.join(texts)
            
            # Fallback: try to extract from dict representation
            if hasattr(assistant_message, 'model_dump'):
                dump = assistant_message.model_dump()
                
                # Check for error in dumped data
                info_dump = dump.get('info', {})
                if isinstance(info_dump, dict) and info_dump.get('error'):
                    error_msg = self._extract_error_message_from_dict(info_dump.get('error'))
                    if error_msg:
                        logger.error(f"API error in session {session_id}: {error_msg}")
                        raise OpenCodeError(f"API Error: {error_msg}")
                
                parts_data = dump.get('parts', [])
                fallback_texts = []
                for part_data in parts_data:
                    if isinstance(part_data, dict) and part_data.get('type') == 'text':
                        text = part_data.get('text', '')
                        if text:
                            fallback_texts.append(text)
                if fallback_texts:
                    return '\n'.join(fallback_texts)
            
            # If we got here with no text content, log a warning
            logger.warning(f"Session {session_id}: No text content found in assistant message")
            return ""
            
        except OpenCodeError:
            # Re-raise OpenCodeError
            raise
        except Exception as e:
            logger.warning(f"Failed to fetch message content: {e}")
            return ""
    
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
            # Add null check for dump['path'] to prevent NoneType error
            if 'path' in dump and dump['path'] is not None and 'parts' in dump['path']:
                parts = dump['path']['parts']
                if parts:
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
