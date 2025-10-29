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
            entity_id = f"switch.guest_mode_{zone_id}"
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
            entity_id = f"switch.guest_mode_{zone_id}"
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

        # Validate and clean up non-existent entities
        all_automations_off = [e for e in self.zone_data.get("automations_off", []) if self.hass.states.get(e)]
        all_automations_on = [e for e in self.zone_data.get("automations_on", []) if self.hass.states.get(e)]
        all_scripts_off = [e for e in self.zone_data.get("scripts_off", []) if self.hass.states.get(e)]
        all_scripts_on = [e for e in self.zone_data.get("scripts_on", []) if self.hass.states.get(e)]
        all_entities_off = [e for e in self.zone_data.get("entities_off", []) if self.hass.states.get(e)]
        all_entities_on = [e for e in self.zone_data.get("entities_on", []) if self.hass.states.get(e)]

        # Log if any entities were removed
        removed_count = (
            len(self.zone_data.get("automations_off", [])) - len(all_automations_off) +
            len(self.zone_data.get("automations_on", [])) - len(all_automations_on) +
            len(self.zone_data.get("scripts_off", [])) - len(all_scripts_off) +
            len(self.zone_data.get("scripts_on", [])) - len(all_scripts_on) +
            len(self.zone_data.get("entities_off", [])) - len(all_entities_off) +
            len(self.zone_data.get("entities_on", [])) - len(all_entities_on)
        )
        if removed_count > 0:
            _LOGGER.warning(f"Zone '{self.zone_data['name']}': {removed_count} configured entities no longer exist and were skipped")

        # Collect all valid entities to manage
        all_entities_to_manage = (
            all_automations_off + all_automations_on +
            all_scripts_off + all_scripts_on +
            all_entities_off + all_entities_on
        )

        # Save current states
        for entity_id in all_entities_to_manage:
            state = self.hass.states.get(entity_id)
            if state:
                data["saved_states"][self.zone_id][entity_id] = state.state

        # Turn OFF automations
        for entity_id in all_automations_off:
            await self.hass.services.async_call(
                "automation", "turn_off", {"entity_id": entity_id}
            )

        # Turn OFF scripts
        for entity_id in all_scripts_off:
            await self.hass.services.async_call(
                "script", "turn_off", {"entity_id": entity_id}
            )

        # Turn OFF entities
        for entity_id in all_entities_off:
            await self.hass.services.async_call(
                "homeassistant", "turn_off", {"entity_id": entity_id}
            )

        # Turn ON automations
        for entity_id in all_automations_on:
            await self.hass.services.async_call(
                "automation", "turn_on", {"entity_id": entity_id}
            )

        # Turn ON scripts
        for entity_id in all_scripts_on:
            await self.hass.services.async_call(
                "script", "turn_on", {"entity_id": entity_id}
            )

        # Turn ON entities
        for entity_id in all_entities_on:
            await self.hass.services.async_call(
                "homeassistant", "turn_on", {"entity_id": entity_id}
            )

        # Handle global WiFi
        global_wifi = self.entry.data.get("global_wifi", {})
        if global_wifi.get("entity"):
            wifi_entity = global_wifi["entity"]
            # Validate WiFi entity exists
            if self.hass.states.get(wifi_entity):
                wifi_mode = global_wifi.get("mode", "off")
                # When guest mode ON: set WiFi to the configured mode
                service = "turn_on" if wifi_mode == "on" else "turn_off"
                await self.hass.services.async_call(
                    "homeassistant", service, {"entity_id": wifi_entity}
                )
            else:
                _LOGGER.warning(f"Configured WiFi entity '{wifi_entity}' no longer exists")

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable guest mode for zone."""
        self._is_on = False
        
        # Restore automations and scripts to their previous states
        data = self.hass.data[DOMAIN][self.entry.entry_id]
        if self.zone_id in data["saved_states"]:
            states = data["saved_states"][self.zone_id]
            for entity_id, state in states.items():
                service = "turn_on" if state == "on" else "turn_off"
                await self.hass.services.async_call(
                    "homeassistant", service, {"entity_id": entity_id}
                )
            del data["saved_states"][self.zone_id]
        
        # Handle global WiFi - switch to opposite of configured mode
        global_wifi = self.entry.data.get("global_wifi", {})
        if global_wifi.get("entity"):
            wifi_entity = global_wifi["entity"]
            wifi_mode = global_wifi.get("mode", "off")
            
            # When guest mode OFF: set WiFi to opposite of configured mode
            service = "turn_off" if wifi_mode == "on" else "turn_on"
            await self.hass.services.async_call(
                "homeassistant", service, {"entity_id": wifi_entity}
            )

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore state."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._is_on = state.state == "on"