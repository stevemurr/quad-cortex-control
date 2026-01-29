"""
MIDI device management with asyncio.

Handles discovery, connection, and message streaming from multiple MIDI devices.
"""

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Callable

import mido

from .config import DeviceConfig
from .messages import MidiMessage, parse_midi_message


@dataclass
class MidiDevice:
    """Represents a connected MIDI device."""
    name: str  # Friendly name from config
    port_name: str  # Actual MIDI port name
    port: mido.ports.BaseInput | None = None

    def __str__(self) -> str:
        return f"{self.name} ({self.port_name})"


def list_midi_ports() -> list[str]:
    """List all available MIDI input ports."""
    return mido.get_input_names()


def find_matching_ports(device_configs: list[DeviceConfig]) -> list[MidiDevice]:
    """
    Find MIDI ports matching the device configurations.

    Args:
        device_configs: List of device configurations to match.

    Returns:
        List of MidiDevice objects for matched ports.
    """
    available_ports = list_midi_ports()
    matched_devices: list[MidiDevice] = []

    for config in device_configs:
        if not config.enabled:
            continue

        for port_name in available_ports:
            # Wildcard matches any device
            if config.match == "*":
                matched_devices.append(MidiDevice(name=config.name, port_name=port_name))
            # Substring match
            elif config.match in port_name:
                matched_devices.append(MidiDevice(name=config.name, port_name=port_name))

    return matched_devices


async def read_messages_async(
    device: MidiDevice,
    callback: Callable[[str, MidiMessage], None],
) -> None:
    """
    Read MIDI messages from a device asynchronously.

    Uses asyncio.to_thread() to wrap mido's blocking reads.

    Args:
        device: The MIDI device to read from.
        callback: Function to call with (device_name, message) for each message.
    """
    def blocking_read():
        """Blocking read that runs in a thread."""
        with mido.open_input(device.port_name) as port:
            device.port = port
            for raw_msg in port:
                msg = parse_midi_message(raw_msg)
                callback(device.name, msg)

    try:
        await asyncio.to_thread(blocking_read)
    except Exception as e:
        print(f"Device {device} disconnected: {e}")


async def stream_messages(
    device: MidiDevice,
) -> AsyncIterator[tuple[str, MidiMessage]]:
    """
    Stream MIDI messages from a device as an async iterator.

    Args:
        device: The MIDI device to read from.

    Yields:
        Tuples of (device_name, message).
    """
    queue: asyncio.Queue[MidiMessage] = asyncio.Queue()

    def on_message(raw_msg):
        msg = parse_midi_message(raw_msg)
        queue.put_nowait(msg)

    def blocking_read():
        with mido.open_input(device.port_name) as port:
            for raw_msg in port:
                on_message(raw_msg)

    # Start the blocking read in a thread
    read_task = asyncio.create_task(asyncio.to_thread(blocking_read))

    try:
        while True:
            msg = await queue.get()
            yield (device.name, msg)
    except asyncio.CancelledError:
        read_task.cancel()
        raise


class DeviceManager:
    """
    Manages multiple MIDI devices with asyncio.

    Handles device discovery, connection, and message routing.
    """

    def __init__(self, device_configs: list[DeviceConfig]):
        self.device_configs = device_configs
        self.devices: list[MidiDevice] = []
        self._tasks: list[asyncio.Task] = []
        self._running = False

    def discover(self) -> list[MidiDevice]:
        """Discover and return matching devices."""
        self.devices = find_matching_ports(self.device_configs)
        return self.devices

    async def run(self, on_message: Callable[[str, MidiMessage], None]) -> None:
        """
        Start listening to all discovered devices.

        Args:
            on_message: Callback for each message (device_name, message).
        """
        if not self.devices:
            self.discover()

        if not self.devices:
            print("No MIDI devices found matching configuration.")
            return

        self._running = True

        # Create a task for each device
        for device in self.devices:
            task = asyncio.create_task(
                read_messages_async(device, on_message),
                name=f"midi-{device.name}",
            )
            self._tasks.append(task)
            print(f"Listening on: {device}")

        # Wait for all tasks (they run until cancelled or device disconnects)
        try:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False

    async def stop(self) -> None:
        """Stop all device listeners."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
