"""
Built-in Home Assistant actions.
"""

from typing import Any

from .base import ActionContext, action


@action("ha_toggle")
def ha_toggle(ctx: ActionContext, entity_id: str) -> None:
    """Toggle a Home Assistant light."""
    if ctx.ha is None:
        print("  -> Error: Home Assistant not configured")
        return

    if ctx.ha.toggle_light(entity_id):
        print(f"  -> Toggled {entity_id}")
    else:
        print(f"  -> Error toggling {entity_id}")


@action("ha_brightness")
def ha_brightness(ctx: ActionContext, entity_id: str, presets: list[dict[str, Any]] | None = None) -> None:
    """
    Set Home Assistant light brightness.

    When cycling, uses preset_value from context.
    Otherwise, uses first preset if available.
    """
    if ctx.ha is None:
        print("  -> Error: Home Assistant not configured")
        return

    # Get brightness value
    if ctx.preset_value is not None:
        preset = ctx.preset_value
    elif presets:
        preset = presets[0]
    else:
        print("  -> Error: No brightness preset provided")
        return

    percent = preset.get("percent", 100)
    label = preset.get("label", f"{percent}%")

    if ctx.ha.set_brightness(entity_id, percent):
        print(f"  -> Set {entity_id} to {label} brightness")
    else:
        print(f"  -> Error setting brightness on {entity_id}")


@action("ha_color")
def ha_color(ctx: ActionContext, entity_id: str, presets: list[dict[str, Any]] | None = None) -> None:
    """
    Set Home Assistant light RGB color.

    When cycling, uses preset_value from context.
    Otherwise, uses first preset if available.
    """
    if ctx.ha is None:
        print("  -> Error: Home Assistant not configured")
        return

    # Get color value
    if ctx.preset_value is not None:
        preset = ctx.preset_value
    elif presets:
        preset = presets[0]
    else:
        print("  -> Error: No color preset provided")
        return

    rgb = preset.get("rgb")
    name = preset.get("name", str(rgb))

    if rgb is None:
        print("  -> Error: Preset has no RGB value")
        return

    # Handle both tuple and list formats
    rgb_tuple = tuple(rgb) if isinstance(rgb, list) else rgb

    if ctx.ha.set_color(entity_id, rgb_tuple):
        print(f"  -> Set {entity_id} to {name}")
    else:
        print(f"  -> Error setting color on {entity_id}")


@action("ha_color_temp")
def ha_color_temp(ctx: ActionContext, entity_id: str, presets: list[dict[str, Any]] | None = None) -> None:
    """
    Set Home Assistant light color temperature.

    When cycling, uses preset_value from context.
    Otherwise, uses first preset if available.
    """
    if ctx.ha is None:
        print("  -> Error: Home Assistant not configured")
        return

    # Get color temp value
    if ctx.preset_value is not None:
        preset = ctx.preset_value
    elif presets:
        preset = presets[0]
    else:
        print("  -> Error: No color temperature preset provided")
        return

    kelvin = preset.get("kelvin")
    name = preset.get("name", f"{kelvin}K")

    if kelvin is None:
        print("  -> Error: Preset has no kelvin value")
        return

    if ctx.ha.set_color_temp(entity_id, kelvin):
        print(f"  -> Set {entity_id} to {name} ({kelvin}K)")
    else:
        print(f"  -> Error setting color temperature on {entity_id}")
