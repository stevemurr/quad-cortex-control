"""
Example custom action plugin.

This file demonstrates how to create custom actions.
Drop .py files in this folder and they'll be auto-discovered.
"""

from midi_controller.actions import ActionContext, action


@action("print_message")
def print_message(ctx: ActionContext, message: str = "Hello from custom action!") -> None:
    """
    Example action that prints a message.

    Args:
        ctx: Action context with MIDI message info
        message: Message to print
    """
    print(f"  -> {message}")
    print(f"     Device: {ctx.device_name}")
    print(f"     MIDI: {ctx.message}")


@action("notify")
def notify(ctx: ActionContext, title: str, body: str = "") -> None:
    """
    Send a macOS notification (example of system integration).

    Args:
        ctx: Action context
        title: Notification title
        body: Notification body text
    """
    import subprocess

    script = f'display notification "{body}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], capture_output=True)
    print(f"  -> Sent notification: {title}")
