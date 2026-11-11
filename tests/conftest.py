"""Shared fixtures for the Guest Mode tests."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.guest_mode.const import DOMAIN, STORAGE_VERSION

ENTRY_ID = "test_entry"
STORAGE_KEY = f"{DOMAIN}_{ENTRY_ID}_saved_states"

LIVING = {
    "name": "Living",
    "automations_off": ["automation.motion"],
    "automations_on": [],
    "scripts_off": [],
    "scripts_on": ["script.welcome"],
    "entities_off": ["light.lamp", "switch.plug"],
    "entities_on": [],
    "auto_off_hours": 0,
}

OFFICE = {
    "name": "Office",
    "automations_off": [],
    "automations_on": [],
    "scripts_off": [],
    "scripts_on": [],
    "entities_off": ["input_boolean.office_alarm"],
    "entities_on": [],
    "auto_off_hours": 0,
}

# Services the integration calls while switching zones. They are replaced by
# recorders so the tests can assert exactly what would have happened.
RECORDED_SERVICES = (
    ("automation", "turn_on"),
    ("automation", "turn_off"),
    ("script", "turn_on"),
    ("script", "turn_off"),
    ("homeassistant", "turn_on"),
    ("homeassistant", "turn_off"),
    ("scene", "apply"),
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow loading custom_components/guest_mode in every test."""
    return


@dataclass
class ServiceRecorder:
    """Collects the service calls made by the integration."""

    calls: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)

    def of(self, domain: str, service: str) -> list[dict[str, Any]]:
        return [d for dom, svc, d in self.calls if (dom, svc) == (domain, service)]

    def entity_ids(self, domain: str, service: str) -> list[str]:
        return [d["entity_id"] for d in self.of(domain, service)]

    def clear(self) -> None:
        self.calls.clear()


def install_recorder(hass: HomeAssistant) -> ServiceRecorder:
    """Register (or override) the recorded services. Call after setup, because
    loading the `scene` dependency registers the real `scene.apply`."""
    recorder = ServiceRecorder()

    def _make(domain: str, service: str):
        async def _handler(call: ServiceCall) -> None:
            recorder.calls.append((domain, service, dict(call.data)))

        return _handler

    for domain, service in RECORDED_SERVICES:
        hass.services.async_register(domain, service, _make(domain, service))
    return recorder


@pytest.fixture
def entities(hass: HomeAssistant) -> None:
    """Entities referenced by the zones, in their 'normal' (pre-guest) state."""
    hass.states.async_set("automation.motion", "on")
    hass.states.async_set("script.welcome", "off")
    hass.states.async_set("light.lamp", "on", {"brightness": 120, "color_temp_kelvin": 3000})
    hass.states.async_set("switch.plug", "on")
    hass.states.async_set("input_boolean.office_alarm", "on")
    hass.states.async_set("switch.guest_wifi", "off")


def make_entry(
    zones: dict[str, dict[str, Any]] | None = None,
    global_wifi: dict[str, Any] | None = None,
) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Guest Mode",
        entry_id=ENTRY_ID,
        data={
            "zones": {"living": dict(LIVING)} if zones is None else zones,
            "global_wifi": global_wifi or {},
        },
    )


def stored_records(hass_storage: dict[str, Any]) -> dict[str, Any]:
    return hass_storage[STORAGE_KEY]["data"]


def seed_storage(hass_storage: dict[str, Any], data: dict[str, Any]) -> None:
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": data,
    }


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> ServiceRecorder:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return install_recorder(hass)


async def switch(hass: HomeAssistant, entity_id: str, on: bool) -> None:
    await hass.services.async_call(
        "switch", "turn_on" if on else "turn_off", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()
