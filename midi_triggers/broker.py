"""
Message broker for routing MIDI messages to actions.
"""

from dataclasses import dataclass
from typing import Any, Callable

from .actions.base import ActionContext
from .config import MappingEntry, MatchRule
from .cycle import CycleKey, CycleManager
from .ha.client import HAClient
from .messages import (
    ControlChange,
    MidiMessage,
    NoteOff,
    NoteOn,
    PitchWheel,
    ProgramChange,
)


def match_rule_signature(rule: MatchRule) -> str:
    """Create a string signature for a match rule (used for cycle key)."""
    parts = [rule.type]
    if rule.channel is not None:
        parts.append(f"ch{rule.channel}")
    if rule.control is not None:
        parts.append(f"cc{rule.control}")
    if rule.note is not None:
        parts.append(f"n{rule.note}")
    if rule.program is not None:
        parts.append(f"p{rule.program}")
    return "_".join(parts)


def matches_message(rule: MatchRule, msg: MidiMessage) -> bool:
    """
    Check if a MIDI message matches a rule.

    Args:
        rule: The match rule to check against.
        msg: The MIDI message to check.

    Returns:
        True if the message matches the rule.
    """
    # Check message type
    type_map = {
        "control_change": ControlChange,
        "note_on": NoteOn,
        "note_off": NoteOff,
        "program_change": ProgramChange,
        "pitchwheel": PitchWheel,
    }

    expected_type = type_map.get(rule.type)
    if expected_type is None or not isinstance(msg, expected_type):
        return False

    # Check channel (None means match any)
    if rule.channel is not None and msg.channel != rule.channel:
        return False

    # Type-specific checks
    if isinstance(msg, ControlChange):
        if rule.control is not None and msg.control != rule.control:
            return False
        # Check value range
        if rule.value_min is not None and msg.value < rule.value_min:
            return False
        if rule.value_max is not None and msg.value > rule.value_max:
            return False

    elif isinstance(msg, (NoteOn, NoteOff)):
        if rule.note is not None and msg.note != rule.note:
            return False
        # Check velocity range
        if rule.velocity_min is not None and msg.velocity < rule.velocity_min:
            return False
        if rule.velocity_max is not None and msg.velocity > rule.velocity_max:
            return False

    elif isinstance(msg, ProgramChange):
        if rule.program is not None and msg.program != rule.program:
            return False

    return True


@dataclass
class MessageBroker:
    """
    Routes MIDI messages to appropriate action handlers.

    Handles:
    - Device-specific mappings
    - Global mappings (apply to all devices)
    - Cycle state management
    """
    actions: dict[str, Callable]
    mappings: dict[str, list[MappingEntry]]  # device_name -> mappings
    ha_client: HAClient | None
    cycle_manager: CycleManager

    def handle(self, device_name: str, message: MidiMessage) -> None:
        """
        Route a message to its handler(s).

        Args:
            device_name: Name of the device that sent the message.
            message: The MIDI message to route.
        """
        # Print the message
        print(f"[{device_name}] {message}")

        # Get device-specific mappings
        device_mappings = self.mappings.get(device_name, [])

        # Get global mappings
        global_mappings = self.mappings.get("global", [])

        # Check all applicable mappings
        for mapping in device_mappings + global_mappings:
            if matches_message(mapping.match, message):
                self._invoke_action(device_name, message, mapping)

    def _invoke_action(
        self,
        device_name: str,
        message: MidiMessage,
        mapping: MappingEntry,
    ) -> None:
        """Invoke an action for a matched mapping."""
        action_func = self.actions.get(mapping.action)
        if action_func is None:
            print(f"  -> Warning: Unknown action '{mapping.action}'")
            return

        # Handle cycling
        cycle_index = None
        preset_value = None

        if mapping.cycle:
            presets = mapping.params.get("presets", [])
            if presets:
                key = CycleKey(
                    device=device_name,
                    match_signature=match_rule_signature(mapping.match),
                )
                cycle_index = self.cycle_manager.get_index(key, len(presets))
                preset_value = presets[cycle_index]

        # Build context
        ctx = ActionContext(
            ha=self.ha_client,
            message=message,
            device_name=device_name,
            cycle_index=cycle_index,
            preset_value=preset_value,
        )

        # Build params (exclude presets as it's handled via preset_value)
        params = {k: v for k, v in mapping.params.items() if k != "presets"}

        # Invoke the action
        try:
            action_func(ctx, **params)
        except Exception as e:
            print(f"  -> Error in action '{mapping.action}': {e}")


def create_broker(
    actions: dict[str, Callable],
    mappings: dict[str, list[MappingEntry]],
    ha_client: HAClient | None,
) -> MessageBroker:
    """
    Create a message broker with the given configuration.

    Args:
        actions: Dictionary of action name -> action function.
        mappings: Dictionary of device name -> list of mappings.
        ha_client: Optional Home Assistant client.

    Returns:
        Configured MessageBroker.
    """
    return MessageBroker(
        actions=actions,
        mappings=mappings,
        ha_client=ha_client,
        cycle_manager=CycleManager(),
    )
