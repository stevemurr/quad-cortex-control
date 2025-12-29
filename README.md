# Quad Cortex MIDI Control

A Python application that listens to MIDI messages from a Neural DSP Quad Cortex and triggers Home Assistant actions. Control your smart home lighting directly from your pedalboard.

## Features

- **Auto-detection**: Automatically finds your Quad Cortex MIDI port
- **Preset cycling**: Consecutive presses of the same control cycle through presets
- **Type-safe MIDI parsing**: Clean dataclass-based message handling
- **Home Assistant integration**: Control lights via the HA REST API

## Requirements

- Python 3.10+
- Neural DSP Quad Cortex (or any MIDI controller)
- Home Assistant instance with API access

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/quad-cortex-control.git
cd quad-cortex-control

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Set these environment variables before running:

```bash
export HA_URL="http://your-home-assistant:8123"
export HA_TOKEN="your-long-lived-access-token"
```

To create a long-lived access token in Home Assistant:
1. Go to your Profile (click your name in the sidebar)
2. Scroll to "Long-Lived Access Tokens"
3. Click "Create Token"

## Usage

```bash
# Auto-detect Quad Cortex
python midi_listener.py

# Or specify a port by index
python midi_listener.py 0
```

The script will list available MIDI ports and start listening.

## Default Mappings

| CC # | Action |
|------|--------|
| 0 | Toggle lights on/off |
| 1 | Cycle color temperatures (6500K → 2200K) |
| 2 | Cycle warm colors (amber, red) |
| 3 | Cycle brightness (20% → 100%) |

All actions target `light.lights` by default. Edit `build_mappings()` in `midi_listener.py` to customize.

## Customization

### Adding new actions

Edit the `build_mappings()` function:

```python
def build_mappings(config: HAConfig) -> dict[int, Action]:
    return {
        0: simple(lambda: ha_toggle_light(config, "light.living_room")),
        1: cycle(NATURAL_LIGHT, lambda c: ha_set_color_temp(config, "light.living_room", c)),
        # Add more mappings...
    }
```

### Adding new presets

Define preset lists at the module level:

```python
MY_COLORS = [
    Color(name="blue", rgb=(0, 0, 255)),
    Color(name="green", rgb=(0, 255, 0)),
]
```

## How it works

1. The script connects to your Quad Cortex via MIDI
2. Control Change messages on channel 0 trigger mapped actions
3. Consecutive presses of the same CC cycle through presets
4. Pressing a different CC resets the cycle position

## License

MIT
