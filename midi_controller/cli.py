"""
Command-line interface for the MIDI controller.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from .broker import create_broker
from .config import load_config
from .devices import DeviceManager, list_midi_ports
from .discovery import discover_actions, load_builtin_actions
from .ha.client import HAClient
from .setup_wizard import run_setup_wizard


def cmd_run(args: argparse.Namespace) -> int:
    """Run the MIDI controller."""
    config_path = Path(args.config)

    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        print("Run 'python -m midi_controller setup' to create one.")
        return 1

    # Load config
    config = load_config(config_path)

    # Load actions
    load_builtin_actions()
    actions_dir = Path.cwd() / "actions"
    actions = discover_actions(actions_dir)

    print(f"Loaded {len(actions)} actions: {', '.join(sorted(actions.keys()))}")
    print()

    # Create HA client if configured
    ha_client = None
    if config.home_assistant and config.home_assistant.url:
        ha_client = HAClient(
            url=config.home_assistant.url,
            token=config.home_assistant.token,
        )
        print(f"Home Assistant: {config.home_assistant.url}")
    else:
        print("Home Assistant: not configured")

    # Create device manager
    device_manager = DeviceManager(config.devices)
    devices = device_manager.discover()

    if not devices:
        print("\nNo MIDI devices found matching configuration.")
        print("Available ports:")
        for port in list_midi_ports():
            print(f"  - {port}")
        print("\nRun 'python -m midi_controller setup' to configure devices.")
        return 1

    # Create message broker
    broker = create_broker(actions, config.mappings, ha_client)

    print()
    print("-" * 60)
    print("Press Ctrl+C to stop")
    print("-" * 60)
    print()

    # Run the event loop
    try:
        asyncio.run(device_manager.run(broker.handle))
    except KeyboardInterrupt:
        print("\n" + "-" * 60)
        print("Stopped.")

    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    """Run the interactive setup wizard."""
    config_path = Path(args.config)
    return run_setup_wizard(config_path)


def cmd_list_devices(args: argparse.Namespace) -> int:
    """List available MIDI devices."""
    ports = list_midi_ports()

    if not ports:
        print("No MIDI input ports found.")
        return 0

    print("Available MIDI input ports:")
    print()
    for i, port in enumerate(ports, 1):
        print(f"  [{i}] {port}")
    print()

    return 0


def cmd_list_actions(args: argparse.Namespace) -> int:
    """List available actions."""
    load_builtin_actions()
    actions_dir = Path.cwd() / "actions"
    actions = discover_actions(actions_dir)

    print("Available actions:")
    print()

    # Group by source
    builtin = ["ha_toggle", "ha_brightness", "ha_color", "ha_color_temp", "shell"]
    custom = [name for name in actions if name not in builtin]

    print("Built-in:")
    for name in sorted(builtin):
        if name in actions:
            func = actions[name]
            doc = func.__doc__ or ""
            first_line = doc.strip().split("\n")[0] if doc else "No description"
            print(f"  {name}: {first_line}")

    if custom:
        print()
        print("Custom (from actions/):")
        for name in sorted(custom):
            func = actions[name]
            doc = func.__doc__ or ""
            first_line = doc.strip().split("\n")[0] if doc else "No description"
            print(f"  {name}: {first_line}")

    print()
    return 0


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="midi_controller",
        description="Device-agnostic MIDI controller with config-driven actions",
    )
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # run command (default)
    run_parser = subparsers.add_parser("run", help="Run the MIDI controller")
    run_parser.set_defaults(func=cmd_run)

    # setup command
    setup_parser = subparsers.add_parser("setup", help="Interactive device setup")
    setup_parser.set_defaults(func=cmd_setup)

    # list-devices command
    list_dev_parser = subparsers.add_parser("list-devices", help="List MIDI devices")
    list_dev_parser.set_defaults(func=cmd_list_devices)

    # list-actions command
    list_act_parser = subparsers.add_parser("list-actions", help="List available actions")
    list_act_parser.set_defaults(func=cmd_list_actions)

    args = parser.parse_args()

    # Default to 'run' if no command specified
    if args.command is None:
        args.func = cmd_run

    # Ensure unbuffered output
    sys.stdout.reconfigure(line_buffering=True)

    sys.exit(args.func(args))
