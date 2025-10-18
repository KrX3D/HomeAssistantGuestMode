from homeassistant import config_entries
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
            return await self.async_step_setup_menu()

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    async def async_step_setup_menu(self, user_input=None):
        """Main setup menu - choose to add zone or global wifi."""
        if user_input is not None:
            action = user_input.get("action")

            if action == "add_zone":
                return await self.async_step_add_zone()
            elif action == "set_wifi":
                return await self.async_step_set_global_wifi()
            elif action == "done":
                return self.async_create_entry(
                    title="Guest Mode",
                    data={"zones": self.zones, "global_wifi": getattr(self, "global_wifi", None)},
                )

        schema = vol.Schema(
            {
                vol.Required("action"): vol.In(["add_zone", "set_wifi", "done"]),
            }
        )

        return self.async_show_form(
            step_id="setup_menu",
            data_schema=schema,
            description_placeholders={
                "zones": f"Zones configured: {len(self.zones)}"
            },
        )

    async def async_step_set_global_wifi(self, user_input=None):
        """Set global WiFi settings."""
        if user_input is not None:
            self.global_wifi = {
                "entity": user_input.get("wifi_entity"),
                "mode": user_input.get("wifi_mode", "off"),
            }
            return await self.async_step_setup_menu()

        schema = vol.Schema(
            {
                vol.Optional("wifi_entity"): EntitySelector(),
                vol.Optional("wifi_mode", default="off"): vol.In(["on", "off"]),
            }
        )

        return self.async_show_form(step_id="set_global_wifi", data_schema=schema)

    async def async_step_add_zone(self, user_input=None):
        """Add a zone."""
        if user_input is not None:
            if not hasattr(self, "zones"):
                self.zones = {}

            zone_name = user_input["zone_name"].lower().replace(" ", "_")
            
            automations = user_input.get("automations")
            if isinstance(automations, str):
                automations = [automations] if automations else []
            
            scripts = user_input.get("scripts")
            if isinstance(scripts, str):
                scripts = [scripts] if scripts else []
            
            entities = user_input.get("entities")
            if isinstance(entities, str):
                entities = [entities] if entities else []

            self.zones[zone_name] = {
                "name": user_input["zone_name"],
                "automations": automations or [],
                "scripts": scripts or [],
                "entities": entities or [],
            }

            return await self.async_step_setup_menu()

        schema = vol.Schema(
            {
                vol.Required("zone_name"): str,
                vol.Optional("automations"): EntitySelector(),
                vol.Optional("scripts"): EntitySelector(),
                vol.Optional("entities"): EntitySelector(),
            }
        )

        return self.async_show_form(step_id="add_zone", data_schema=schema)


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
                vol.Optional("zone_select"): vol.In(zone_choices),
            }
        )

        return self.async_show_form(step_id="manage_menu", data_schema=schema)

    async def async_step_edit_global_wifi(self, user_input=None):
        """Edit global WiFi settings."""
        if user_input is not None:
            self.global_wifi = {
                "entity": user_input.get("wifi_entity"),
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
            
            automations = user_input.get("automations")
            if isinstance(automations, str):
                automations = [automations] if automations else []
            
            scripts = user_input.get("scripts")
            if isinstance(scripts, str):
                scripts = [scripts] if scripts else []
            
            entities = user_input.get("entities")
            if isinstance(entities, str):
                entities = [entities] if entities else []

            self.zones[zone_name] = {
                "name": user_input["zone_name"],
                "automations": automations or [],
                "scripts": scripts or [],
                "entities": entities or [],
            }
            return await self.async_step_manage_menu()

        schema = vol.Schema(
            {
                vol.Required("zone_name"): str,
                vol.Optional("automations"): EntitySelector(),
                vol.Optional("scripts"): EntitySelector(),
                vol.Optional("entities"): EntitySelector(),
            }
        )

        return self.async_show_form(step_id="add_zone", data_schema=schema)

    async def async_step_edit_zone(self, user_input=None):
        """Edit an existing zone."""
        if user_input is not None:
            zone_id = self.zone_to_edit
            
            automations = user_input.get("automations")
            if isinstance(automations, str):
                automations = [automations] if automations else []
            
            scripts = user_input.get("scripts")
            if isinstance(scripts, str):
                scripts = [scripts] if scripts else []
            
            entities = user_input.get("entities")
            if isinstance(entities, str):
                entities = [entities] if entities else []

            self.zones[zone_id] = {
                "name": user_input["zone_name"],
                "automations": automations or [],
                "scripts": scripts or [],
                "entities": entities or [],
            }
            return await self.async_step_manage_menu()

        zone = self.zones[self.zone_to_edit]

        schema = vol.Schema(
            {
                vol.Required("zone_name", default=zone["name"]): str,
                vol.Optional("automations", default=zone.get("automations", [])): EntitySelector(),
                vol.Optional("scripts", default=zone.get("scripts", [])): EntitySelector(),
                vol.Optional("entities", default=zone.get("entities", [])): EntitySelector(),
            }
        )

        return self.async_show_form(step_id="edit_zone", data_schema=schema)