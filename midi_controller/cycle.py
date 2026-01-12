"""
Cycle state management.

Tracks cycling state for actions that cycle through presets.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CycleKey:
    """Unique key for cycle state."""
    device: str
    match_signature: str  # String representation of the match rule


@dataclass
class CycleManager:
    """
    Manages cycling state across actions.

    When the same control is pressed consecutively, the index advances.
    When a different control is pressed, the index resets.
    """
    indices: dict[CycleKey, int] = field(default_factory=dict)
    last_key: CycleKey | None = None

    def get_index(self, key: CycleKey, preset_count: int) -> int:
        """
        Get the current cycle index for a key, advancing if it's a consecutive press.

        Args:
            key: Unique identifier for this mapping.
            preset_count: Number of presets to cycle through.

        Returns:
            Current index to use for the preset.
        """
        if preset_count == 0:
            return 0

        if key not in self.indices:
            self.indices[key] = 0

        # Advance if same key pressed consecutively
        if self.last_key == key:
            self.indices[key] = (self.indices[key] + 1) % preset_count

        self.last_key = key
        return self.indices[key]

    def reset(self, key: CycleKey) -> None:
        """Reset the cycle index for a key."""
        if key in self.indices:
            del self.indices[key]

    def clear(self) -> None:
        """Clear all cycle state."""
        self.indices.clear()
        self.last_key = None
