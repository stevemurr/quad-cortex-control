"""
macOS menubar application for the MIDI controller.

Runs the MIDI listener as a background service with a system tray icon.
"""

import asyncio
import queue
import threading
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any

import rumps

from .broker import create_broker
from .config import load_config
from .devices import DeviceManager, list_midi_ports
from .discovery import discover_actions, load_builtin_actions
from .ha.client import HAClient


class EventType(Enum):
    """Types of events sent from the async thread to the UI."""
    STATUS_CHANGE = auto()
    DEVICE_CONNECTED = auto()
    DEVICE_DISCONNECTED = auto()
    MIDI_MESSAGE = auto()
    ERROR = auto()


@dataclass
class UIEvent:
    """Event for updating the UI from the async thread."""
    type: EventType
    data: Any = None


class MidiControllerApp(rumps.App):
    """Menubar application for the MIDI controller."""

    def __init__(self, config_path: Path):
        super().__init__("MIDI", quit_button=None)
        self.config_path = config_path

        # Thread-safe communication
        self._event_queue: queue.Queue[UIEvent] = queue.Queue()

        # Async loop and thread
        self._loop: asyncio.AbstractEventLoop | None = None
        self._async_thread: threading.Thread | None = None
        self._stop_event: asyncio.Event | None = None

        # State
        self._running = False
        self._devices: list[str] = []

        # Build initial menu
        self._build_menu()

        # Start polling for UI updates
        self._timer = rumps.Timer(self._poll_events, 0.1)
        self._timer.start()

    def _build_menu(self) -> None:
        """Build the menu structure."""
        # Create Devices submenu with initial placeholder
        self._devices_menu = rumps.MenuItem("Devices")
        self._devices_menu.add(rumps.MenuItem("No devices connected"))

        self.menu = [
            rumps.MenuItem("Status: Stopped", callback=None),
            None,  # Separator
            self._devices_menu,
            None,  # Separator
            rumps.MenuItem("Start", callback=self.on_start),
            rumps.MenuItem("Stop", callback=self.on_stop),
            None,  # Separator
            rumps.MenuItem("Quit", callback=self.on_quit),
        ]
        # Disable stop initially
        self.menu["Stop"].set_callback(None)

    def _update_status(self, status: str) -> None:
        """Update the status menu item."""
        self.menu["Status: Stopped"].title = f"Status: {status}"

    def _update_devices_menu(self) -> None:
        """Update the devices submenu."""
        # Clear existing items
        self._devices_menu.clear()

        if not self._devices:
            self._devices_menu.add(rumps.MenuItem("No devices connected"))
        else:
            for device in self._devices:
                self._devices_menu.add(rumps.MenuItem(device))

    def _poll_events(self, _: rumps.Timer) -> None:
        """Poll for events from the async thread."""
        try:
            while True:
                event = self._event_queue.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass

    def _handle_event(self, event: UIEvent) -> None:
        """Handle an event from the async thread."""
        if event.type == EventType.STATUS_CHANGE:
            self._update_status(event.data)
        elif event.type == EventType.DEVICE_CONNECTED:
            if event.data not in self._devices:
                self._devices.append(event.data)
                self._update_devices_menu()
        elif event.type == EventType.DEVICE_DISCONNECTED:
            if event.data in self._devices:
                self._devices.remove(event.data)
                self._update_devices_menu()
        elif event.type == EventType.ERROR:
            rumps.notification(
                title="MIDI Controller Error",
                subtitle="",
                message=str(event.data),
            )

    def _run_asyncio_loop(self) -> None:
        """Run the asyncio event loop in a background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._stop_event = asyncio.Event()

        try:
            self._loop.run_until_complete(self._async_main())
        except Exception as e:
            self._event_queue.put(UIEvent(EventType.ERROR, str(e)))
        finally:
            self._loop.close()
            self._loop = None

    async def _async_main(self) -> None:
        """Main async entry point."""
        self._event_queue.put(UIEvent(EventType.STATUS_CHANGE, "Starting..."))

        # Load config
        try:
            config = load_config(self.config_path)
        except Exception as e:
            self._event_queue.put(UIEvent(EventType.ERROR, f"Config error: {e}"))
            self._event_queue.put(UIEvent(EventType.STATUS_CHANGE, "Error"))
            return

        # Load actions
        load_builtin_actions()
        actions_dir = Path.cwd() / "actions"
        actions = discover_actions(actions_dir)

        # Create HA client if configured
        ha_client = None
        if config.home_assistant and config.home_assistant.url:
            ha_client = HAClient(
                url=config.home_assistant.url,
                token=config.home_assistant.token,
            )

        # Create device manager
        device_manager = DeviceManager(config.devices)
        devices = device_manager.discover()

        if not devices:
            ports = list_midi_ports()
            msg = "No MIDI devices found matching config"
            if ports:
                msg += f". Available: {', '.join(ports)}"
            self._event_queue.put(UIEvent(EventType.ERROR, msg))
            self._event_queue.put(UIEvent(EventType.STATUS_CHANGE, "No Devices"))
            return

        # Update UI with connected devices
        for device in devices:
            self._event_queue.put(UIEvent(EventType.DEVICE_CONNECTED, str(device)))

        # Create message broker
        broker = create_broker(actions, config.mappings, ha_client)

        self._event_queue.put(UIEvent(EventType.STATUS_CHANGE, "Running"))

        # Run until stop is requested
        run_task = asyncio.create_task(device_manager.run(broker.handle))

        # Wait for stop signal
        await self._stop_event.wait()

        # Stop the device manager
        await device_manager.stop()
        run_task.cancel()
        try:
            await run_task
        except asyncio.CancelledError:
            pass

        self._event_queue.put(UIEvent(EventType.STATUS_CHANGE, "Stopped"))

    @rumps.clicked("Start")
    def on_start(self, _: rumps.MenuItem) -> None:
        """Handle Start button click."""
        if self._running:
            return

        self._running = True

        # Update menu state
        self.menu["Start"].set_callback(None)
        self.menu["Stop"].set_callback(self.on_stop)

        # Clear devices
        self._devices.clear()
        self._update_devices_menu()

        # Start the async thread
        self._async_thread = threading.Thread(
            target=self._run_asyncio_loop,
            daemon=True,
            name="midi-async",
        )
        self._async_thread.start()

    @rumps.clicked("Stop")
    def on_stop(self, _: rumps.MenuItem) -> None:
        """Handle Stop button click."""
        if not self._running:
            return

        self._running = False

        # Signal the async loop to stop
        if self._loop and self._stop_event:
            self._loop.call_soon_threadsafe(self._stop_event.set)

        # Wait for thread to finish (with timeout)
        if self._async_thread and self._async_thread.is_alive():
            self._async_thread.join(timeout=2.0)

        self._async_thread = None

        # Update menu state
        self.menu["Start"].set_callback(self.on_start)
        self.menu["Stop"].set_callback(None)

        # Clear devices
        self._devices.clear()
        self._update_devices_menu()
        self._update_status("Stopped")

    @rumps.clicked("Quit")
    def on_quit(self, _: rumps.MenuItem) -> None:
        """Handle Quit button click."""
        # Stop if running
        if self._running:
            self.on_stop(None)

        # Stop the timer
        self._timer.stop()

        # Quit the app
        rumps.quit_application()


def run_menubar_app(config_path: Path) -> None:
    """Run the menubar application."""
    app = MidiControllerApp(config_path)
    app.run()
