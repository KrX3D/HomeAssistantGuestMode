"""Auto-off timers."""
from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import (
    LIVING,
    make_entry,
    seed_storage,
    setup_entry,
    stored_records,
    switch,
)

LIVING_SWITCH = "switch.guest_mode_living"

pytestmark = pytest.mark.usefixtures("entities")


def _timed_entry(hours: float = 2):
    return make_entry({"living": {**LIVING, "auto_off_hours": hours}})


async def test_auto_off_after_configured_hours(hass: HomeAssistant, hass_storage) -> None:
    calls = await setup_entry(hass, _timed_entry(2))
    await switch(hass, LIVING_SWITCH, True)

    until = dt_util.parse_datetime(hass.states.get(LIVING_SWITCH).attributes["auto_off_at"])
    assert until is not None
    assert timedelta(hours=1, minutes=59) < until - dt_util.utcnow() <= timedelta(hours=2)

    calls.clear()
    async_fire_time_changed(hass, until - timedelta(minutes=1))
    await hass.async_block_till_done()
    assert hass.states.get(LIVING_SWITCH).state == "on"

    async_fire_time_changed(hass, until + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert hass.states.get(LIVING_SWITCH).state == "off"
    assert calls.entity_ids("automation", "turn_on") == ["automation.motion"]
    assert stored_records(hass_storage) == {}


async def test_no_timer_when_hours_is_zero(hass: HomeAssistant) -> None:
    await setup_entry(hass, _timed_entry(0))
    await switch(hass, LIVING_SWITCH, True)

    assert hass.states.get(LIVING_SWITCH).attributes["auto_off_at"] is None
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=60))
    await hass.async_block_till_done()
    assert hass.states.get(LIVING_SWITCH).state == "on"


async def test_manual_off_cancels_timer(hass: HomeAssistant) -> None:
    calls = await setup_entry(hass, _timed_entry(1))
    await switch(hass, LIVING_SWITCH, True)
    await switch(hass, LIVING_SWITCH, False)
    calls.clear()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert calls.calls == []


async def test_expired_timer_on_startup_restores(hass: HomeAssistant, hass_storage) -> None:
    past = dt_util.utcnow() - timedelta(minutes=5)
    seed_storage(
        hass_storage,
        {
            "living": {
                "entities": {"automation.motion": {"state": "on", "attributes": {}}},
                "since": (past - timedelta(hours=1)).isoformat(),
                "until": past.isoformat(),
            }
        },
    )
    await setup_entry(hass, _timed_entry(1))

    assert hass.states.get(LIVING_SWITCH).state == "off"
    assert stored_records(hass_storage) == {}


async def test_pending_timer_is_rearmed_on_startup(hass: HomeAssistant, hass_storage) -> None:
    until = dt_util.utcnow() + timedelta(minutes=30)
    seed_storage(
        hass_storage,
        {
            "living": {
                "entities": {"automation.motion": {"state": "on", "attributes": {}}},
                "since": dt_util.utcnow().isoformat(),
                "until": until.isoformat(),
            }
        },
    )
    calls = await setup_entry(hass, _timed_entry(1))
    assert hass.states.get(LIVING_SWITCH).state == "on"

    async_fire_time_changed(hass, until + timedelta(seconds=1))
    await hass.async_block_till_done()

    assert hass.states.get(LIVING_SWITCH).state == "off"
    assert calls.entity_ids("automation", "turn_on") == ["automation.motion"]


async def test_unload_cancels_timer(hass: HomeAssistant) -> None:
    entry = _timed_entry(1)
    calls = await setup_entry(hass, entry)
    await switch(hass, LIVING_SWITCH, True)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    calls.clear()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert calls.calls == []
