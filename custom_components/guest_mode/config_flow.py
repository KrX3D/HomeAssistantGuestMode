"""Config flow for Guest Mode integration."""
from __future__ import annotations

import copy
import logging
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_AUTO_OFF_HOURS,
    CONF_AUTOMATIONS_OFF,
    CONF_AUTOMATIONS_ON,
    CONF_ENTITIES_OFF,
    CONF_ENTITIES_ON,
    CONF_SCRIPTS_OFF,
    CONF_SCRIPTS_ON,
    CONF_UPDATE_ENTITY_ID,
    CONF_WIFI_ENTITY,
    CONF_WIFI_MODE,
    CONF_ZONE_NAME,
    DOMAIN,
    ZONE_LIST_KEYS,
)

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reusable entity selectors (searchable, fast — no manual options dict needed)
# ---------------------------------------------------------------------------

_SELECTOR_AUTOMATIONS = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="automation", multiple=True)
)
_SELECTOR_SCRIPTS = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="script", multiple=True)
)
_SELECTOR_WIFI = selector.EntitySelector(
    selector.EntitySelectorConfig(multiple=False)
)
_SELECTOR_AUTO_OFF = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0,
        max=720,
        step=0.5,
        unit_of_measurement="h",
        mode=selector.NumberSelectorMode.BOX,
    )
)


def _own_entity_ids(hass) -> list[str]:
    """Entity IDs created by this integration (never offered inside a zone)."""
    registry = er.async_get(hass)
    return [e.entity_id for e in registry.entities.values() if e.platform == DOMAIN]


def _zone_schema(
    hass, *, with_entity_id_option: bool = False
) -> vol.Schema:
    """Zone add/edit schema. Existing values are pre-filled as *suggested* values
    (see add_suggested_values_to_schema) so a field can really be cleared."""
    entities_selector = selector.EntitySelector(
        selector.EntitySelectorConfig(
            multiple=True, exclude_entities=_own_entity_ids(hass)
        )
    )
    fields: dict[Any, Any] = {
        vol.Required(CONF_ZONE_NAME): cv.string,
        vol.Optional(CONF_AUTOMATIONS_OFF): _SELECTOR_AUTOMATIONS,
        vol.Optional(CONF_AUTOMATIONS_ON): _SELECTOR_AUTOMATIONS,
        vol.Optional(CONF_SCRIPTS_OFF): _SELECTOR_SCRIPTS,
        vol.Optional(CONF_SCRIPTS_ON): _SELECTOR_SCRIPTS,
        vol.Optional(CONF_ENTITIES_OFF): entities_selector,
        vol.Optional(CONF_ENTITIES_ON): entities_selector,
        vol.Optional(CONF_AUTO_OFF_HOURS, default=0): _SELECTOR_AUTO_OFF,
    }
    if with_entity_id_option:
        fields[vol.Optional(CONF_UPDATE_ENTITY_ID, default=False)] = cv.boolean
    return vol.Schema(fields)


def _wifi_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_WIFI_ENTITY): _SELECTOR_WIFI,
            vol.Optional(CONF_WIFI_MODE, default="off"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["on", "off"],
                    translation_key="wifi_mode",
                )
            ),
        }
    )


def _zone_from_input(name: str, user_input: dict[str, Any]) -> dict[str, Any]:
    zone: dict[str, Any] = {"name": name}
    for key in ZONE_LIST_KEYS:
        zone[key] = user_input.get(key, [])
    zone[CONF_AUTO_OFF_HOURS] = float(user_input.get(CONF_AUTO_OFF_HOURS) or 0)
    return zone


def _zone_suggestions(zone: dict[str, Any]) -> dict[str, Any]:
    suggested = {CONF_ZONE_NAME: zone.get("name", "")}
    for key in ZONE_LIST_KEYS:
        suggested[key] = zone.get(key, [])
    suggested[CONF_AUTO_OFF_HOURS] = zone.get(CONF_AUTO_OFF_HOURS, 0)
    return suggested


# ---------------------------------------------------------------------------
# Steps shared by the initial config flow and the options flow
# ---------------------------------------------------------------------------

class _ZoneFlowMixin:
    """Zone / WiFi steps. Host classes provide ``_commit`` and ``_menu``."""

    zones: dict[str, dict[str, Any]]
    global_wifi: dict[str, Any]
    _pending: dict[str, Any]
    _zone_to_edit: str | None

    async def _menu(self):  # pragma: no cover - implemented by host
        raise NotImplementedError

    def _commit(self) -> None:  # pragma: no cover - implemented by host
        raise NotImplementedError

    # -- helpers ---------------------------------------------------------

    def _zone_entity_id(self, zone_id: str) -> str | None:
        entry_id = getattr(getattr(self, "config_entry", None), "entry_id", None)
        if entry_id is None:
            return None
        return er.async_get(self.hass).async_get_entity_id(
            "switch", DOMAIN, f"{DOMAIN}_zone_{zone_id}_{entry_id}"
        )

    def _validate_name(self, raw: str, editing: str | None) -> tuple[str, str | None]:
        """Return (clean name, error key or None)."""
        name = raw.strip()
        if not name:
            return name, "zone_name_required"
        if not slugify(name):
            return name, "zone_name_invalid"
        taken = {
            slugify(z["name"]) for zid, z in self.zones.items() if zid != editing
        } | {zid for zid in self.zones if zid != editing}
        if slugify(name) in taken:
            return name, "zone_name_duplicate"
        return name, None

    def _describe(self, entity_ids: list[str]) -> str:
        if not entity_ids:
            return "-"
        parts = []
        for entity_id in entity_ids:
            state = self.hass.states.get(entity_id)
            parts.append(f"{state.name} (`{entity_id}`)" if state else f"`{entity_id}`")
        return ", ".join(parts)

    # -- add / edit ------------------------------------------------------

    async def async_step_add_zone(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            name, error = self._validate_name(user_input.get(CONF_ZONE_NAME, ""), None)
            if error:
                errors[CONF_ZONE_NAME] = error
            else:
                self._pending = {
                    "zone_id": slugify(name),
                    "zone": _zone_from_input(name, user_input),
                    "rename_entity": False,
                }
                return await self.async_step_preview()

        schema = _zone_schema(self.hass)
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="add_zone", data_schema=schema, errors=errors)

    async def async_step_select_edit(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._zone_to_edit = user_input["zone"]
            return await self.async_step_edit_zone()
        return self.async_show_form(
            step_id="select_edit", data_schema=self._zone_picker(next(iter(self.zones)))
        )

    def _zone_picker(self, default: str) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("zone", default=default): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": zid, "label": z["name"]}
                            for zid, z in self.zones.items()
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

    async def async_step_edit_zone(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        zone_id = self._zone_to_edit
        zone = self.zones[zone_id]
        has_registry_entity = self._zone_entity_id(zone_id) is not None

        if user_input is not None:
            name, error = self._validate_name(user_input.get(CONF_ZONE_NAME, ""), zone_id)
            rename_entity = bool(user_input.get(CONF_UPDATE_ENTITY_ID))
            if error:
                errors[CONF_ZONE_NAME] = error
            elif rename_entity and has_registry_entity:
                target = f"switch.guest_mode_{slugify(name)}"
                current = self._zone_entity_id(zone_id)
                if target != current and er.async_get(self.hass).async_get(target):
                    errors[CONF_UPDATE_ENTITY_ID] = "entity_id_taken"
            if not errors:
                self._pending = {
                    "zone_id": zone_id,
                    "zone": _zone_from_input(name, user_input),
                    "rename_entity": rename_entity and has_registry_entity,
                }
                return await self.async_step_preview()

        schema = _zone_schema(self.hass, with_entity_id_option=has_registry_entity)
        schema = self.add_suggested_values_to_schema(
            schema, user_input if user_input is not None else _zone_suggestions(zone)
        )
        return self.async_show_form(step_id="edit_zone", data_schema=schema, errors=errors)

    # -- dry-run preview -------------------------------------------------

    async def async_step_preview(self, user_input: dict[str, Any] | None = None):
        pending = self._pending
        zone = pending["zone"]

        if user_input is not None:
            zone_id = pending["zone_id"]
            self.zones[zone_id] = zone
            if pending["rename_entity"]:
                registry = er.async_get(self.hass)
                if entity_id := self._zone_entity_id(zone_id):
                    registry.async_update_entity(
                        entity_id, new_entity_id=f"switch.guest_mode_{slugify(zone['name'])}"
                    )
            self._commit()
            return await self._menu()

        existing = {
            key: [e for e in zone[key] if self.hass.states.get(e)] for key in ZONE_LIST_KEYS
        }
        missing = [e for key in ZONE_LIST_KEYS for e in zone[key] if not self.hass.states.get(e)]
        hours = zone.get(CONF_AUTO_OFF_HOURS) or 0
        return self.async_show_form(
            step_id="preview",
            data_schema=vol.Schema({}),
            description_placeholders={
                "zone": zone["name"],
                "turn_off": self._describe(
                    existing[CONF_AUTOMATIONS_OFF]
                    + existing[CONF_SCRIPTS_OFF]
                    + existing[CONF_ENTITIES_OFF]
                ),
                "turn_on": self._describe(
                    existing[CONF_AUTOMATIONS_ON]
                    + existing[CONF_SCRIPTS_ON]
                    + existing[CONF_ENTITIES_ON]
                ),
                "missing": self._describe(missing),
                "auto_off": f"{hours:g} h" if hours else "-",
            },
        )

    # -- WiFi ------------------------------------------------------------

    async def async_step_wifi(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            entity = user_input.get(CONF_WIFI_ENTITY)
            self.global_wifi = (
                {"entity": entity, "mode": user_input.get(CONF_WIFI_MODE, "off")}
                if entity
                else {}
            )
            self._commit()
            return await self._menu()

        schema = self.add_suggested_values_to_schema(
            _wifi_schema(),
            {
                CONF_WIFI_ENTITY: self.global_wifi.get("entity"),
                CONF_WIFI_MODE: self.global_wifi.get("mode", "off"),
            },
        )
        return self.async_show_form(step_id="wifi", data_schema=schema)


# ---------------------------------------------------------------------------
# Config flow (initial setup)
# ---------------------------------------------------------------------------

class GuestModeConfigFlow(_ZoneFlowMixin, config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Guest Mode."""

    VERSION = 1

    def __init__(self) -> None:
        self.zones = {}
        self.global_wifi = {}
        self._pending = {}
        self._zone_to_edit = None

    def _commit(self) -> None:
        """Nothing to persist until the user finishes."""

    async def _menu(self):
        return await self.async_step_user()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Main setup menu."""
        return self.async_show_menu(
            step_id="user", menu_options=["add_zone", "wifi", "finish"]
        )

    async def async_step_finish(self, user_input: dict[str, Any] | None = None):
        return self.async_create_entry(
            title="Guest Mode",
            data={"zones": self.zones, "global_wifi": self.global_wifi},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return GuestModeOptionsFlow()


# ---------------------------------------------------------------------------
# Options flow (reconfigure after setup)
# ---------------------------------------------------------------------------

class GuestModeOptionsFlow(_ZoneFlowMixin, config_entries.OptionsFlow):
    """Options flow for Guest Mode."""

    def __init__(self) -> None:
        self._loaded = False
        self.zones = {}
        self.global_wifi = {}
        self._pending = {}
        self._zone_to_edit = None

    def _commit(self) -> None:
        """Persist; the update listener reloads the entry so switches follow."""
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={
                "zones": copy.deepcopy(self.zones),
                "global_wifi": dict(self.global_wifi),
            },
        )

    async def _menu(self):
        return await self.async_step_init()

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Main management menu."""
        if not self._loaded:
            self.zones = copy.deepcopy(dict(self.config_entry.data.get("zones", {})))
            self.global_wifi = dict(self.config_entry.data.get("global_wifi", {}))
            self._loaded = True

        options = ["add_zone"]
        if self.zones:
            options += ["select_edit", "select_delete"]
        options += ["wifi", "finish"]
        return self.async_show_menu(step_id="init", menu_options=options)

    async def async_step_select_delete(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            # An active zone is restored by the integration on reload and its
            # switch entity is removed from the registry there as well.
            self.zones.pop(user_input["zone"], None)
            self._commit()
            return await self.async_step_init()
        return self.async_show_form(
            step_id="select_delete", data_schema=self._zone_picker(next(iter(self.zones)))
        )

    async def async_step_finish(self, user_input: dict[str, Any] | None = None):
        return self.async_create_entry(title="", data={})
