"""
Built-in shell command action.
"""

import subprocess

from .base import ActionContext, action


@action("shell")
def shell(ctx: ActionContext, command: str) -> None:
    """Execute a shell command."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print(f"  -> Executed: {command}")
            if result.stdout.strip():
                for line in result.stdout.strip().split("\n")[:3]:
                    print(f"     {line}")
        else:
            print(f"  -> Command failed: {command}")
            if result.stderr.strip():
                print(f"     {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        print(f"  -> Command timed out: {command}")
    except Exception as e:
        print(f"  -> Error running command: {e}")
