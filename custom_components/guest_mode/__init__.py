"""Guest Mode Integration."""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch"]

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
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
        """Restore saved states for a specific zone (manual service call)."""
        zone_id = call.data.get("zone_id")
        data = hass.data[DOMAIN][entry.entry_id]

        if zone_id not in data["saved_states"]:
            _LOGGER.warning("No saved states found for zone '%s'", zone_id)
            return

        saved = data["saved_states"].pop(zone_id)
        for entity_id, state in saved.items():
            # Use domain-specific services for automations and scripts
            entity_domain = entity_id.split(".", 1)[0]
            svc_domain = (
                entity_domain if entity_domain in ("automation", "script")
                else "homeassistant"
            )
            service = "turn_on" if state == "on" else "turn_off"
            await hass.services.async_call(
                svc_domain, service, {"entity_id": entity_id}
            )

    hass.services.async_register(
        DOMAIN,
        "restore_zone_states",
        handle_restore_states,
        schema=vol.Schema({vol.Required("zone_id"): cv.string}),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok