# Quad Cortex MIDI Control

A device-agnostic, config-driven MIDI control system that routes MIDI messages from input devices to configurable actions. Designed primarily for integrating MIDI controllers (like the Neural DSP Quad Cortex and nanoKEY2) with Home Assistant for smart home automation.

## Features

- **Multi-device support** - Listen to multiple MIDI devices simultaneously
- **Home Assistant integration** - Control lights, fans, and other devices via HA REST API
- **Preset cycling** - Cycle through brightness levels, colors, or color temperatures with repeated presses
- **Shell commands** - Trigger system commands from MIDI controls
- **Custom actions** - Extend with your own Python action plugins
- **Interactive setup wizard** - Learn MIDI controls and generate configuration automatically
- **macOS menubar app** - Run as a background service with system tray controls

## Installation

```bash
pip install -r requirements.txt
```

### Dependencies

- `mido[ports-rtmidi]` - MIDI input handling
- `requests` - HTTP client for Home Assistant
- `pyyaml` - Configuration parsing
- `rumps` - macOS menubar support (optional)

## Quick Start

1. Set your Home Assistant credentials:
   ```bash
   export HA_URL="http://your-ha-instance:8123"
   export HA_TOKEN="your-long-lived-access-token"
   ```

2. Run the interactive setup wizard:
   ```bash
   python -m midi_controller setup
   ```

3. Start the controller:
   ```bash
   python -m midi_controller run
   ```

## Usage

```bash
# Run MIDI controller
python -m midi_controller run

# Interactive setup wizard
python -m midi_controller setup

# List available MIDI devices
python -m midi_controller list-devices

# List available actions
python -m midi_controller list-actions

# Run as macOS menubar app
python -m midi_controller menubar

# Use custom config file
python -m midi_controller -c /path/to/config.yaml run
```

## Configuration

Configuration is stored in `config.yaml`. The file supports environment variable substitution using `${VAR}` syntax.

### Example Configuration

```yaml
home_assistant:
  url: ${HA_URL}
  token: ${HA_TOKEN}

devices:
  quad_cortex:
    port: "Quad Cortex"
  nanokey:
    port: "nanoKEY2"

presets:
  brightness_levels:
    - 25
    - 50
    - 75
    - 100
  color_temps:
    - 2700
    - 4000
    - 5500

mappings:
  quad_cortex:
    - match:
        type: control_change
        control: 1
      action: ha_toggle
      params:
        entity_id: light.living_room

    - match:
        type: control_change
        control: 2
      action: ha_brightness
      params:
        entity_id: light.living_room
        cycle: $brightness_levels

  nanokey:
    - match:
        type: note_on
        note: 60
      action: shell
      params:
        command: "osascript -e 'tell application \"Spotify\" to playpause'"
```

### Match Rules

| Field | Description |
|-------|-------------|
| `type` | Message type: `control_change`, `note_on`, `note_off`, `program_change`, `pitchwheel` |
| `channel` | MIDI channel (0-15), omit to match any |
| `control` | Control number for CC messages |
| `note` | Note number for note messages |
| `value_min`, `value_max` | Range filter for CC values |
| `velocity_min`, `velocity_max` | Range filter for note velocity |

## Built-in Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `ha_toggle` | Toggle a Home Assistant light | `entity_id` |
| `ha_brightness` | Set light brightness | `entity_id`, `brightness` or `cycle` |
| `ha_color` | Set RGB color | `entity_id`, `color` or `cycle` |
| `ha_color_temp` | Set color temperature | `entity_id`, `color_temp` or `cycle` |
| `ha_fan_speed` | Set fan speed percentage | `entity_id`, `speed` |
| `shell` | Execute shell command | `command` |

## Custom Actions

Create custom actions in the `actions/` directory:

```python
# actions/my_action.py
from midi_controller.actions.base import action, ActionContext

@action("my_custom_action")
def my_action(ctx: ActionContext, message: str = "Hello"):
    print(f"MIDI from {ctx.device}: {ctx.message}")
    print(message)
```

Actions are auto-discovered at startup. The `ActionContext` provides:
- `message` - The MIDI message that triggered the action
- `device` - Name of the source device
- `ha_client` - Home Assistant API client
- `cycle_state` - Preset cycling state manager

## Project Structure

```
quad_cortex_control/
├── main.py                 # Entry point
├── config.yaml             # Configuration
├── requirements.txt        # Dependencies
├── actions/                # Custom action plugins
└── midi_controller/        # Main package
    ├── cli.py              # Command-line interface
    ├── config.py           # Config loading
    ├── devices.py          # MIDI device management
    ├── messages.py         # MIDI message types
    ├── broker.py           # Message routing
    ├── cycle.py            # Preset cycling
    ├── discovery.py        # Plugin discovery
    ├── setup_wizard.py     # Interactive setup
    ├── menubar.py          # macOS menubar app
    ├── actions/            # Built-in actions
    └── ha/                 # Home Assistant client
```

## License

MIT
