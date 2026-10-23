"""Guest Mode Integration."""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SERVICE_RESTORE_ZONE_STATES, STORAGE_VERSION
from .manager import GuestModeManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type GuestModeConfigEntry = ConfigEntry[GuestModeManager]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services (once, independent of config entries)."""

    async def handle_restore_states(call: ServiceCall) -> None:
        """Restore saved states for a specific zone and switch it off."""
        zone_id = call.data["zone_id"]
        for entry in hass.config_entries.async_entries(DOMAIN):
            manager: GuestModeManager | None = getattr(entry, "runtime_data", None)
            if manager is not None and manager.is_active(zone_id):
                await manager.async_deactivate_zone(zone_id)
                return
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="zone_not_active",
            translation_placeholders={"zone_id": zone_id},
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESTORE_ZONE_STATES,
        handle_restore_states,
        schema=vol.Schema({vol.Required("zone_id"): cv.string}),
    )
    return True


def _remove_orphan_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove registry entries of zones that were deleted."""
    registry = er.async_get(hass)
    wanted = {f"{DOMAIN}_main_{entry.entry_id}"} | {
        f"{DOMAIN}_zone_{zone_id}_{entry.entry_id}"
        for zone_id in entry.data.get("zones", {})
    }
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.unique_id not in wanted:
            registry.async_remove(reg_entry.entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: GuestModeConfigEntry) -> bool:
    """Set up integration from config entry."""
    # Saved pre-guest-mode states are persisted to disk so an active zone is
    # still restored correctly after a Home Assistant restart.
    store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}_saved_states")
    manager = GuestModeManager(hass, entry, store)
    await manager.async_load()
    entry.runtime_data = manager

    _remove_orphan_entities(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(manager.async_stop)
    if cancel := manager.async_start():
        entry.async_on_unload(cancel)
    # Any change to zones / WiFi reloads the entry so the switches pick it up.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: GuestModeConfigEntry) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
