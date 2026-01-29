"""
MIDI message types.

Provides typed dataclasses for all supported MIDI message types.
"""

from dataclasses import dataclass


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
        return f"CC ch={self.channel} cc={self.control} val={self.value}"


@dataclass(frozen=True)
class NoteOn(MidiMessage):
    """Note On MIDI message."""
    note: int
    velocity: int

    def __str__(self) -> str:
        return f"NoteOn ch={self.channel} note={self.note} vel={self.velocity}"


@dataclass(frozen=True)
class NoteOff(MidiMessage):
    """Note Off MIDI message."""
    note: int
    velocity: int

    def __str__(self) -> str:
        return f"NoteOff ch={self.channel} note={self.note} vel={self.velocity}"


@dataclass(frozen=True)
class ProgramChange(MidiMessage):
    """Program Change MIDI message."""
    program: int

    def __str__(self) -> str:
        return f"PC ch={self.channel} prog={self.program}"


@dataclass(frozen=True)
class PitchWheel(MidiMessage):
    """Pitch Wheel MIDI message."""
    pitch: int

    def __str__(self) -> str:
        return f"PitchWheel ch={self.channel} pitch={self.pitch}"


@dataclass(frozen=True)
class UnknownMessage:
    """Unknown MIDI message type."""
    raw: object

    def __str__(self) -> str:
        return f"Unknown: {self.raw}"


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
