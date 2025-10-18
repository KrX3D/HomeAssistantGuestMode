from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import EntitySelector
import voluptuous as vol

DOMAIN = "guest_mode"


class GuestModeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Guest Mode."""

    VERSION = 1

    def __init__(self):
        """Initialize."""
        self.zones: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Initial step."""
        if user_input is not None:
            self.zones = {}
            return await self.async_step_add_zone()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            description_placeholders={"setup": "Click submit to add your first zone"},
        )

    async def async_step_add_zone(self, user_input: dict[str, Any] | None = None):
        """Add a zone."""
        if user_input is not None:
            zone_name = user_input["zone_name"].lower().replace(" ", "_")
            self.zones[zone_name] = {
                "name": user_input["zone_name"],
                "automations": user_input.get("automations", []),
                "scripts": user_input.get("scripts", []),
                "entities": user_input.get("entities", []),
                "wifi_entity": user_input.get("wifi_entity"),
                "wifi_mode": user_input.get("wifi_mode", "off"),
            }

            if user_input.get("add_another"):
                return await self.async_step_add_zone()

            return self.async_create_entry(
                title="Guest Mode",
                data={"zones": self.zones},
            )

        schema = vol.Schema(
            {
                vol.Required("zone_name"): str,
                vol.Optional("automations", default=[]): EntitySelector(),
                vol.Optional("scripts", default=[]): EntitySelector(),
                vol.Optional("entities", default=[]): EntitySelector(),
                vol.Optional("wifi_entity"): EntitySelector(),
                vol.Optional(
                    "wifi_mode", default="off"
                ): vol.In(["on", "off"]),
                vol.Optional("add_another", default=False): bool,
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

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Options step."""
        return await self.async_step_manage_zones()

    async def async_step_manage_zones(self, user_input: dict[str, Any] | None = None):
        """Manage zones."""
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
                    self.config_entry, data={"zones": self.zones}
                )
                return await self.async_step_manage_zones()

            self.hass.config_entries.async_update_entry(
                self.config_entry, data={"zones": self.zones}
            )
            return self.async_abort(reason="reconfigure_successful")

        zone_choices = {
            zone_id: zone["name"] for zone_id, zone in self.zones.items()
        }

        schema = vol.Schema(
            {
                vol.Required("action"): vol.In(["add", "edit", "delete"]),
                vol.Optional("zone_select"): vol.In(zone_choices),
            }
        )

        return self.async_show_form(
            step_id="manage_zones",
            data_schema=schema,
            description_placeholders={
                "zones": f"Configured zones: {', '.join(zone_choices.values()) if zone_choices else 'None'}"
            },
        )

    async def async_step_add_zone(self, user_input: dict[str, Any] | None = None):
        """Add a new zone."""
        if user_input is not None:
            zone_name = user_input["zone_name"].lower().replace(" ", "_")
            self.zones[zone_name] = {
                "name": user_input["zone_name"],
                "automations": user_input.get("automations", []),
                "scripts": user_input.get("scripts", []),
                "entities": user_input.get("entities", []),
                "wifi_entity": user_input.get("wifi_entity"),
                "wifi_mode": user_input.get("wifi_mode", "off"),
            }
            return await self.async_step_manage_zones()

        schema = vol.Schema(
            {
                vol.Required("zone_name"): str,
                vol.Optional("automations", default=[]): EntitySelector(),
                vol.Optional("scripts", default=[]): EntitySelector(),
                vol.Optional("entities", default=[]): EntitySelector(),
                vol.Optional("wifi_entity"): EntitySelector(),
                vol.Optional(
                    "wifi_mode", default="off"
                ): vol.In(["on", "off"]),
            }
        )

        return self.async_show_form(step_id="add_zone", data_schema=schema)

    async def async_step_edit_zone(self, user_input: dict[str, Any] | None = None):
        """Edit an existing zone."""
        if user_input is not None:
            zone_id = self.zone_to_edit
            self.zones[zone_id] = {
                "name": user_input["zone_name"],
                "automations": user_input.get("automations", []),
                "scripts": user_input.get("scripts", []),
                "entities": user_input.get("entities", []),
                "wifi_entity": user_input.get("wifi_entity"),
                "wifi_mode": user_input.get("wifi_mode", "off"),
            }
            return await self.async_step_manage_zones()

        zone = self.zones[self.zone_to_edit]

        schema = vol.Schema(
            {
                vol.Required("zone_name", default=zone["name"]): str,
                vol.Optional(
                    "automations", default=zone.get("automations", [])
                ): EntitySelector(),
                vol.Optional(
                    "scripts", default=zone.get("scripts", [])
                ): EntitySelector(),
                vol.Optional("entities", default=zone.get("entities", [])): EntitySelector(),
                vol.Optional(
                    "wifi_entity", default=zone.get("wifi_entity")
                ): EntitySelector(),
                vol.Optional(
                    "wifi_mode", default=zone.get("wifi_mode", "off")
                ): vol.In(["on", "off"]),
            }
        )

        return self.async_show_form(step_id="edit_zone", data_schema=schema)