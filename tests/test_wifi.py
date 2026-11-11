"""Global guest WiFi handling."""
from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from .conftest import LIVING, OFFICE, make_entry, setup_entry, switch

WIFI = "switch.guest_wifi"
LIVING_SWITCH = "switch.guest_mode_living"
OFFICE_SWITCH = "switch.guest_mode_office"

pytestmark = pytest.mark.usefixtures("entities")


def _wifi_calls(calls, service: str) -> list[str]:
    return [e for e in calls.entity_ids("homeassistant", service) if e == WIFI]


@pytest.mark.parametrize(
    ("mode", "on_activate", "on_deactivate"),
    [("on", "turn_on", "turn_off"), ("off", "turn_off", "turn_on")],
)
async def test_wifi_follows_mode(
    hass: HomeAssistant, mode: str, on_activate: str, on_deactivate: str
) -> None:
    calls = await setup_entry(hass, make_entry(global_wifi={"entity": WIFI, "mode": mode}))

    await switch(hass, LIVING_SWITCH, True)
    assert _wifi_calls(calls, on_activate) == [WIFI]
    calls.clear()

    await switch(hass, LIVING_SWITCH, False)
    assert _wifi_calls(calls, on_deactivate) == [WIFI]


async def test_wifi_only_toggles_on_first_and_last_zone(hass: HomeAssistant) -> None:
    entry = make_entry(
        {"living": dict(LIVING), "office": dict(OFFICE)},
        global_wifi={"entity": WIFI, "mode": "on"},
    )
    calls = await setup_entry(hass, entry)

    await switch(hass, LIVING_SWITCH, True)
    await switch(hass, OFFICE_SWITCH, True)
    assert _wifi_calls(calls, "turn_on") == [WIFI]
    calls.clear()

    await switch(hass, LIVING_SWITCH, False)
    assert _wifi_calls(calls, "turn_off") == []

    await switch(hass, OFFICE_SWITCH, False)
    assert _wifi_calls(calls, "turn_off") == [WIFI]


async def test_no_wifi_configured(hass: HomeAssistant) -> None:
    calls = await setup_entry(hass, make_entry(global_wifi={}))
    await switch(hass, LIVING_SWITCH, True)
    await switch(hass, LIVING_SWITCH, False)

    assert WIFI not in calls.entity_ids("homeassistant", "turn_on")
    assert WIFI not in calls.entity_ids("homeassistant", "turn_off")


async def test_missing_wifi_entity_is_ignored(hass: HomeAssistant) -> None:
    hass.states.async_remove(WIFI)
    calls = await setup_entry(hass, make_entry(global_wifi={"entity": WIFI, "mode": "on"}))

    await switch(hass, LIVING_SWITCH, True)

    assert hass.states.get(LIVING_SWITCH).state == "on"
    assert WIFI not in calls.entity_ids("homeassistant", "turn_on")
