"""
7000%AUTO Web Dashboard

Read-only web interface for monitoring the autonomous AI system.
"""

from web.app import app, event_broadcaster, broadcast_event

__all__ = ["app", "event_broadcaster", "broadcast_event"]
