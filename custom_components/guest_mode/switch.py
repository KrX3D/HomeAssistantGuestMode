"""Switch platform for Guest Mode integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    CONF_AUTOMATIONS_OFF,
    CONF_AUTOMATIONS_ON,
    CONF_SCRIPTS_OFF,
    CONF_SCRIPTS_ON,
    CONF_ENTITIES_OFF,
    CONF_ENTITIES_ON,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities from config entry."""
    zones = entry.data.get("zones", {})
    entities: list[SwitchEntity] = [MainGuestModeSwitch(hass, entry)]

    for zone_id, zone_data in zones.items():
        entities.append(ZoneGuestModeSwitch(hass, entry, zone_id, zone_data))

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Shared device info
# ---------------------------------------------------------------------------

def _device_info(entry: ConfigEntry) -> dr.DeviceInfo:
    return dr.DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Guest Mode",
        manufacturer="KrX3D",
        model="Guest Mode",
        entry_type=dr.DeviceEntryType.SERVICE,
    )


# ---------------------------------------------------------------------------
# Main (all-zones) switch
# ---------------------------------------------------------------------------

class MainGuestModeSwitch(SwitchEntity, RestoreEntity):
    """Master switch — delegates to every zone switch."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._is_on = False

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_main_{self.entry.entry_id}"

    @property
    def name(self) -> str:
        return "Guest Mode"

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def icon(self) -> str:
        return "mdi:account-multiple"

    @property
    def device_info(self) -> dr.DeviceInfo:
        return _device_info(self.entry)

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._is_on = True
        for zone_id in self.entry.data.get("zones", {}):
            await self.hass.services.async_call(
                "homeassistant", "turn_on",
                {"entity_id": f"switch.guest_mode_{zone_id}"},
            )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._is_on = False
        for zone_id in self.entry.data.get("zones", {}):
            await self.hass.services.async_call(
                "homeassistant", "turn_off",
                {"entity_id": f"switch.guest_mode_{zone_id}"},
            )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last:
            self._is_on = last.state == "on"


# ---------------------------------------------------------------------------
# Per-zone switch
# ---------------------------------------------------------------------------

class ZoneGuestModeSwitch(SwitchEntity, RestoreEntity):
    """Switch for a single guest mode zone."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        zone_id: str,
        zone_data: dict[str, Any],
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.zone_id = zone_id
        self.zone_data = zone_data
        self._is_on = False

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_zone_{self.zone_id}_{self.entry.entry_id}"

    @property
    def name(self) -> str:
        return self.zone_data["name"]

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def icon(self) -> str:
        return "mdi:door-open" if self._is_on else "mdi:door-closed"

    @property
    def device_info(self) -> dr.DeviceInfo:
        return _device_info(self.entry)

    # ------------------------------------------------------------------
    # Turn ON
    # ------------------------------------------------------------------

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable guest mode for this zone."""
        self._is_on = True
        data = self.hass.data[DOMAIN][self.entry.entry_id]
        data["saved_states"][self.zone_id] = {}

        # Resolve only entities that currently exist in HA state machine
        valid = self._resolve_entities()
        removed = valid["removed_count"]
        if removed:
            _LOGGER.warning(
                "Zone '%s': %d configured entities no longer exist and were skipped",
                self.zone_data["name"], removed,
            )

        # Save current states for everything we are about to touch
        all_managed = (
            valid[CONF_AUTOMATIONS_OFF] + valid[CONF_AUTOMATIONS_ON]
            + valid[CONF_SCRIPTS_OFF]     + valid[CONF_SCRIPTS_ON]
            + valid[CONF_ENTITIES_OFF]    + valid[CONF_ENTITIES_ON]
        )
        for entity_id in all_managed:
            state = self.hass.states.get(entity_id)
            if state:
                data["saved_states"][self.zone_id][entity_id] = state.state

        # Apply changes — use domain-specific services where possible
        await self._call_many("automation", "turn_off", valid[CONF_AUTOMATIONS_OFF])
        await self._call_many("automation", "turn_on",  valid[CONF_AUTOMATIONS_ON])
        await self._call_many("script",     "turn_off", valid[CONF_SCRIPTS_OFF])
        await self._call_many("script",     "turn_on",  valid[CONF_SCRIPTS_ON])
        await self._call_many("homeassistant", "turn_off", valid[CONF_ENTITIES_OFF])
        await self._call_many("homeassistant", "turn_on",  valid[CONF_ENTITIES_ON])

        # WiFi — only on first zone activation
        if not self._other_zones_active():
            await self._apply_wifi(guest_active=True)

        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Turn OFF
    # ------------------------------------------------------------------

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable guest mode and restore previous states."""
        self._is_on = False
        data = self.hass.data[DOMAIN][self.entry.entry_id]

        if self.zone_id in data["saved_states"]:
            saved = data["saved_states"].pop(self.zone_id)
            for entity_id, state in saved.items():
                domain = entity_id.split(".", 1)[0]
                svc_domain = domain if domain in ("automation", "script") else "homeassistant"
                service = "turn_on" if state == "on" else "turn_off"
                await self.hass.services.async_call(
                    svc_domain, service, {"entity_id": entity_id}
                )

        # WiFi — only on last zone deactivation
        if not self._other_zones_active():
            await self._apply_wifi(guest_active=False)

        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last:
            self._is_on = last.state == "on"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_entities(self) -> dict:
        """Filter zone entity lists down to those that currently exist."""
        zd = self.zone_data
        result: dict[str, Any] = {}
        total_configured = 0
        total_valid = 0

        for key in (
            CONF_AUTOMATIONS_OFF, CONF_AUTOMATIONS_ON,
            CONF_SCRIPTS_OFF,     CONF_SCRIPTS_ON,
            CONF_ENTITIES_OFF,    CONF_ENTITIES_ON,
        ):
            configured = zd.get(key, [])
            valid = [e for e in configured if self.hass.states.get(e)]
            result[key] = valid
            total_configured += len(configured)
            total_valid += len(valid)

        result["removed_count"] = total_configured - total_valid
        return result

    async def _call_many(self, domain: str, service: str, entity_ids: list[str]) -> None:
        """Call a service for each entity in the list."""
        for entity_id in entity_ids:
            await self.hass.services.async_call(
                domain, service, {"entity_id": entity_id}
            )

    async def _apply_wifi(self, *, guest_active: bool) -> None:
        """Set the WiFi entity to the configured state (or its inverse on deactivation)."""
        global_wifi = self.entry.data.get("global_wifi", {})
        wifi_entity = global_wifi.get("entity")
        if not wifi_entity:
            return

        if not self.hass.states.get(wifi_entity):
            _LOGGER.warning("Configured WiFi entity '%s' no longer exists", wifi_entity)
            return

        wifi_mode = global_wifi.get("mode", "off")  # desired state when guest is ON
        if guest_active:
            service = "turn_on" if wifi_mode == "on" else "turn_off"
        else:
            service = "turn_off" if wifi_mode == "on" else "turn_on"

        await self.hass.services.async_call(
            "homeassistant", service, {"entity_id": wifi_entity}
        )

    def _other_zones_active(self) -> bool:
        """Return True if any *other* zone switch is currently on."""
        for zone_id in self.entry.data.get("zones", {}):
            if zone_id == self.zone_id:
                continue
            state = self.hass.states.get(f"switch.guest_mode_{zone_id}")
            if state and state.state == "on":
                return True
        return False