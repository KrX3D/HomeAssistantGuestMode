"""Constants for Guest Mode integration."""

DOMAIN = "guest_mode"

CONF_ZONE_NAME = "zone_name"
CONF_AUTOMATIONS_OFF = "automations_off"
CONF_AUTOMATIONS_ON = "automations_on"
CONF_SCRIPTS_OFF = "scripts_off"
CONF_SCRIPTS_ON = "scripts_on"
CONF_ENTITIES_OFF = "entities_off"
CONF_ENTITIES_ON = "entities_on"
CONF_AUTO_OFF_HOURS = "auto_off_hours"
CONF_UPDATE_ENTITY_ID = "update_entity_id"
CONF_WIFI_ENTITY = "wifi_entity"
CONF_WIFI_MODE = "wifi_mode"

# Order matters: this is the order in which zone changes are applied.
ZONE_LIST_KEYS = (
    CONF_AUTOMATIONS_OFF,
    CONF_AUTOMATIONS_ON,
    CONF_SCRIPTS_OFF,
    CONF_SCRIPTS_ON,
    CONF_ENTITIES_OFF,
    CONF_ENTITIES_ON,
)

SERVICE_RESTORE_ZONE_STATES = "restore_zone_states"

STORAGE_VERSION = 1
