"""
Home Assistant API client.
"""

from dataclasses import dataclass

import requests


@dataclass
class HAClient:
    """Client for interacting with Home Assistant API."""
    url: str
    token: str

    def call_service(self, service: str, data: dict) -> bool:
        """
        Call a Home Assistant service.

        Args:
            service: Service name (e.g., "light/toggle", "light/turn_on")
            data: Service data (e.g., {"entity_id": "light.living_room"})

        Returns:
            True if successful, False otherwise.
        """
        url = f"{self.url}/api/services/{service}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=5)
            return response.ok
        except requests.RequestException:
            return False

    def toggle_light(self, entity_id: str) -> bool:
        """Toggle a light entity."""
        return self.call_service("light/toggle", {"entity_id": entity_id})

    def turn_on_light(self, entity_id: str, **kwargs) -> bool:
        """
        Turn on a light with optional parameters.

        Supported kwargs:
            brightness_pct: int (0-100)
            rgb_color: tuple[int, int, int]
            color_temp_kelvin: int
        """
        data = {"entity_id": entity_id, **kwargs}
        return self.call_service("light/turn_on", data)

    def set_brightness(self, entity_id: str, percent: int) -> bool:
        """Set light brightness as a percentage (0-100)."""
        return self.turn_on_light(entity_id, brightness_pct=percent)

    def set_color(self, entity_id: str, rgb: tuple[int, int, int]) -> bool:
        """Set light RGB color."""
        return self.turn_on_light(entity_id, rgb_color=list(rgb))

    def set_color_temp(self, entity_id: str, kelvin: int) -> bool:
        """Set light color temperature in Kelvin."""
        return self.turn_on_light(entity_id, color_temp_kelvin=kelvin)
