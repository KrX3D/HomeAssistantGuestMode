import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import selector

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_ZONE_NAME = "zone_name"
CONF_AUTOMATIONS_OFF = "automations_off"
CONF_AUTOMATIONS_ON = "automations_on"
CONF_SCRIPTS_OFF = "scripts_off"
CONF_SCRIPTS_ON = "scripts_on"
CONF_ENTITIES_OFF = "entities_off"
CONF_ENTITIES_ON = "entities_on"
CONF_WIFI_ENTITY = "wifi_entity"
CONF_WIFI_MODE = "wifi_mode"


class GuestModeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Guest Mode."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Initial step - Set up global WiFi."""
        if user_input is not None:
            self.global_wifi = {
                "entity": user_input.get(CONF_WIFI_ENTITY),
                "mode": user_input.get(CONF_WIFI_MODE, "off"),
            }
            self.zones = {}
            return await self.async_step_add_zone()

        schema = vol.Schema(
            {
                vol.Optional(CONF_WIFI_ENTITY): selector.EntitySelector(),
                vol.Optional(CONF_WIFI_MODE, default="off"): vol.In(["on", "off"]),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            description_placeholders={"info": "Set up global WiFi (optional)"},
        )

    async def async_step_add_zone(self, user_input=None):
        """Add a zone."""
        if user_input is not None:
            zone_name = user_input[CONF_ZONE_NAME].lower().replace(" ", "_")

            self.zones[zone_name] = {
                "name": user_input[CONF_ZONE_NAME],
                CONF_AUTOMATIONS_OFF: user_input.get(CONF_AUTOMATIONS_OFF, []),
                CONF_AUTOMATIONS_ON: user_input.get(CONF_AUTOMATIONS_ON, []),
                CONF_SCRIPTS_OFF: user_input.get(CONF_SCRIPTS_OFF, []),
                CONF_SCRIPTS_ON: user_input.get(CONF_SCRIPTS_ON, []),
                CONF_ENTITIES_OFF: user_input.get(CONF_ENTITIES_OFF, []),
                CONF_ENTITIES_ON: user_input.get(CONF_ENTITIES_ON, []),
            }

            if user_input.get("add_another"):
                return await self.async_step_add_zone()

            return self.async_create_entry(
                title="Guest Mode",
                data={"zones": self.zones, "global_wifi": self.global_wifi},
            )

        # Get automation and script options
        all_automations = sorted(self.hass.states.async_entity_ids("automation"))
        all_scripts = sorted(self.hass.states.async_entity_ids("script"))
        all_entities = sorted([e for e in self.hass.states.async_entity_ids() 
                              if not e.startswith("automation.") and not e.startswith("script.")])

        schema = vol.Schema(
            {
                vol.Required(CONF_ZONE_NAME): cv.string,
                vol.Optional(CONF_AUTOMATIONS_OFF, default=[]): vol.All(
                    cv.multi_select(all_automations)
                ),
                vol.Optional(CONF_AUTOMATIONS_ON, default=[]): vol.All(
                    cv.multi_select(all_automations)
                ),
                vol.Optional(CONF_SCRIPTS_OFF, default=[]): vol.All(
                    cv.multi_select(all_scripts)
                ),
                vol.Optional(CONF_SCRIPTS_ON, default=[]): vol.All(
                    cv.multi_select(all_scripts)
                ),
                vol.Optional(CONF_ENTITIES_OFF, default=[]): vol.All(
                    cv.multi_select(all_entities)
                ),
                vol.Optional(CONF_ENTITIES_ON, default=[]): vol.All(
                    cv.multi_select(all_entities)
                ),
                vol.Optional("add_another", default=False): cv.boolean,
            }
        )

        return self.async_show_form(step_id="add_zone", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow."""
        return GuestModeOptionsFlow(config_entry)


class GuestModeOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Guest Mode."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config_entry = config_entry
        self.zones = dict(config_entry.data.get("zones", {}))
        self.global_wifi = config_entry.data.get("global_wifi", {})

    async def async_step_init(self, user_input=None):
        """Options step."""
        return await self.async_step_manage_menu()

    async def async_step_manage_menu(self, user_input=None):
        """Main management menu."""
        if user_input is not None:
            action = user_input.get("action")

            if action == "add":
                return await self.async_step_add_zone()
            elif action == "edit":
                self.zone_to_edit = user_input.get("zone_select")
                return await self.async_step_edit_zone()
            elif action == "delete":
                zone_id = user_input.get("zone_select")
                self.zones.pop(zone_id, None)
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={"zones": self.zones, "global_wifi": self.global_wifi},
                )
                return await self.async_step_manage_menu()
            elif action == "edit_wifi":
                return await self.async_step_edit_global_wifi()
            elif action == "done":
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={"zones": self.zones, "global_wifi": self.global_wifi},
                )
                return self.async_abort(reason="reconfigure_successful")

        zone_choices = {
            zone_id: zone["name"] for zone_id, zone in self.zones.items()
        }

        schema = vol.Schema(
            {
                vol.Required("action"): vol.In(["add", "edit", "delete", "edit_wifi", "done"]),
                vol.Optional("zone_select"): vol.In(zone_choices) if zone_choices else cv.string,
            }
        )

        return self.async_show_form(step_id="manage_menu", data_schema=schema)

    async def async_step_edit_global_wifi(self, user_input=None):
        """Edit global WiFi settings."""
        if user_input is not None:
            self.global_wifi = {
                "entity": user_input.get(CONF_WIFI_ENTITY),
                "mode": user_input.get(CONF_WIFI_MODE, "off"),
            }
            return await self.async_step_manage_menu()

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_WIFI_ENTITY, default=self.global_wifi.get("entity")
                ): selector.EntitySelector(),
                vol.Optional(
                    CONF_WIFI_MODE, default=self.global_wifi.get("mode", "off")
                ): vol.In(["on", "off"]),
            }
        )

        return self.async_show_form(step_id="edit_global_wifi", data_schema=schema)

    async def async_step_add_zone(self, user_input=None):
        """Add a new zone."""
        if user_input is not None:
            zone_name = user_input[CONF_ZONE_NAME].lower().replace(" ", "_")

            self.zones[zone_name] = {
                "name": user_input[CONF_ZONE_NAME],
                CONF_AUTOMATIONS_OFF: user_input.get(CONF_AUTOMATIONS_OFF, []),
                CONF_AUTOMATIONS_ON: user_input.get(CONF_AUTOMATIONS_ON, []),
                CONF_SCRIPTS_OFF: user_input.get(CONF_SCRIPTS_OFF, []),
                CONF_SCRIPTS_ON: user_input.get(CONF_SCRIPTS_ON, []),
                CONF_ENTITIES_OFF: user_input.get(CONF_ENTITIES_OFF, []),
                CONF_ENTITIES_ON: user_input.get(CONF_ENTITIES_ON, []),
            }
            return await self.async_step_manage_menu()

        all_automations = sorted(self.hass.states.async_entity_ids("automation"))
        all_scripts = sorted(self.hass.states.async_entity_ids("script"))
        all_entities = sorted([e for e in self.hass.states.async_entity_ids() 
                              if not e.startswith("automation.") and not e.startswith("script.")])

        schema = vol.Schema(
            {
                vol.Required(CONF_ZONE_NAME): cv.string,
                vol.Optional(CONF_AUTOMATIONS_OFF, default=[]): vol.All(
                    cv.multi_select(all_automations)
                ),
                vol.Optional(CONF_AUTOMATIONS_ON, default=[]): vol.All(
                    cv.multi_select(all_automations)
                ),
                vol.Optional(CONF_SCRIPTS_OFF, default=[]): vol.All(
                    cv.multi_select(all_scripts)
                ),
                vol.Optional(CONF_SCRIPTS_ON, default=[]): vol.All(
                    cv.multi_select(all_scripts)
                ),
                vol.Optional(CONF_ENTITIES_OFF, default=[]): vol.All(
                    cv.multi_select(all_entities)
                ),
                vol.Optional(CONF_ENTITIES_ON, default=[]): vol.All(
                    cv.multi_select(all_entities)
                ),
            }
        )

        return self.async_show_form(step_id="add_zone", data_schema=schema)

    async def async_step_edit_zone(self, user_input=None):
        """Edit an existing zone."""
        if user_input is not None:
            zone_id = self.zone_to_edit

            self.zones[zone_id] = {
                "name": user_input[CONF_ZONE_NAME],
                CONF_AUTOMATIONS_OFF: user_input.get(CONF_AUTOMATIONS_OFF, []),
                CONF_AUTOMATIONS_ON: user_input.get(CONF_AUTOMATIONS_ON, []),
                CONF_SCRIPTS_OFF: user_input.get(CONF_SCRIPTS_OFF, []),
                CONF_SCRIPTS_ON: user_input.get(CONF_SCRIPTS_ON, []),
                CONF_ENTITIES_OFF: user_input.get(CONF_ENTITIES_OFF, []),
                CONF_ENTITIES_ON: user_input.get(CONF_ENTITIES_ON, []),
            }
            return await self.async_step_manage_menu()

        zone = self.zones[self.zone_to_edit]

        all_automations = sorted(self.hass.states.async_entity_ids("automation"))
        all_scripts = sorted(self.hass.states.async_entity_ids("script"))
        all_entities = sorted([e for e in self.hass.states.async_entity_ids() 
                              if not e.startswith("automation.") and not e.startswith("script.")])

        schema = vol.Schema(
            {
                vol.Required(CONF_ZONE_NAME, default=zone["name"]): cv.string,
                vol.Optional(
                    CONF_AUTOMATIONS_OFF, default=zone.get(CONF_AUTOMATIONS_OFF, [])
                ): vol.All(cv.multi_select(all_automations)),
                vol.Optional(
                    CONF_AUTOMATIONS_ON, default=zone.get(CONF_AUTOMATIONS_ON, [])
                ): vol.All(cv.multi_select(all_automations)),
                vol.Optional(
                    CONF_SCRIPTS_OFF, default=zone.get(CONF_SCRIPTS_OFF, [])
                ): vol.All(cv.multi_select(all_scripts)),
                vol.Optional(
                    CONF_SCRIPTS_ON, default=zone.get(CONF_SCRIPTS_ON, [])
                ): vol.All(cv.multi_select(all_scripts)),
                vol.Optional(
                    CONF_ENTITIES_OFF, default=zone.get(CONF_ENTITIES_OFF, [])
                ): vol.All(cv.multi_select(all_entities)),
                vol.Optional(
                    CONF_ENTITIES_ON, default=zone.get(CONF_ENTITIES_ON, [])
                ): vol.All(cv.multi_select(all_entities)),
            }
        )

        return self.async_show_form(step_id="edit_zone", data_schema=schema)