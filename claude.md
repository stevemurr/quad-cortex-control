# Claude Code Context

## Project Overview

This is a config-driven MIDI control system that routes MIDI messages to actions, primarily for Home Assistant integration. It listens to MIDI devices (like the Quad Cortex guitar processor) and triggers smart home controls or shell commands.

## Architecture

### Core Flow

1. `cli.py` parses commands and loads config
2. `devices.py` discovers and connects to MIDI ports
3. `broker.py` receives messages and matches them against config mappings
4. Actions are dispatched with an `ActionContext` containing the message, device, HA client, and cycle state

### Key Patterns

- **Async I/O**: Uses `asyncio` for concurrent device listening
- **Dataclasses**: Frozen dataclasses for MIDI messages (`messages.py`)
- **Decorator-based actions**: `@action("name")` registers handlers
- **Plugin discovery**: Auto-loads actions from `actions/` directory at startup
- **Environment variable substitution**: Config supports `${VAR}` syntax

### Important Files

| File | Purpose |
|------|---------|
| `midi_triggers/broker.py` | Central message routing and action dispatch |
| `midi_triggers/config.py` | YAML config loading with env var substitution |
| `midi_triggers/actions/base.py` | Action decorator and ActionContext dataclass |
| `midi_triggers/ha/client.py` | Home Assistant REST API client |
| `midi_triggers/cycle.py` | Preset cycling state management |

## Code Style

- Python 3.10+ with type hints
- Dataclasses for data structures
- f-strings for formatting
- Single-file modules, avoid deep nesting
- No test suite currently

## Common Tasks

### Adding a new built-in action

1. Add function in `midi_triggers/actions/homeassistant.py` or `shell.py`
2. Decorate with `@action("action_name")`
3. First param must be `ctx: ActionContext`
4. Additional params come from config `params`

```python
@action("ha_new_action")
def new_action(ctx: ActionContext, entity_id: str, value: int = 100):
    ctx.ha_client.call_service("light", "turn_on", entity_id, brightness_pct=value)
```

### Adding a new MIDI message type

1. Add dataclass in `midi_triggers/messages.py`
2. Update `parse_message()` function
3. Add match handling in `broker.py`

### Modifying config structure

1. Update schema in `midi_triggers/config.py`
2. Update `_load_mappings()` or relevant loader function
3. Update `config.yaml` example

## Dependencies

- `mido` - MIDI I/O (with rtmidi backend)
- `requests` - HTTP for Home Assistant
- `pyyaml` - Config parsing
- `rumps` - macOS menubar (optional)

## Running

```bash
# Standard run
python -m midi_triggers run

# Debug with verbose output
python -m midi_triggers run  # (add logging if needed)

# List devices to verify MIDI connection
python -m midi_triggers list-devices
```

## Environment Variables

- `HA_URL` - Home Assistant base URL (e.g., `http://192.168.1.100:8123`)
- `HA_TOKEN` - Long-lived access token from Home Assistant

## Notes

- No tests currently - manual testing with actual MIDI devices
- macOS-focused (menubar uses rumps, some shell commands use osascript)
- MIDI port names are matched by substring, not exact match
- Cycle state resets when a different control is pressed
