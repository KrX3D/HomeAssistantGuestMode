"""Guest Mode Integration - Complete Package"""

from __future__ import annotations
import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "guest_mode"
PLATFORMS = ["switch"]

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up integration from config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "saved_states": {},
        "zones": entry.data.get("zones", {}),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_restore_states(call: ServiceCall) -> None:
        """Restore saved states."""
        zone_id = call.data.get("zone_id")
        data = hass.data[DOMAIN][entry.entry_id]
        
        if zone_id in data["saved_states"]:
            states = data["saved_states"][zone_id]
            for entity_id, state in states.items():
                await hass.services.async_call(
                    "homeassistant",
                    "turn_on" if state == "on" else "turn_off",
                    {"entity_id": entity_id},
                )
            del data["saved_states"][zone_id]

    hass.services.async_register(
        DOMAIN, "restore_zone_states", handle_restore_states
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok