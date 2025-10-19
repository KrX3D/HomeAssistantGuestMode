from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)
DOMAIN = "guest_mode"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities."""
    zones = entry.data.get("zones", {})
    entities = [MainGuestModeSwitch(hass, entry)]

    for zone_id, zone_data in zones.items():
        entities.append(ZoneGuestModeSwitch(hass, entry, zone_id, zone_data))

    async_add_entities(entities)


class MainGuestModeSwitch(SwitchEntity, RestoreEntity):
    """Main guest mode toggle."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self._is_on = False

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{DOMAIN}_main_{self.entry.entry_id}"

    @property
    def name(self) -> str:
        """Return name."""
        return "Guest Mode"

    @property
    def is_on(self) -> bool:
        """Return state."""
        return self._is_on

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:account-multiple"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on guest mode."""
        self._is_on = True
        zones = self.entry.data.get("zones", {})
        for zone_id in zones:
            entity_id = f"switch.guest_mode_zone_{zone_id}"
            await self.hass.services.async_call(
                "homeassistant",
                "turn_on",
                {"entity_id": entity_id},
            )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off guest mode."""
        self._is_on = False
        zones = self.entry.data.get("zones", {})
        for zone_id in zones:
            entity_id = f"switch.guest_mode_zone_{zone_id}"
            await self.hass.services.async_call(
                "homeassistant",
                "turn_off",
                {"entity_id": entity_id},
            )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore state."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._is_on = state.state == "on"


class ZoneGuestModeSwitch(SwitchEntity, RestoreEntity):
    """Per-zone guest mode switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        zone_id: str,
        zone_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.zone_id = zone_id
        self.zone_data = zone_data
        self._is_on = False

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{DOMAIN}_zone_{self.zone_id}_{self.entry.entry_id}"

    @property
    def name(self) -> str:
        """Return name."""
        return f"Guest Mode - {self.zone_data['name']}"

    @property
    def is_on(self) -> bool:
        """Return state."""
        return self._is_on

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:door-open" if self._is_on else "mdi:door-closed"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable guest mode for zone."""
        self._is_on = True
        data = self.hass.data[DOMAIN][self.entry.entry_id]
        data["saved_states"][self.zone_id] = {}

        # Collect all entities to manage
        all_entities_to_manage = (
            self.zone_data.get("automations_off", [])
            + self.zone_data.get("automations_on", [])
            + self.zone_data.get("scripts_off", [])
            + self.zone_data.get("scripts_on", [])
            + self.zone_data.get("entities_off", [])
            + self.zone_data.get("entities_on", [])
        )

        # Save current states
        for entity_id in all_entities_to_manage:
            state = self.hass.states.get(entity_id)
            if state:
                data["saved_states"][self.zone_id][entity_id] = state.state

        # Turn OFF automations
        for entity_id in self.zone_data.get("automations_off", []):
            await self.hass.services.async_call(
                "automation", "turn_off", {"entity_id": entity_id}
            )

        # Turn OFF scripts
        for entity_id in self.zone_data.get("scripts_off", []):
            await self.hass.services.async_call(
                "script", "turn_off", {"entity_id": entity_id}
            )

        # Turn OFF entities
        for entity_id in self.zone_data.get("entities_off", []):
            await self.hass.services.async_call(
                "homeassistant", "turn_off", {"entity_id": entity_id}
            )

        # Turn ON automations
        for entity_id in self.zone_data.get("automations_on", []):
            await self.hass.services.async_call(
                "automation", "turn_on", {"entity_id": entity_id}
            )

        # Turn ON scripts
        for entity_id in self.zone_data.get("scripts_on", []):
            await self.hass.services.async_call(
                "script", "turn_on", {"entity_id": entity_id}
            )

        # Turn ON entities
        for entity_id in self.zone_data.get("entities_on", []):
            await self.hass.services.async_call(
                "homeassistant", "turn_on", {"entity_id": entity_id}
            )

        # Handle global WiFi
        global_wifi = self.entry.data.get("global_wifi", {})
        if global_wifi.get("entity"):
            service = "turn_on" if global_wifi.get("mode") == "on" else "turn_off"
            await self.hass.services.async_call(
                "homeassistant", service, {"entity_id": global_wifi["entity"]}
            )

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable guest mode for zone."""
        self._is_on = False
        data = self.hass.data[DOMAIN][self.entry.entry_id]

        # Restore states
        if self.zone_id in data["saved_states"]:
            states = data["saved_states"][self.zone_id]
            for entity_id, state in states.items():
                service = "turn_on" if state == "on" else "turn_off"
                await self.hass.services.async_call(
                    "homeassistant", service, {"entity_id": entity_id}
                )
            del data["saved_states"][self.zone_id]

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore state."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._is_on = state.state == "on"