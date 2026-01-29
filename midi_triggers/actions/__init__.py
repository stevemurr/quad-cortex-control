"""
Action system for MIDI controller.

Provides the @action decorator and ActionContext for creating actions.
"""

from .base import ActionContext, action, get_registered_actions

__all__ = ["ActionContext", "action", "get_registered_actions"]
