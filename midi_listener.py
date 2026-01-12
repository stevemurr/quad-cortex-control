#!/usr/bin/env python3
"""
MIDI Listener for Quad Cortex

Listens for MIDI messages from the Neural DSP Quad Cortex
and triggers actions based on configured handlers.
"""

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable, Generic, Sequence, TypeVar

import mido
import requests

# Ensure output is not buffered
sys.stdout.reconfigure(line_buffering=True)


@dataclass(frozen=True)
class MidiMessage:
    """Base class for MIDI messages."""
    channel: int


@dataclass(frozen=True)
class ControlChange(MidiMessage):
    """Control Change MIDI message."""
    control: int
    value: int

    def __str__(self) -> str:
        return f"Control Change | channel={self.channel} control={self.control} value={self.value}"


@dataclass(frozen=True)
class NoteOn(MidiMessage):
    """Note On MIDI message."""
    note: int
    velocity: int

    def __str__(self) -> str:
        return f"Note On        | channel={self.channel} note={self.note} velocity={self.velocity}"


@dataclass(frozen=True)
class NoteOff(MidiMessage):
    """Note Off MIDI message."""
    note: int
    velocity: int

    def __str__(self) -> str:
        return f"Note Off       | channel={self.channel} note={self.note} velocity={self.velocity}"


@dataclass(frozen=True)
class ProgramChange(MidiMessage):
    """Program Change MIDI message."""
    program: int

    def __str__(self) -> str:
        return f"Program Change | channel={self.channel} program={self.program}"


@dataclass(frozen=True)
class PitchWheel(MidiMessage):
    """Pitch Wheel MIDI message."""
    pitch: int

    def __str__(self) -> str:
        return f"Pitch Wheel    | channel={self.channel} pitch={self.pitch}"


@dataclass(frozen=True)
class UnknownMessage:
    """Unknown MIDI message type."""
    raw: object

    def __str__(self) -> str:
        return f"{'Unknown':14} | {self.raw}"


def parse_midi_message(msg) -> MidiMessage | UnknownMessage:
    """Parse a mido message into a typed MidiMessage."""
    if msg.type == "control_change":
        return ControlChange(channel=msg.channel, control=msg.control, value=msg.value)
    elif msg.type == "note_on":
        return NoteOn(channel=msg.channel, note=msg.note, velocity=msg.velocity)
    elif msg.type == "note_off":
        return NoteOff(channel=msg.channel, note=msg.note, velocity=msg.velocity)
    elif msg.type == "program_change":
        return ProgramChange(channel=msg.channel, program=msg.program)
    elif msg.type == "pitchwheel":
        return PitchWheel(channel=msg.channel, pitch=msg.pitch)
    else:
        return UnknownMessage(raw=msg)


@dataclass(frozen=True)
class HAConfig:
    url: str
    token: str


@dataclass(frozen=True)
class Color:
    name: str
    rgb: tuple[int, int, int] | None = None
    kelvin: int | None = None


@dataclass(frozen=True)
class Brightness:
    percent: int
    label: str | None = None


# Home Assistant Configuration
HA_CONFIG = HAConfig(
    url=os.environ.get("HA_URL", ""),
    token=os.environ.get("HA_TOKEN", ""),
)

# External tools
NOWPLAYING_CLI = shutil.which("nowplaying-cli")

# Cycle presets
NATURAL_LIGHT = [
    Color(name="cool daylight", kelvin=6500),
    Color(name="daylight", kelvin=5500),
    Color(name="neutral", kelvin=4000),
    Color(name="warm white", kelvin=3000),
    Color(name="candlelight", kelvin=2200),
]
WARM_COLORS = [
    Color(name="deep amber", rgb=(255, 100, 0)),
    Color(name="red", rgb=(255, 0, 0)),
]
BRIGHTNESS_PRESETS = [
    Brightness(percent=20, label="dim"),
    Brightness(percent=40),
    Brightness(percent=60),
    Brightness(percent=80),
    Brightness(percent=100, label="full"),
]


@dataclass
class CycleState:
    """Encapsulates the cycling state for control changes."""
    indices: dict[int, int] = field(default_factory=dict)
    last_control: int | None = None

    def advance(self, control: int, preset_count: int) -> int:
        """Advance the cycle index for a control if it was pressed consecutively.

        Returns the current index to use for the preset.
        """
        if control not in self.indices:
            self.indices[control] = 0
        if self.last_control == control:
            self.indices[control] = (self.indices[control] + 1) % preset_count
        self.last_control = control
        return self.indices[control]


# Action Types
T = TypeVar("T")


@dataclass(frozen=True)
class SimpleAction:
    """Action that executes once (no cycling)."""
    execute: Callable[[], None]

    def __call__(self, state: CycleState, cc: int) -> None:
        self.execute()
        state.last_control = cc


@dataclass(frozen=True)
class CycleAction(Generic[T]):
    """Action that cycles through presets."""
    presets: tuple[T, ...]
    execute: Callable[[T], None]

    def __call__(self, state: CycleState, cc: int) -> None:
        idx = state.advance(cc, len(self.presets))
        self.execute(self.presets[idx])


Action = SimpleAction | CycleAction


def simple(execute: Callable[[], None]) -> SimpleAction:
    """Create a simple action that executes once."""
    return SimpleAction(execute)


def cycle(presets: Sequence[T], execute: Callable[[T], None]) -> CycleAction[T]:
    """Create an action that cycles through presets."""
    return CycleAction(tuple(presets), execute)


def ha_request(config: HAConfig, service: str, data: dict, description: str):
    """Make a Home Assistant service call."""
    url = f"{config.url}/api/services/{service}"
    headers = {
        "Authorization": f"Bearer {config.token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=5)
        if response.ok:
            print(f"  -> {description}")
        else:
            print(f"  -> Error: {response.status_code} {response.text}")
    except requests.RequestException as e:
        print(f"  -> Request failed: {e}")


def ha_toggle_light(config: HAConfig, entity_id: str):
    """Toggle a Home Assistant light."""
    ha_request(config, "light/toggle", {"entity_id": entity_id}, f"Toggled {entity_id}")


def ha_set_light_color(config: HAConfig, entity_id: str, color: Color):
    """Set a Home Assistant light to a specific color."""
    data = {"entity_id": entity_id, "rgb_color": color.rgb}
    ha_request(config, "light/turn_on", data, f"Set {entity_id} to {color.name}")


def ha_set_brightness(config: HAConfig, entity_id: str, brightness: Brightness):
    """Set a Home Assistant light brightness."""
    data = {"entity_id": entity_id, "brightness_pct": brightness.percent}
    ha_request(config, "light/turn_on", data, f"Set {entity_id} to {brightness.percent}% brightness")


def ha_set_color_temp(config: HAConfig, entity_id: str, color: Color):
    """Set a Home Assistant light color temperature."""
    data = {"entity_id": entity_id, "color_temp_kelvin": color.kelvin}
    ha_request(config, "light/turn_on", data, f"Set {entity_id} to {color.name} ({color.kelvin}K)")


def run_shell_command(command: str) -> None:
    """Execute a shell command."""
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  -> Executed: {command}")
    else:
        print(f"  -> Command failed: {command}")
        if result.stderr:
            print(f"     stderr: {result.stderr.strip()}")


def build_mappings(config: HAConfig) -> dict[tuple[int, int], Action]:
    """Build CC mappings with Home Assistant backend. Keys are (channel, cc)."""
    mappings: dict[tuple[int, int], Action] = {
        (0, 0): simple(lambda: ha_toggle_light(config, "light.lights")),
        (0, 1): cycle(NATURAL_LIGHT, lambda c: ha_set_color_temp(config, "light.lights", c)),
        (0, 2): cycle(WARM_COLORS, lambda c: ha_set_light_color(config, "light.lights", c)),
        (0, 3): cycle(BRIGHTNESS_PRESETS, lambda b: ha_set_brightness(config, "light.lights", b)),
    }
    if NOWPLAYING_CLI:
        mappings[(0, 9)] = simple(lambda: run_shell_command(f"{NOWPLAYING_CLI} togglePlayPause"))
    return mappings


def list_midi_ports():
    """List all available MIDI input ports."""
    ports = mido.get_input_names()
    if not ports:
        print("No MIDI input ports found!")
        return []

    print("Available MIDI input ports:")
    for i, port in enumerate(ports):
        print(f"  [{i}] {port}")
    print()
    return ports


def find_quad_cortex_port(ports):
    """Find the Quad Cortex MIDI port."""
    for port in ports:
        if "Quad Cortex" in port:
            return port
    return None


def handle_message(msg: MidiMessage | UnknownMessage, state: CycleState, mappings: dict[tuple[int, int], Action]) -> None:
    """Check message against handlers and trigger actions."""
    if not isinstance(msg, ControlChange):
        return

    if action := mappings.get((msg.channel, msg.control)):
        action(state, msg.control)


def listen(port_name: str, mappings: dict[tuple[int, int], Action]) -> None:
    """Listen for MIDI messages on the specified port."""
    print(f"Listening on: {port_name}")
    print("Press Ctrl+C to stop\n")
    print("-" * 60)

    state = CycleState()

    try:
        with mido.open_input(port_name) as inport:
            for raw_msg in inport:
                msg = parse_midi_message(raw_msg)
                print(msg)
                handle_message(msg, state, mappings)
    except KeyboardInterrupt:
        print("\n" + "-" * 60)
        print("Stopped.")


def main():
    ports = list_midi_ports()
    if not ports:
        sys.exit(1)

    # Build mappings with Home Assistant backend
    mappings = build_mappings(HA_CONFIG)

    # Try to find Quad Cortex automatically
    qc_port = find_quad_cortex_port(ports)

    if qc_port:
        print(f"Found Quad Cortex: {qc_port}\n")
        listen(qc_port, mappings)
    else:
        print("Quad Cortex not found. Available ports listed above.")
        print("You can specify a port index as an argument: python midi_listener.py 0")

        if len(sys.argv) > 1:
            try:
                idx = int(sys.argv[1])
                listen(ports[idx], mappings)
            except (ValueError, IndexError):
                print(f"Invalid port index: {sys.argv[1]}")
                sys.exit(1)


if __name__ == "__main__":
    main()
