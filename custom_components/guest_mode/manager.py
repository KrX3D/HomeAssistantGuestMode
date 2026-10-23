"""Runtime state and logic shared by all Guest Mode switches."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUTO_OFF_HOURS,
    CONF_AUTOMATIONS_OFF,
    CONF_AUTOMATIONS_ON,
    CONF_ENTITIES_OFF,
    CONF_ENTITIES_ON,
    CONF_SCRIPTS_OFF,
    CONF_SCRIPTS_ON,
    DOMAIN,
    ZONE_LIST_KEYS,
)

_LOGGER = logging.getLogger(__name__)

# Domains that are restored with a plain turn_on / turn_off. Everything else
# (lights, climate, covers, media players, ...) is restored with scene.apply so
# brightness, setpoints, positions etc. come back too.
SIMPLE_DOMAINS = {"automation", "script", "switch", "input_boolean"}


def _normalize_records(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Upgrade records saved by older versions (zone -> {entity: "on"})."""
    records: dict[str, dict[str, Any]] = {}
    for zone_id, value in raw.items():
        if isinstance(value, dict) and isinstance(value.get("entities"), dict):
            records[zone_id] = value
            continue
        records[zone_id] = {
            "entities": {
                entity_id: {"state": state, "attributes": {}}
                for entity_id, state in (value or {}).items()
            },
            "since": None,
            "until": None,
        }
    return records


class GuestModeManager:
    """Owns the active-zone records and applies / reverts zone changes.

    A zone is "on" exactly when it has a record here. The records are persisted,
    so the on/off state of every zone survives restarts and reloads.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, store: Store) -> None:
        self.hass = hass
        self.entry = entry
        self._store = store
        self._records: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._timers: dict[str, CALLBACK_TYPE] = {}

    async def async_load(self) -> None:
        self._records = _normalize_records(await self._store.async_load() or {})

    # ------------------------------------------------------------------
    # Properties / queries
    # ------------------------------------------------------------------

    @property
    def signal(self) -> str:
        return f"{DOMAIN}_update_{self.entry.entry_id}"

    @property
    def zones(self) -> dict[str, dict[str, Any]]:
        return self.entry.data.get("zones", {})

    @property
    def active_zone_ids(self) -> list[str]:
        return [z for z in self.zones if z in self._records]

    def is_active(self, zone_id: str) -> bool:
        return zone_id in self._records

    def record(self, zone_id: str) -> dict[str, Any] | None:
        return self._records.get(zone_id)

    @callback
    def _notify(self) -> None:
        async_dispatcher_send(self.hass, self.signal)

    async def _async_save(self) -> None:
        await self._store.async_save(self._records)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def async_start(self) -> CALLBACK_TYPE | None:
        """Run start-up housekeeping once Home Assistant has fully started."""
        return async_at_started(self.hass, self._async_started)

    async def _async_started(self, hass: HomeAssistant) -> None:
        self._cleanup_issues()
        # Zones deleted while active: put everything back the way it was.
        for zone_id in [z for z in self._records if z not in self.zones]:
            await self.async_deactivate_zone(zone_id)
        now = dt_util.utcnow()
        for zone_id, record in list(self._records.items()):
            until = dt_util.parse_datetime(record["until"]) if record.get("until") else None
            if until and until <= now:
                await self.async_deactivate_zone(zone_id)
            else:
                self._arm_timer(zone_id)
        for zone_id, zone in self.zones.items():
            _, missing = self.resolve(zone)
            self._update_issue(zone_id, zone, missing)

    @callback
    def async_stop(self) -> None:
        for cancel in self._timers.values():
            cancel()
        self._timers.clear()

    # ------------------------------------------------------------------
    # Public actions
    # ------------------------------------------------------------------

    async def async_activate_zone(self, zone_id: str) -> None:
        async with self._lock:
            zone = self.zones.get(zone_id)
            # Already active: do nothing, otherwise the saved *original* states
            # would be overwritten with the guest-mode ones.
            if zone is None or zone_id in self._records:
                return

            valid, missing = self.resolve(zone)
            self._update_issue(zone_id, zone, missing)
            if missing:
                _LOGGER.warning(
                    "Zone '%s': %d configured entities no longer exist and were skipped",
                    zone["name"], len(missing),
                )

            saved: dict[str, dict[str, Any]] = {}
            for key in ZONE_LIST_KEYS:
                for entity_id in valid[key]:
                    state = self.hass.states.get(entity_id)
                    if state and entity_id not in saved:
                        saved[entity_id] = {
                            "state": state.state,
                            "attributes": (
                                {}
                                if entity_id.split(".", 1)[0] in SIMPLE_DOMAINS
                                else dict(state.attributes)
                            ),
                        }

            now = dt_util.utcnow()
            hours = float(zone.get(CONF_AUTO_OFF_HOURS) or 0)
            self._records[zone_id] = {
                "entities": saved,
                "since": now.isoformat(),
                "until": (now + timedelta(hours=hours)).isoformat() if hours > 0 else None,
            }
            await self._async_save()
            self._notify()

            for key, domain, service in (
                (CONF_AUTOMATIONS_OFF, "automation", "turn_off"),
                (CONF_AUTOMATIONS_ON, "automation", "turn_on"),
                (CONF_SCRIPTS_OFF, "script", "turn_off"),
                (CONF_SCRIPTS_ON, "script", "turn_on"),
                (CONF_ENTITIES_OFF, "homeassistant", "turn_off"),
                (CONF_ENTITIES_ON, "homeassistant", "turn_on"),
            ):
                for entity_id in valid[key]:
                    await self._call(domain, service, {"entity_id": entity_id})

            if len(self._records) == 1:
                await self._apply_wifi(guest_active=True)

            self._arm_timer(zone_id)
            self._notify()

    async def async_deactivate_zone(self, zone_id: str) -> None:
        async with self._lock:
            record = self._records.pop(zone_id, None)
            if record is None:
                return
            self._cancel_timer(zone_id)
            await self._async_save()
            self._notify()

            await self._restore(record["entities"])

            if not self._records:
                await self._apply_wifi(guest_active=False)
            self._notify()

    async def async_activate_all(self) -> None:
        for zone_id in list(self.zones):
            await self.async_activate_zone(zone_id)

    async def async_deactivate_all(self) -> None:
        for zone_id in list(self._records):
            await self.async_deactivate_zone(zone_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def resolve(self, zone: dict[str, Any]) -> tuple[dict[str, list[str]], list[str]]:
        """Split a zone's configured entities into (existing, missing).

        Guest Mode's own entities are skipped so a zone can never switch itself.
        """
        registry = er.async_get(self.hass)
        valid: dict[str, list[str]] = {}
        missing: list[str] = []
        for key in ZONE_LIST_KEYS:
            valid[key] = []
            for entity_id in dict.fromkeys(zone.get(key, [])):
                reg_entry = registry.async_get(entity_id)
                if reg_entry and reg_entry.platform == DOMAIN:
                    continue
                if self.hass.states.get(entity_id):
                    valid[key].append(entity_id)
                else:
                    missing.append(entity_id)
        return valid, missing

    async def _call(self, domain: str, service: str, data: dict[str, Any]) -> None:
        """Call a service; one failing entity must not abort the whole zone."""
        try:
            await self.hass.services.async_call(domain, service, data, blocking=True)
        except HomeAssistantError as err:
            _LOGGER.warning("Calling %s.%s with %s failed: %s", domain, service, data, err)

    async def _restore(self, saved: dict[str, Any]) -> None:
        rich: dict[str, dict[str, Any]] = {}
        for entity_id, rec in saved.items():
            if isinstance(rec, str):
                rec = {"state": rec, "attributes": {}}
            state = rec["state"]
            if state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                continue
            domain = entity_id.split(".", 1)[0]
            if domain in SIMPLE_DOMAINS:
                if state not in ("on", "off"):
                    continue
                svc_domain = domain if domain in ("automation", "script") else "homeassistant"
                await self._call(
                    svc_domain,
                    "turn_on" if state == "on" else "turn_off",
                    {"entity_id": entity_id},
                )
            elif self.hass.states.get(entity_id):
                rich[entity_id] = {**rec.get("attributes", {}), "state": state}
        if rich:
            await self._call("scene", "apply", {"entities": rich})

    async def _apply_wifi(self, *, guest_active: bool) -> None:
        """Set the WiFi entity to the configured state (or its inverse on deactivation)."""
        global_wifi = self.entry.data.get("global_wifi", {})
        wifi_entity = global_wifi.get("entity")
        if not wifi_entity:
            return
        if not self.hass.states.get(wifi_entity):
            _LOGGER.warning("Configured WiFi entity '%s' no longer exists", wifi_entity)
            return

        wifi_on_when_guest = global_wifi.get("mode", "off") == "on"
        turn_on = wifi_on_when_guest if guest_active else not wifi_on_when_guest
        await self._call(
            "homeassistant", "turn_on" if turn_on else "turn_off", {"entity_id": wifi_entity}
        )

    # --- auto-off timers -------------------------------------------------

    def _cancel_timer(self, zone_id: str) -> None:
        if cancel := self._timers.pop(zone_id, None):
            cancel()

    def _arm_timer(self, zone_id: str) -> None:
        self._cancel_timer(zone_id)
        record = self._records.get(zone_id)
        until = dt_util.parse_datetime(record["until"]) if record and record.get("until") else None
        if until is None:
            return

        @callback
        def _expired(_now: datetime) -> None:
            self._timers.pop(zone_id, None)
            self.hass.async_create_task(self.async_deactivate_zone(zone_id))

        self._timers[zone_id] = async_track_point_in_utc_time(self.hass, _expired, until)

    # --- repair issues ---------------------------------------------------

    def _issue_id(self, zone_id: str) -> str:
        return f"missing_entities_{self.entry.entry_id}_{zone_id}"

    def _update_issue(self, zone_id: str, zone: dict[str, Any], missing: list[str]) -> None:
        if missing:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self._issue_id(zone_id),
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="missing_entities",
                translation_placeholders={
                    "zone": zone["name"],
                    "entities": ", ".join(missing),
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, self._issue_id(zone_id))

    def _cleanup_issues(self) -> None:
        """Drop issues that belong to zones which no longer exist."""
        prefix = f"missing_entities_{self.entry.entry_id}_"
        wanted = {self._issue_id(z) for z in self.zones}
        for domain, issue_id in list(ir.async_get(self.hass).issues):
            if domain == DOMAIN and issue_id.startswith(prefix) and issue_id not in wanted:
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)
