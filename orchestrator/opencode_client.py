"""
OpenCode SDK Client Wrapper for 7000%AUTO
"""

import json
import logging
import re
from typing import Optional, Dict, Any, AsyncIterator

logger = logging.getLogger(__name__)


class OpenCodeError(Exception):
    """Base exception for OpenCode client errors"""
    pass


class OpenCodeClient:
    """Wrapper for OpenCode SDK interactions"""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url
        self._sessions: Dict[str, Any] = {}
    
    async def create_session(self, agent_name: str) -> str:
        """Create a new session for an agent"""
        try:
            # In production, this would use the actual OpenCode SDK
            # For now, we simulate session creation
            session_id = f"{agent_name}_{id(self)}"
            self._sessions[session_id] = {
                "agent": agent_name,
                "messages": []
            }
            logger.info(f"Created session {session_id} for agent {agent_name}")
            return session_id
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise OpenCodeError(f"Failed to create session: {e}")
    
    async def send_message(self, session_id: str, message: str) -> Dict[str, Any]:
        """Send a message and get response"""
        try:
            if session_id not in self._sessions:
                raise OpenCodeError(f"Session {session_id} not found")
            
            # In production, this would call the actual OpenCode API
            # For now, we return a placeholder response
            logger.info(f"Sending message to session {session_id}")
            
            response = {
                "content": "Response from agent",
                "parsed": None
            }
            
            return response
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise OpenCodeError(f"Failed to send message: {e}")
    
    async def stream_response(self, session_id: str, message: str) -> AsyncIterator[str]:
        """Stream response from agent"""
        try:
            if session_id not in self._sessions:
                raise OpenCodeError(f"Session {session_id} not found")
            
            # In production, this would stream from the actual API
            yield "Streaming response..."
            
        except Exception as e:
            logger.error(f"Failed to stream response: {e}")
            raise OpenCodeError(f"Failed to stream response: {e}")
    
    async def close_session(self, session_id: str):
        """Close a session"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Closed session {session_id}")
    
    @staticmethod
    def parse_json_from_response(content: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from agent response"""
        # Try to find JSON in code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass
        
        # Try to parse the whole content as JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        return None
