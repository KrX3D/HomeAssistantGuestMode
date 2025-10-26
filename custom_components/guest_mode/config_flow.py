import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import selector
from homeassistant.helpers.entity_registry import async_get as entity_registry_async_get

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
        """Main setup menu (initial step)."""
        # Temporary storage while configuring
        if not hasattr(self, "zones"):
            self.zones = {}
        if not hasattr(self, "global_wifi"):
            self.global_wifi = {}

        if user_input is not None:
            action = user_input.get("action")
            if action == "setup":  # add / setup first zone
                return await self.async_step_add_zone()
            if action == "setup_wifi":  # configure global Wi-Fi
                return await self.async_step_setup_wifi()
            if action == "done":
                # Finish and create entry with whatever has been configured so far
                return self.async_create_entry(
                    title="Guest Mode",
                    data={"zones": self.zones, "global_wifi": self.global_wifi},
                )

        # Show main menu with three actions: setup (zone), setup_wifi, done
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In(
                        ["setup", "setup_wifi", "done"]
                    )
                }
            ),
            description_placeholders={
                "info": "Create zones and optionally configure WiFi. Use 'Done' when finished."
            },
        )

    async def async_step_add_zone(self, user_input=None):
        """Add a zone (sub-step). Return to main menu after OK."""
        if user_input is not None:
            zone_name = user_input.get(CONF_ZONE_NAME, "").lower().replace(" ", "_")
            if not zone_name:
                # redisplay form (validation)
                return await self.async_step_add_zone()

            self.zones[zone_name] = {
                "name": user_input.get(CONF_ZONE_NAME, ""),
                CONF_AUTOMATIONS_OFF: user_input.get(CONF_AUTOMATIONS_OFF, []),
                CONF_AUTOMATIONS_ON: user_input.get(CONF_AUTOMATIONS_ON, []),
                CONF_SCRIPTS_OFF: user_input.get(CONF_SCRIPTS_OFF, []),
                CONF_SCRIPTS_ON: user_input.get(CONF_SCRIPTS_ON, []),
                CONF_ENTITIES_OFF: user_input.get(CONF_ENTITIES_OFF, []),
                CONF_ENTITIES_ON: user_input.get(CONF_ENTITIES_ON, []),
            }

            if user_input.get("add_another"):
                # Let user add more zones immediately
                return await self.async_step_add_zone()

            # Return to main menu after adding zone
            return await self.async_step_user()

        # Build available entity lists with friendly names (cached for efficiency)
        automation_options = {}
        for entity_id in sorted(self.hass.states.async_entity_ids("automation")):
            state = self.hass.states.get(entity_id)
            friendly_name = state.attributes.get("friendly_name", entity_id) if state else entity_id
            automation_options[entity_id] = friendly_name

        script_options = {}
        for entity_id in sorted(self.hass.states.async_entity_ids("script")):
            state = self.hass.states.get(entity_id)
            friendly_name = state.attributes.get("friendly_name", entity_id) if state else entity_id
            script_options[entity_id] = friendly_name

        entity_options = {}
        for entity_id in sorted(self.hass.states.async_entity_ids()):
            if not entity_id.startswith("automation.") and not entity_id.startswith("script."):
                state = self.hass.states.get(entity_id)
                friendly_name = state.attributes.get("friendly_name", entity_id) if state else entity_id
                entity_options[entity_id] = friendly_name

        schema = vol.Schema(
            {
                vol.Required(CONF_ZONE_NAME): cv.string,
                vol.Optional(CONF_AUTOMATIONS_OFF, default=[]): vol.All(
                    cv.multi_select(automation_options)
                )
                if automation_options
                else cv.string,
                vol.Optional(CONF_AUTOMATIONS_ON, default=[]): vol.All(
                    cv.multi_select(automation_options)
                )
                if automation_options
                else cv.string,
                vol.Optional(CONF_SCRIPTS_OFF, default=[]): vol.All(
                    cv.multi_select(script_options)
                )
                if script_options
                else cv.string,
                vol.Optional(CONF_SCRIPTS_ON, default=[]): vol.All(
                    cv.multi_select(script_options)
                )
                if script_options
                else cv.string,
                vol.Optional(CONF_ENTITIES_OFF, default=[]): vol.All(
                    cv.multi_select(entity_options)
                )
                if entity_options
                else cv.string,
                vol.Optional(CONF_ENTITIES_ON, default=[]): vol.All(
                    cv.multi_select(entity_options)
                )
                if entity_options
                else cv.string,
                vol.Optional("add_another", default=False): cv.boolean,
            }
        )

        return self.async_show_form(step_id="add_zone", data_schema=schema)

    async def async_step_setup_wifi(self, user_input=None):
        """Set up global WiFi (sub-step). Return to main menu after OK."""
        if user_input is not None:
            self.global_wifi = {
                "entity": user_input.get(CONF_WIFI_ENTITY),
                "mode": user_input.get(CONF_WIFI_MODE, "off"),
            }
            # Return to main menu after configuring WiFi
            return await self.async_step_user()

        schema = vol.Schema(
            {
                vol.Optional(CONF_WIFI_ENTITY): selector.EntitySelector(),
                vol.Optional(CONF_WIFI_MODE, default="off"): vol.In(["on", "off"]),
            }
        )

        return self.async_show_form(
            step_id="setup_wifi",
            data_schema=schema,
            description_placeholders={
                "setup": "Configure global WiFi settings (optional). Click OK to return to the main menu."
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow."""
        return GuestModeOptionsFlow(config_entry)


class GuestModeOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Guest Mode."""

    def __init__(self, config_entry):
        """Initialize."""
        self._config_entry = config_entry
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
                zone_id = user_input.get("zone_select")
                if zone_id:
                    self.zone_to_edit = zone_id
                    return await self.async_step_edit_zone()
                else:
                    # Re-show menu if no zone selected
                    return await self.async_step_manage_menu()
            elif action == "delete":
                zone_id = user_input.get("zone_select")
                if zone_id:
                    await self._delete_zone(zone_id)
                    self.zones.pop(zone_id, None)
                    self.hass.config_entries.async_update_entry(
                        self._config_entry,
                        data={"zones": self.zones, "global_wifi": self.global_wifi},
                    )
                    # Reload to remove the switch entity
                    await self.hass.config_entries.async_reload(self._config_entry.entry_id)
                return await self.async_step_manage_menu()
            elif action == "edit_wifi" or action == "setup_wifi":
                return await self.async_step_edit_global_wifi()
            elif action == "done":
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data={"zones": self.zones, "global_wifi": self.global_wifi},
                )
                return self.async_abort(reason="reconfigure_successful")

        zone_choices = {
            zone_id: zone["name"] for zone_id, zone in self.zones.items()
        }

        # Build schema based on available zones
        schema_dict = {}

        if self.zones:
            # Check if WiFi is configured
            wifi_configured = bool(self.global_wifi and self.global_wifi.get("entity"))
            wifi_action = "edit_wifi" if wifi_configured else "setup_wifi"
            actions = ["add", "edit", "delete", wifi_action, "done"]
            schema_dict[vol.Required("action")] = vol.In(actions)
            schema_dict[vol.Required("zone_select")] = vol.In(zone_choices)
        else:
            # Check if WiFi is configured
            wifi_configured = bool(self.global_wifi and self.global_wifi.get("entity"))
            wifi_action = "edit_wifi" if wifi_configured else "setup_wifi"
            actions = ["add", wifi_action, "done"]
            schema_dict[vol.Required("action")] = vol.In(actions)

        schema = vol.Schema(schema_dict)

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
            self.hass.config_entries.async_update_entry(
                self._config_entry,
                data={"zones": self.zones, "global_wifi": self.global_wifi},
            )
            # Reload the config entry to create new switch entities
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return await self.async_step_manage_menu()

        # Build entity options with friendly names
        automation_options = {}
        for entity_id in sorted(self.hass.states.async_entity_ids("automation")):
            state = self.hass.states.get(entity_id)
            friendly_name = state.attributes.get("friendly_name", entity_id) if state else entity_id
            automation_options[entity_id] = friendly_name

        script_options = {}
        for entity_id in sorted(self.hass.states.async_entity_ids("script")):
            state = self.hass.states.get(entity_id)
            friendly_name = state.attributes.get("friendly_name", entity_id) if state else entity_id
            script_options[entity_id] = friendly_name

        entity_options = {}
        for entity_id in sorted(self.hass.states.async_entity_ids()):
            if not entity_id.startswith("automation.") and not entity_id.startswith("script."):
                state = self.hass.states.get(entity_id)
                friendly_name = state.attributes.get("friendly_name", entity_id) if state else entity_id
                entity_options[entity_id] = friendly_name

        schema = vol.Schema(
            {
                vol.Required(CONF_ZONE_NAME): cv.string,
                vol.Optional(CONF_AUTOMATIONS_OFF, default=[]): vol.All(
                    cv.multi_select(automation_options)
                ),
                vol.Optional(CONF_AUTOMATIONS_ON, default=[]): vol.All(
                    cv.multi_select(automation_options)
                ),
                vol.Optional(CONF_SCRIPTS_OFF, default=[]): vol.All(
                    cv.multi_select(script_options)
                ),
                vol.Optional(CONF_SCRIPTS_ON, default=[]): vol.All(
                    cv.multi_select(script_options)
                ),
                vol.Optional(CONF_ENTITIES_OFF, default=[]): vol.All(
                    cv.multi_select(entity_options)
                ),
                vol.Optional(CONF_ENTITIES_ON, default=[]): vol.All(
                    cv.multi_select(entity_options)
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
            self.hass.config_entries.async_update_entry(
                self._config_entry,
                data={"zones": self.zones, "global_wifi": self.global_wifi},
            )
            # Reload to update the switch entity
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return await self.async_step_manage_menu()

        zone = self.zones[self.zone_to_edit]

        all_automations = sorted(self.hass.states.async_entity_ids("automation"))
        all_scripts = sorted(self.hass.states.async_entity_ids("script"))
        all_entities = sorted(
            [
                e
                for e in self.hass.states.async_entity_ids()
                if not e.startswith("automation.") and not e.startswith("script.")
            ]
        )

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

    async def _delete_zone(self, zone_id):
        """Delete zone and its associated entities."""
        try:
            entity_registry = entity_registry_async_get(self.hass)

            # Remove the zone switch entity - correct entity ID format
            zone_switch_id = f"switch.guest_mode_{zone_id}"

            # Find and remove from entity registry
            for entity_id in list(entity_registry.entities.keys()):
                if entity_id == zone_switch_id:
                    _LOGGER.debug(f"Removing entity from registry: {entity_id}")
                    entity_registry.async_remove(entity_id)
                    break

            # Also remove the state
            if self.hass.states.get(zone_switch_id):
                self.hass.states.async_remove(zone_switch_id)
                _LOGGER.debug(f"Removed state: {zone_switch_id}")

        except Exception as e:
            _LOGGER.error(f"Error deleting zone entities: {e}")