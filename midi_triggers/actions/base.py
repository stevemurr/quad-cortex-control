"""
Base action infrastructure.

Provides ActionContext and the @action decorator for registering actions.
"""

from dataclasses import dataclass
from typing import Any, Callable

from ..ha.client import HAClient
from ..messages import MidiMessage


@dataclass
class ActionContext:
    """Context passed to all actions."""
    ha: HAClient | None
    message: MidiMessage
    device_name: str
    cycle_index: int | None = None  # Current preset index if cycling
    preset_value: Any = None  # Current preset value if cycling


# Global registry of actions
_action_registry: dict[str, Callable] = {}


def action(name: str | None = None):
    """
    Decorator to register an action.

    Usage:
        @action("my_action")
        def my_action(ctx: ActionContext, param1: str) -> None:
            ...

        # Or use function name as action name:
        @action()
        def another_action(ctx: ActionContext) -> None:
            ...
    """
    def decorator(func: Callable) -> Callable:
        action_name = name if name else func.__name__
        _action_registry[action_name] = func
        return func

    # Handle @action without parentheses
    if callable(name):
        func = name
        _action_registry[func.__name__] = func
        return func

    return decorator


def get_registered_actions() -> dict[str, Callable]:
    """Get a copy of all registered actions."""
    return _action_registry.copy()


def register_action(name: str, func: Callable) -> None:
    """Manually register an action."""
    _action_registry[name] = func
