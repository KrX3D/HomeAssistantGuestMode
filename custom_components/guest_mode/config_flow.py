"""Config flow for Guest Mode integration."""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_ZONE_NAME,
    CONF_AUTOMATIONS_OFF,
    CONF_AUTOMATIONS_ON,
    CONF_SCRIPTS_OFF,
    CONF_SCRIPTS_ON,
    CONF_ENTITIES_OFF,
    CONF_ENTITIES_ON,
    CONF_WIFI_ENTITY,
    CONF_WIFI_MODE,
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
_SELECTOR_ENTITIES = selector.EntitySelector(
    selector.EntitySelectorConfig(multiple=True)
)
_SELECTOR_WIFI = selector.EntitySelector(
    selector.EntitySelectorConfig(multiple=False)
)


def _zone_schema(defaults: dict | None = None, exclude_entities: list[str] | None = None) -> vol.Schema:
    """Return the zone add/edit schema with optional pre-filled defaults.

    exclude_entities: entity IDs to hide from the general entity picker
    (used to filter out the integration's own switches).
    """
    d = defaults or {}

    if exclude_entities:
        entities_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(
                multiple=True,
                exclude_entities=exclude_entities,
            )
        )
    else:
        entities_selector = _SELECTOR_ENTITIES

    return vol.Schema(
        {
            vol.Required(CONF_ZONE_NAME, default=d.get(CONF_ZONE_NAME, "")): cv.string,
            vol.Optional(CONF_AUTOMATIONS_OFF, default=d.get(CONF_AUTOMATIONS_OFF, [])): _SELECTOR_AUTOMATIONS,
            vol.Optional(CONF_AUTOMATIONS_ON,  default=d.get(CONF_AUTOMATIONS_ON,  [])): _SELECTOR_AUTOMATIONS,
            vol.Optional(CONF_SCRIPTS_OFF,     default=d.get(CONF_SCRIPTS_OFF,     [])): _SELECTOR_SCRIPTS,
            vol.Optional(CONF_SCRIPTS_ON,      default=d.get(CONF_SCRIPTS_ON,      [])): _SELECTOR_SCRIPTS,
            vol.Optional(CONF_ENTITIES_OFF,    default=d.get(CONF_ENTITIES_OFF,    [])): entities_selector,
            vol.Optional(CONF_ENTITIES_ON,     default=d.get(CONF_ENTITIES_ON,     [])): entities_selector,
        }
    )


def _wifi_schema(defaults: dict | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Optional(CONF_WIFI_ENTITY, default=d.get("entity", vol.UNDEFINED)): _SELECTOR_WIFI,
            vol.Optional(CONF_WIFI_MODE,   default=d.get("mode", "off")): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["on", "off"],
                    translation_key="wifi_mode",
                )
            ),
        }
    )


# ---------------------------------------------------------------------------
# Config flow (initial setup)
# ---------------------------------------------------------------------------

class GuestModeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Guest Mode."""

    VERSION = 1

    def __init__(self) -> None:
        self.zones: dict = {}
        self.global_wifi: dict = {}

    def _guest_mode_entity_ids(self) -> list[str]:
        """Return all switch entity IDs belonging to this integration."""
        return [
            state.entity_id
            for state in self.hass.states.async_all("switch")
            if state.entity_id.startswith("switch.guest_mode")
        ]

    async def async_step_user(self, user_input=None):
        """Main setup menu."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "setup":
                return await self.async_step_add_zone()
            if action == "setup_wifi":
                return await self.async_step_setup_wifi()
            if action == "done":
                return self.async_create_entry(
                    title="Guest Mode",
                    data={"zones": self.zones, "global_wifi": self.global_wifi},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("action"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["setup", "setup_wifi", "done"],
                        translation_key="action",
                    )
                )}
            ),
        )

    async def async_step_add_zone(self, user_input=None):
        """Add a zone during initial setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            zone_name = user_input.get(CONF_ZONE_NAME, "").strip()
            if not zone_name:
                errors[CONF_ZONE_NAME] = "zone_name_required"
            else:
                zone_id = zone_name.lower().replace(" ", "_")
                self.zones[zone_id] = {
                    "name": zone_name,
                    CONF_AUTOMATIONS_OFF: user_input.get(CONF_AUTOMATIONS_OFF, []),
                    CONF_AUTOMATIONS_ON:  user_input.get(CONF_AUTOMATIONS_ON,  []),
                    CONF_SCRIPTS_OFF:     user_input.get(CONF_SCRIPTS_OFF,     []),
                    CONF_SCRIPTS_ON:      user_input.get(CONF_SCRIPTS_ON,      []),
                    CONF_ENTITIES_OFF:    user_input.get(CONF_ENTITIES_OFF,    []),
                    CONF_ENTITIES_ON:     user_input.get(CONF_ENTITIES_ON,     []),
                }
                if user_input.get("add_another"):
                    return await self.async_step_add_zone()
                return await self.async_step_user()

        schema = _zone_schema(exclude_entities=self._guest_mode_entity_ids())
        schema = schema.extend(
            {vol.Optional("add_another", default=False): cv.boolean}
        )

        return self.async_show_form(
            step_id="add_zone",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_setup_wifi(self, user_input=None):
        """Configure global WiFi."""
        if user_input is not None:
            self.global_wifi = {
                "entity": user_input.get(CONF_WIFI_ENTITY),
                "mode":   user_input.get(CONF_WIFI_MODE, "off"),
            }
            return await self.async_step_user()

        return self.async_show_form(
            step_id="setup_wifi",
            data_schema=_wifi_schema(),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return GuestModeOptionsFlow(config_entry)


# ---------------------------------------------------------------------------
# Options flow (reconfigure after setup)
# ---------------------------------------------------------------------------

class GuestModeOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Guest Mode."""

    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry
        self.zones: dict = dict(config_entry.data.get("zones", {}))
        self.global_wifi: dict = dict(config_entry.data.get("global_wifi", {}))
        self.zone_to_edit: str | None = None

    def _guest_mode_entity_ids(self) -> list[str]:
        """Return all switch entity IDs belonging to this integration."""
        return [
            state.entity_id
            for state in self.hass.states.async_all("switch")
            if state.entity_id.startswith("switch.guest_mode")
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _save(self) -> None:
        """Persist current state back to the config entry."""
        self.hass.config_entries.async_update_entry(
            self._config_entry,
            data={"zones": self.zones, "global_wifi": self.global_wifi},
        )

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    async def async_step_init(self, user_input=None):
        return await self.async_step_manage_menu()

    async def async_step_manage_menu(self, user_input=None):
        """Main management menu."""
        if user_input is not None:
            action = user_input.get("action")
            zone_id = user_input.get("zone_select")

            if action == "add":
                return await self.async_step_add_zone()

            elif action == "edit":
                if not zone_id:
                    return await self.async_step_manage_menu()
                self.zone_to_edit = zone_id
                return await self.async_step_edit_zone()

            elif action == "delete":
                if zone_id and zone_id in self.zones:
                    self.zones.pop(zone_id)
                    self._save()
                    # Reload to remove the switch; abort cleanly afterward
                    await self.hass.config_entries.async_reload(
                        self._config_entry.entry_id
                    )
                    return self.async_abort(reason="reconfigure_successful")
                return await self.async_step_manage_menu()

            elif action in ("edit_wifi", "setup_wifi"):
                return await self.async_step_edit_global_wifi()

            elif action == "done":
                self._save()
                return self.async_abort(reason="reconfigure_successful")

        wifi_configured = bool(self.global_wifi and self.global_wifi.get("entity"))
        wifi_action = "edit_wifi" if wifi_configured else "setup_wifi"

        if self.zones:
            zone_choices = {z_id: z["name"] for z_id, z in self.zones.items()}
            actions = ["add", "edit", "delete", wifi_action, "done"]
            schema = vol.Schema(
                {
                    vol.Required("action"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=actions, translation_key="action"
                        )
                    ),
                    vol.Optional("zone_select"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": k, "label": v}
                                for k, v in zone_choices.items()
                            ]
                        )
                    ),
                }
            )
        else:
            actions = ["add", wifi_action, "done"]
            schema = vol.Schema(
                {
                    vol.Required("action"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=actions, translation_key="action"
                        )
                    ),
                }
            )

        return self.async_show_form(step_id="manage_menu", data_schema=schema)

    async def async_step_edit_global_wifi(self, user_input=None):
        """Edit WiFi settings."""
        if user_input is not None:
            self.global_wifi = {
                "entity": user_input.get(CONF_WIFI_ENTITY),
                "mode":   user_input.get(CONF_WIFI_MODE, "off"),
            }
            self._save()
            return await self.async_step_manage_menu()

        return self.async_show_form(
            step_id="edit_global_wifi",
            data_schema=_wifi_schema(self.global_wifi),
        )

    async def async_step_add_zone(self, user_input=None):
        """Add a new zone."""
        errors: dict[str, str] = {}

        if user_input is not None:
            zone_name = user_input.get(CONF_ZONE_NAME, "").strip()
            if not zone_name:
                errors[CONF_ZONE_NAME] = "zone_name_required"
            else:
                zone_id = zone_name.lower().replace(" ", "_")
                self.zones[zone_id] = {
                    "name": zone_name,
                    CONF_AUTOMATIONS_OFF: user_input.get(CONF_AUTOMATIONS_OFF, []),
                    CONF_AUTOMATIONS_ON:  user_input.get(CONF_AUTOMATIONS_ON,  []),
                    CONF_SCRIPTS_OFF:     user_input.get(CONF_SCRIPTS_OFF,     []),
                    CONF_SCRIPTS_ON:      user_input.get(CONF_SCRIPTS_ON,      []),
                    CONF_ENTITIES_OFF:    user_input.get(CONF_ENTITIES_OFF,    []),
                    CONF_ENTITIES_ON:     user_input.get(CONF_ENTITIES_ON,     []),
                }
                self._save()
                # Reload to create the new switch entity, then close the flow
                await self.hass.config_entries.async_reload(
                    self._config_entry.entry_id
                )
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="add_zone",
            data_schema=_zone_schema(exclude_entities=self._guest_mode_entity_ids()),
            errors=errors,
        )

    async def async_step_edit_zone(self, user_input=None):
        """Edit an existing zone."""
        errors: dict[str, str] = {}
        zone = self.zones[self.zone_to_edit]

        if user_input is not None:
            zone_name = user_input.get(CONF_ZONE_NAME, "").strip()
            if not zone_name:
                errors[CONF_ZONE_NAME] = "zone_name_required"
            else:
                self.zones[self.zone_to_edit] = {
                    "name": zone_name,
                    CONF_AUTOMATIONS_OFF: user_input.get(CONF_AUTOMATIONS_OFF, []),
                    CONF_AUTOMATIONS_ON:  user_input.get(CONF_AUTOMATIONS_ON,  []),
                    CONF_SCRIPTS_OFF:     user_input.get(CONF_SCRIPTS_OFF,     []),
                    CONF_SCRIPTS_ON:      user_input.get(CONF_SCRIPTS_ON,      []),
                    CONF_ENTITIES_OFF:    user_input.get(CONF_ENTITIES_OFF,    []),
                    CONF_ENTITIES_ON:     user_input.get(CONF_ENTITIES_ON,     []),
                }
                self._save()
                # No reload needed for edits — switch will pick up data on next trigger
                return await self.async_step_manage_menu()

        return self.async_show_form(
            step_id="edit_zone",
            data_schema=_zone_schema(zone, exclude_entities=self._guest_mode_entity_ids()),
            errors=errors,
        )