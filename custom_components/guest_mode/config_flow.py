def _get_automation_options(self):
        """Get automation options."""
        return [
            {"value": entity_id, "label": entity_id}
            for entity_id in self.hass.states.async_entity_ids("automation")
        ]

    def _get_script_options(self):
        """Get script options."""
        return [
            {"value": entity_id, "label": entity_id}
            for entity_id in self.hass.states.async_entity_ids("script")
        ]

    def _get_entity_options(self):
        """Get all entity options."""
        excluded_domains = ["automation", "script"]
        all_entities = []
        for entity_id in self.hass.states.async_entity_ids():
            domain = entity_id.split(".")[0]
            if domain not in excluded_domains:
                all_entities.append({"value": entity_id, "label": entity_id})
        return all_entitiesfrom homeassistant import config_entries
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import EntitySelector
import voluptuous as vol

DOMAIN = "guest_mode"


class GuestModeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Guest Mode."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Initial step."""
        if user_input is not None:
            self.zones = {}
            self.global_wifi = {"entity": None, "mode": "off"}
            return await self.async_step_set_global_wifi()

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    async def async_step_set_global_wifi(self, user_input=None):
        """Set global WiFi settings."""
        if user_input is not None:
            wifi_entity = user_input.get("wifi_entity")
            self.global_wifi = {
                "entity": wifi_entity if wifi_entity else None,
                "mode": user_input.get("wifi_mode", "off"),
            }
            return await self.async_step_add_first_zone()

        schema = vol.Schema(
            {
                vol.Optional("wifi_entity"): EntitySelector(),
                vol.Optional("wifi_mode", default="off"): vol.In(["on", "off"]),
            }
        )

        return self.async_show_form(
            step_id="set_global_wifi",
            data_schema=schema,
            description_placeholders={"info": "Configure WiFi settings (optional)"},
        )

    async def async_step_add_first_zone(self, user_input=None):
        """Add first zone."""
        if user_input is not None:
            zone_name = user_input["zone_name"].lower().replace(" ", "_")

            self.zones[zone_name] = {
                "name": user_input["zone_name"],
                "automations_off": user_input.get("automations_off", []),
                "automations_on": user_input.get("automations_on", []),
                "scripts_off": user_input.get("scripts_off", []),
                "scripts_on": user_input.get("scripts_on", []),
                "entities_off": user_input.get("entities_off", []),
                "entities_on": user_input.get("entities_on", []),
            }

            return self.async_create_entry(
                title="Guest Mode",
                data={"zones": self.zones, "global_wifi": self.global_wifi},
            )

        schema = vol.Schema(
            {
                vol.Required("zone_name"): str,
                vol.Optional("automations_off", default=[]): vol.All(
                    cv.ensure_list, [str]
                ),
                vol.Optional("automations_on", default=[]): vol.All(
                    cv.ensure_list, [str]
                ),
                vol.Optional("scripts_off", default=[]): vol.All(
                    cv.ensure_list, [str]
                ),
                vol.Optional("scripts_on", default=[]): vol.All(
                    cv.ensure_list, [str]
                ),
                vol.Optional("entities_off", default=[]): vol.All(
                    cv.ensure_list, [str]
                ),
                vol.Optional("entities_on", default=[]): vol.All(
                    cv.ensure_list, [str]
                ),
            }
        )

        return self.async_show_form(step_id="add_first_zone", data_schema=schema)

    def _get_automation_options(self):
        """Get automation options."""
        return [
            {"value": entity_id, "label": entity_id}
            for entity_id in self.hass.states.async_entity_ids("automation")
        ]

    def _get_script_options(self):
        """Get script options."""
        return [
            {"value": entity_id, "label": entity_id}
            for entity_id in self.hass.states.async_entity_ids("script")
        ]

    def _get_entity_options(self):
        """Get all entity options."""
        excluded_domains = ["automation", "script"]
        all_entities = []
        for entity_id in self.hass.states.async_entity_ids():
            domain = entity_id.split(".")[0]
            if domain not in excluded_domains:
                all_entities.append({"value": entity_id, "label": entity_id})
        return all_entities


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
                    self.config_entry, data={"zones": self.zones, "global_wifi": self.global_wifi}
                )
                return await self.async_step_manage_menu()
            elif action == "edit_wifi":
                return await self.async_step_edit_global_wifi()
            elif action == "done":
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data={"zones": self.zones, "global_wifi": self.global_wifi}
                )
                return self.async_abort(reason="reconfigure_successful")

        zone_choices = {
            zone_id: zone["name"] for zone_id, zone in self.zones.items()
        }

        schema = vol.Schema(
            {
                vol.Required("action"): vol.In(["add", "edit", "delete", "edit_wifi", "done"]),
                vol.Optional("zone_select"): vol.In(zone_choices) if zone_choices else None,
            }
        )

        return self.async_show_form(step_id="manage_menu", data_schema=schema)

    async def async_step_edit_global_wifi(self, user_input=None):
        """Edit global WiFi settings."""
        if user_input is not None:
            wifi_entity = user_input.get("wifi_entity")
            self.global_wifi = {
                "entity": wifi_entity if wifi_entity else None,
                "mode": user_input.get("wifi_mode", "off"),
            }
            return await self.async_step_manage_menu()

        schema = vol.Schema(
            {
                vol.Optional("wifi_entity", default=self.global_wifi.get("entity")): EntitySelector(),
                vol.Optional("wifi_mode", default=self.global_wifi.get("mode", "off")): vol.In(["on", "off"]),
            }
        )

        return self.async_show_form(step_id="edit_global_wifi", data_schema=schema)

    async def async_step_add_zone(self, user_input=None):
        """Add a new zone."""
        if user_input is not None:
            zone_name = user_input["zone_name"].lower().replace(" ", "_")

            self.zones[zone_name] = {
                "name": user_input["zone_name"],
                "automations_off": user_input.get("automations_off", []),
                "automations_on": user_input.get("automations_on", []),
                "scripts_off": user_input.get("scripts_off", []),
                "scripts_on": user_input.get("scripts_on", []),
                "entities_off": user_input.get("entities_off", []),
                "entities_on": user_input.get("entities_on", []),
            }
            return await self.async_step_manage_menu()

        schema = vol.Schema(
            {
                vol.Required("zone_name"): str,
                vol.Optional("automations_off", default=[]): vol.All(
                    cv.ensure_list, [str]
                ),
                vol.Optional("automations_on", default=[]): vol.All(
                    cv.ensure_list, [str]
                ),
                vol.Optional("scripts_off", default=[]): vol.All(
                    cv.ensure_list, [str]
                ),
                vol.Optional("scripts_on", default=[]): vol.All(
                    cv.ensure_list, [str]
                ),
                vol.Optional("entities_off", default=[]): vol.All(
                    cv.ensure_list, [str]
                ),
                vol.Optional("entities_on", default=[]): vol.All(
                    cv.ensure_list, [str]
                ),
            }
        )

        return self.async_show_form(step_id="add_zone", data_schema=schema)

    async def async_step_edit_zone(self, user_input=None):
        """Edit an existing zone."""
        if user_input is not None:
            zone_id = self.zone_to_edit

            self.zones[zone_id] = {
                "name": user_input["zone_name"],
                "automations_off": user_input.get("automations_off", []),
                "automations_on": user_input.get("automations_on", []),
                "scripts_off": user_input.get("scripts_off", []),
                "scripts_on": user_input.get("scripts_on", []),
                "entities_off": user_input.get("entities_off", []),
                "entities_on": user_input.get("entities_on", []),
            }
            return await self.async_step_manage_menu()

        zone = self.zones[self.zone_to_edit]

        schema = vol.Schema(
            {
                vol.Required("zone_name", default=zone["name"]): str,
                vol.Optional("automations_off", default=zone.get("automations_off", [])): vol.All(
                    cv.ensure_list, [str]
                ),
                vol.Optional("automations_on", default=zone.get("automations_on", [])): vol.All(
                    cv.ensure_list, [str]
                ),
                vol.Optional("scripts_off", default=zone.get("scripts_off", [])): vol.All(
                    cv.ensure_list, [str]
                ),
                vol.Optional("scripts_on", default=zone.get("scripts_on", [])): vol.All(
                    cv.ensure_list, [str]
                ),
                vol.Optional("entities_off", default=zone.get("entities_off", [])): vol.All(
                    cv.ensure_list, [str]
                ),
                vol.Optional("entities_on", default=zone.get("entities_on", [])): vol.All(
                    cv.ensure_list, [str]
                ),
            }
        )

        return self.async_show_form(step_id="edit_zone", data_schema=schema)

    def _get_automation_options(self):
        """Get automation options."""
        return [
            {"value": entity_id, "label": entity_id}
            for entity_id in self.hass.states.async_entity_ids("automation")
        ]

    def _get_script_options(self):
        """Get script options."""
        return [
            {"value": entity_id, "label": entity_id}
            for entity_id in self.hass.states.async_entity_ids("script")
        ]

    def _get_entity_options(self):
        """Get all entity options."""
        excluded_domains = ["automation", "script"]
        all_entities = []
        for entity_id in self.hass.states.async_entity_ids():
            domain = entity_id.split(".")[0]
            if domain not in excluded_domains:
                all_entities.append({"value": entity_id, "label": entity_id})
        return all_entities