"""Switch platform for Guest Mode integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .manager import GuestModeManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities from config entry."""
    manager: GuestModeManager = entry.runtime_data
    entities: list[SwitchEntity] = [MainGuestModeSwitch(manager)]
    entities.extend(ZoneGuestModeSwitch(manager, zone_id) for zone_id in manager.zones)
    async_add_entities(entities)


class _GuestModeSwitch(SwitchEntity):
    """Common behaviour: no polling, refresh whenever the manager changes."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: GuestModeManager) -> None:
        self._manager = manager
        self._entry = manager.entry

    @property
    def device_info(self) -> dr.DeviceInfo:
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Guest Mode",
            manufacturer="KrX3D",
            model="Guest Mode",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._manager.signal, self._handle_update)
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class MainGuestModeSwitch(_GuestModeSwitch):
    """Master switch: on while any zone is on; toggles every zone."""

    _attr_name = None  # use the device name, i.e. switch.guest_mode
    _attr_translation_key = "main"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_main_{self._entry.entry_id}"

    @property
    def is_on(self) -> bool:
        return bool(self._manager.active_zone_ids)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        zones = self._manager.zones
        return {
            "active_zones": [zones[z]["name"] for z in self._manager.active_zone_ids],
            "zone_count": len(zones),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._manager.async_activate_all()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._manager.async_deactivate_all()


class ZoneGuestModeSwitch(_GuestModeSwitch):
    """Switch for a single guest mode zone."""

    _attr_translation_key = "zone"

    def __init__(self, manager: GuestModeManager, zone_id: str) -> None:
        super().__init__(manager)
        self.zone_id = zone_id

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_zone_{self.zone_id}_{self._entry.entry_id}"

    @property
    def name(self) -> str:
        return self._manager.zones[self.zone_id]["name"]

    @property
    def is_on(self) -> bool:
        return self._manager.is_active(self.zone_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        record = self._manager.record(self.zone_id)
        if record is None:
            return {}
        return {
            "active_since": record.get("since"),
            "auto_off_at": record.get("until"),
            "saved_entities": list(record["entities"]),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._manager.async_activate_zone(self.zone_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._manager.async_deactivate_zone(self.zone_id)
