"""
Configuration loading and validation.

Handles YAML config parsing with environment variable expansion.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class DeviceConfig:
    """Configuration for a MIDI device."""
    name: str
    match: str
    enabled: bool = True


@dataclass
class MatchRule:
    """Rule for matching MIDI messages."""
    type: str  # control_change, note_on, note_off, program_change, pitchwheel
    channel: int | None = None
    control: int | None = None  # For CC
    note: int | None = None  # For Note On/Off
    program: int | None = None  # For Program Change
    value_min: int | None = None  # For CC value range
    value_max: int | None = None
    velocity_min: int | None = None  # For Note velocity range
    velocity_max: int | None = None


@dataclass
class MappingEntry:
    """A single mapping from MIDI message to action."""
    match: MatchRule
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    cycle: bool = False


@dataclass
class HomeAssistantConfig:
    """Home Assistant connection configuration."""
    url: str
    token: str


@dataclass
class Config:
    """Root configuration object."""
    home_assistant: HomeAssistantConfig | None
    devices: list[DeviceConfig]
    presets: dict[str, list[dict[str, Any]]]
    mappings: dict[str, list[MappingEntry]]  # device_name -> mappings


def expand_env_vars(value: str) -> str:
    """Expand environment variables in a string.

    Supports ${VAR} syntax.
    """
    pattern = re.compile(r'\$\{([^}]+)\}')

    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, "")

    return pattern.sub(replacer, value)


def expand_env_vars_recursive(obj: Any) -> Any:
    """Recursively expand environment variables in a data structure."""
    if isinstance(obj, str):
        return expand_env_vars(obj)
    elif isinstance(obj, dict):
        return {k: expand_env_vars_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [expand_env_vars_recursive(item) for item in obj]
    return obj


def resolve_preset_reference(value: Any, presets: dict[str, list[dict[str, Any]]]) -> Any:
    """Resolve preset references ($preset_name) in values."""
    if isinstance(value, str) and value.startswith("$"):
        preset_name = value[1:]
        if preset_name in presets:
            return presets[preset_name]
        raise ValueError(f"Unknown preset: {preset_name}")
    return value


def parse_match_rule(data: dict[str, Any]) -> MatchRule:
    """Parse a match rule from config data."""
    # Handle velocity/value as range objects or single values
    velocity = data.get("velocity")
    velocity_min = velocity_max = None
    if isinstance(velocity, dict):
        velocity_min = velocity.get("min")
        velocity_max = velocity.get("max")
    elif isinstance(velocity, int):
        velocity_min = velocity_max = velocity

    value = data.get("value")
    value_min = value_max = None
    if isinstance(value, dict):
        value_min = value.get("min")
        value_max = value.get("max")
    elif isinstance(value, int):
        value_min = value_max = value

    return MatchRule(
        type=data["type"],
        channel=data.get("channel"),
        control=data.get("control"),
        note=data.get("note"),
        program=data.get("program"),
        value_min=value_min,
        value_max=value_max,
        velocity_min=velocity_min,
        velocity_max=velocity_max,
    )


def parse_mapping_entry(data: dict[str, Any], presets: dict[str, list[dict[str, Any]]]) -> MappingEntry:
    """Parse a mapping entry from config data."""
    params = data.get("params", {})

    # Resolve preset references in params
    resolved_params = {}
    for key, value in params.items():
        resolved_params[key] = resolve_preset_reference(value, presets)

    return MappingEntry(
        match=parse_match_rule(data["match"]),
        action=data["action"],
        params=resolved_params,
        cycle=data.get("cycle", False),
    )


def load_config(path: Path) -> Config:
    """Load configuration from a YAML file."""
    with open(path) as f:
        raw = yaml.safe_load(f)

    # Expand environment variables
    raw = expand_env_vars_recursive(raw)

    # Parse Home Assistant config
    ha_config = None
    if "home_assistant" in raw:
        ha_data = raw["home_assistant"]
        ha_config = HomeAssistantConfig(
            url=ha_data.get("url", ""),
            token=ha_data.get("token", ""),
        )

    # Parse devices
    devices = []
    for dev_data in raw.get("devices", []):
        devices.append(DeviceConfig(
            name=dev_data["name"],
            match=dev_data["match"],
            enabled=dev_data.get("enabled", True),
        ))

    # Parse presets
    presets = raw.get("presets", {})

    # Parse mappings
    mappings: dict[str, list[MappingEntry]] = {}
    for device_name, mapping_list in raw.get("mappings", {}).items():
        mappings[device_name] = [
            parse_mapping_entry(entry, presets) for entry in mapping_list
        ]

    return Config(
        home_assistant=ha_config,
        devices=devices,
        presets=presets,
        mappings=mappings,
    )
