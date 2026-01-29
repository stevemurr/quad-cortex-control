"""
Plugin discovery for custom actions.

Scans the actions/ folder for Python files and loads any @action decorated functions.
"""

import importlib.util
import sys
from pathlib import Path
from typing import Callable

from .actions.base import get_registered_actions


def discover_actions(actions_dir: Path) -> dict[str, Callable]:
    """
    Discover and load all actions from a directory.

    Scans for .py files (excluding __init__.py and files starting with _),
    imports them, and returns all actions that were registered via @action.

    Args:
        actions_dir: Path to the actions directory.

    Returns:
        Dictionary mapping action names to action functions.
    """
    if not actions_dir.exists():
        return {}

    for py_file in sorted(actions_dir.glob("*.py")):
        # Skip private files and __init__.py
        if py_file.name.startswith("_"):
            continue

        try:
            load_module_from_file(py_file)
        except Exception as e:
            print(f"Warning: Failed to load action plugin {py_file.name}: {e}")

    return get_registered_actions()


def load_module_from_file(file_path: Path) -> None:
    """
    Load a Python module from a file path.

    The module is executed, which will trigger @action decorators
    and register any defined actions.
    """
    module_name = f"user_actions.{file_path.stem}"

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module spec from {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    spec.loader.exec_module(module)


def load_builtin_actions() -> None:
    """
    Load all built-in actions.

    This imports the built-in action modules to trigger their @action decorators.
    """
    # Import built-in action modules to register them
    from .actions import homeassistant  # noqa: F401
    from .actions import shell  # noqa: F401
