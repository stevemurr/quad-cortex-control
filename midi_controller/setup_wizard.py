"""
Interactive setup wizard for configuring MIDI devices.

Features:
- Device detection
- Learning mode to capture MIDI events
- Smart action suggestions based on event patterns
- Config generation
"""

import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import mido
import yaml

from .devices import list_midi_ports
from .messages import (
    ControlChange,
    MidiMessage,
    NoteOn,
    NoteOff,
    ProgramChange,
    PitchWheel,
    parse_midi_message,
)


@dataclass
class CapturedControl:
    """A captured MIDI control with metadata."""
    msg_type: str
    channel: int
    identifier: int  # control number, note, or program
    count: int = 1
    min_value: int = 127
    max_value: int = 0
    values: list[int] = field(default_factory=list)

    @property
    def key(self) -> tuple:
        return (self.msg_type, self.channel, self.identifier)

    @property
    def value_range(self) -> int:
        return self.max_value - self.min_value

    def update(self, value: int) -> None:
        self.count += 1
        self.min_value = min(self.min_value, value)
        self.max_value = max(self.max_value, value)
        self.values.append(value)


def detect_control_type(control: CapturedControl) -> tuple[str, str, str]:
    """
    Detect the type of control and suggest an action.

    Returns:
        Tuple of (control_type_name, suggested_action, description)
    """
    if control.msg_type == "control_change":
        if control.value_range > 50:
            return ("Fader/Knob", "ha_brightness", "Continuous control - good for brightness or volume")
        else:
            return ("Button (CC)", "ha_toggle", "Binary control - good for toggle")

    elif control.msg_type == "note_on":
        if control.count > 2:
            return ("Multi-press Button", "ha_color_temp", "Multiple presses - good for cycling through presets")
        else:
            return ("Button", "ha_toggle", "Single press - good for toggle")

    elif control.msg_type == "program_change":
        return ("Preset Selector", "shell", "Program change - good for switching scenes")

    elif control.msg_type == "pitchwheel":
        return ("Pitch Wheel", "ha_brightness", "Continuous pitch - could control brightness")

    return ("Unknown", "print_message", "Unknown control type")


def capture_events(port_name: str, duration: float = 30.0) -> list[CapturedControl]:
    """
    Capture MIDI events from a port.

    Args:
        port_name: Name of the MIDI port to listen on.
        duration: Maximum capture time in seconds (or until Ctrl+C).

    Returns:
        List of captured controls.
    """
    controls: dict[tuple, CapturedControl] = {}
    print(f"\nCapturing from: {port_name}")
    print(f"Press buttons, turn knobs, move faders...")
    print(f"Press Ctrl+C when done (or wait {duration:.0f}s)")
    print()

    start_time = time.time()

    try:
        with mido.open_input(port_name) as port:
            while time.time() - start_time < duration:
                # Non-blocking read with timeout
                msg = port.receive(block=True)
                if msg is None:
                    continue

                parsed = parse_midi_message(msg)
                control = _process_message(parsed, controls)
                if control:
                    elapsed = time.time() - start_time
                    print(f"  [{elapsed:5.1f}s] {parsed}")

    except KeyboardInterrupt:
        print("\n\nCapture stopped.")

    return list(controls.values())


def _process_message(
    msg: MidiMessage,
    controls: dict[tuple, CapturedControl],
) -> CapturedControl | None:
    """Process a MIDI message and update the controls dict."""
    if isinstance(msg, ControlChange):
        key = ("control_change", msg.channel, msg.control)
        value = msg.value
    elif isinstance(msg, NoteOn):
        if msg.velocity == 0:
            return None  # Note off disguised as note on
        key = ("note_on", msg.channel, msg.note)
        value = msg.velocity
    elif isinstance(msg, NoteOff):
        return None  # Ignore note off
    elif isinstance(msg, ProgramChange):
        key = ("program_change", msg.channel, msg.program)
        value = msg.program
    elif isinstance(msg, PitchWheel):
        key = ("pitchwheel", msg.channel, 0)  # Use 0 as identifier for pitch wheel
        value = msg.pitch
    else:
        return None

    if key in controls:
        controls[key].update(value)
    else:
        controls[key] = CapturedControl(
            msg_type=key[0],
            channel=key[1],
            identifier=key[2],
            min_value=value,
            max_value=value,
            values=[value],
        )

    return controls[key]


def generate_config_block(
    device_name: str,
    port_name: str,
    controls: list[CapturedControl],
    accepted_suggestions: dict[tuple, str],
) -> dict[str, Any]:
    """
    Generate a config block for a device.

    Args:
        device_name: Friendly name for the device.
        port_name: MIDI port name pattern to match.
        controls: List of captured controls.
        accepted_suggestions: Dict mapping control key to accepted action.

    Returns:
        Config dictionary for this device.
    """
    mappings = []

    for control in controls:
        action = accepted_suggestions.get(control.key)
        if not action:
            continue

        # Build match rule
        match_rule: dict[str, Any] = {"type": control.msg_type}

        if control.channel != 0:  # Only specify channel if non-zero
            match_rule["channel"] = control.channel

        if control.msg_type == "control_change":
            match_rule["control"] = control.identifier
        elif control.msg_type in ("note_on", "note_off"):
            match_rule["note"] = control.identifier
        elif control.msg_type == "program_change":
            match_rule["program"] = control.identifier

        # Build mapping entry
        mapping: dict[str, Any] = {
            "match": match_rule,
            "action": action,
            "params": {},
        }

        # Add default params based on action
        if action == "ha_toggle":
            mapping["params"]["entity_id"] = "light.your_light"
        elif action == "ha_brightness":
            mapping["params"]["entity_id"] = "light.your_light"
            mapping["params"]["presets"] = "$brightness"
            mapping["cycle"] = True
        elif action == "ha_color":
            mapping["params"]["entity_id"] = "light.your_light"
            mapping["params"]["presets"] = "$colors"
            mapping["cycle"] = True
        elif action == "ha_color_temp":
            mapping["params"]["entity_id"] = "light.your_light"
            mapping["params"]["presets"] = "$natural_light"
            mapping["cycle"] = True
        elif action == "shell":
            mapping["params"]["command"] = "echo 'Hello from MIDI'"
        elif action == "print_message":
            mapping["params"]["message"] = f"Control {control.identifier} triggered"

        mappings.append(mapping)

    return {
        "device": {
            "name": device_name,
            "match": _get_port_pattern(port_name),
        },
        "mappings": mappings,
    }


def _get_port_pattern(port_name: str) -> str:
    """Extract a reasonable pattern from a port name."""
    # Common patterns: "Device Name:Port 0" or "Device Name"
    if ":" in port_name:
        return port_name.split(":")[0].strip()
    return port_name


def write_config(
    config_path: Path,
    device_name: str,
    port_name: str,
    controls: list[CapturedControl],
    accepted: dict[tuple, str],
) -> None:
    """
    Write or update the config file with the new device.
    """
    config_block = generate_config_block(device_name, port_name, controls, accepted)

    # Load existing config or create new
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {
            "home_assistant": {
                "url": "${HA_URL}",
                "token": "${HA_TOKEN}",
            },
            "devices": [],
            "presets": {
                "natural_light": [
                    {"name": "cool daylight", "kelvin": 6500},
                    {"name": "daylight", "kelvin": 5500},
                    {"name": "neutral", "kelvin": 4000},
                    {"name": "warm white", "kelvin": 3000},
                    {"name": "candlelight", "kelvin": 2200},
                ],
                "brightness": [
                    {"percent": 20, "label": "dim"},
                    {"percent": 40},
                    {"percent": 60},
                    {"percent": 80},
                    {"percent": 100, "label": "full"},
                ],
                "colors": [
                    {"name": "red", "rgb": [255, 0, 0]},
                    {"name": "green", "rgb": [0, 255, 0]},
                    {"name": "blue", "rgb": [0, 0, 255]},
                ],
            },
            "mappings": {},
        }

    # Add/update device
    if "devices" not in config:
        config["devices"] = []

    # Check if device already exists
    existing_idx = None
    for i, dev in enumerate(config["devices"]):
        if dev.get("name") == device_name:
            existing_idx = i
            break

    if existing_idx is not None:
        config["devices"][existing_idx] = config_block["device"]
    else:
        config["devices"].append(config_block["device"])

    # Add/update mappings
    if "mappings" not in config:
        config["mappings"] = {}

    config["mappings"][device_name] = config_block["mappings"]

    # Write config
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"\nConfig written to: {config_path}")


def run_setup_wizard(config_path: Path) -> int:
    """
    Run the interactive setup wizard.

    Returns:
        Exit code (0 for success).
    """
    print("=" * 60)
    print("MIDI Controller Setup Wizard")
    print("=" * 60)
    print()

    # List available devices
    ports = list_midi_ports()
    if not ports:
        print("No MIDI input ports found!")
        print("Connect a MIDI device and try again.")
        return 1

    print("Available MIDI devices:")
    print()
    for i, port in enumerate(ports, 1):
        print(f"  [{i}] {port}")
    print()

    # Select device
    while True:
        try:
            choice = input("Select device to configure (number): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(ports):
                selected_port = ports[idx]
                break
            print("Invalid selection. Try again.")
        except ValueError:
            print("Please enter a number.")
        except (KeyboardInterrupt, EOFError):
            print("\nSetup cancelled.")
            return 1

    print(f"\nSelected: {selected_port}")
    print()

    # Get device name
    default_name = _get_port_pattern(selected_port).lower().replace(" ", "_")
    try:
        name_input = input(f"Enter a name for this device [{default_name}]: ").strip()
        device_name = name_input if name_input else default_name
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.")
        return 1

    # Learning mode
    print()
    try:
        learn = input("Enter learning mode to capture controls? [Y/n]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.")
        return 1

    controls: list[CapturedControl] = []
    if learn != "n":
        controls = capture_events(selected_port)

    if not controls:
        print("\nNo controls captured. Creating minimal config...")
        write_config(config_path, device_name, selected_port, [], {})
        return 0

    # Show captured controls with suggestions
    print()
    print(f"Captured {len(controls)} control(s):")
    print()

    accepted: dict[tuple, str] = {}

    for i, control in enumerate(controls, 1):
        control_type, suggested_action, description = detect_control_type(control)

        # Format control info
        if control.msg_type == "control_change":
            ctrl_info = f"CC {control.identifier}"
            if control.value_range > 0:
                ctrl_info += f" (range: {control.min_value}-{control.max_value})"
        elif control.msg_type == "note_on":
            ctrl_info = f"Note {control.identifier} (pressed {control.count}x)"
        elif control.msg_type == "program_change":
            programs = sorted(set(control.values))
            ctrl_info = f"Program (values: {programs})"
        elif control.msg_type == "pitchwheel":
            ctrl_info = f"Pitch (range: {control.min_value}-{control.max_value})"
        else:
            ctrl_info = str(control.identifier)

        print(f"  [{i}] {control.msg_type} ch={control.channel} {ctrl_info}")
        print(f"      -> Detected: {control_type}")
        print(f"      -> Suggested: {suggested_action} ({description})")
        print()

        # For now, accept all suggestions
        accepted[control.key] = suggested_action

    # Ask for confirmation
    try:
        confirm = input("Accept suggestions and create config? [Y/n]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.")
        return 1

    if confirm == "n":
        print("Setup cancelled.")
        return 0

    # Write config
    write_config(config_path, device_name, selected_port, controls, accepted)

    print()
    print("Next steps:")
    print(f"  1. Edit {config_path} to customize entity IDs and actions")
    print("  2. Set HA_URL and HA_TOKEN environment variables")
    print("  3. Run: python -m midi_controller run")
    print()

    return 0
