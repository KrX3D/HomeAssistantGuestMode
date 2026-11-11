"""Setup, the main switch and the restore_zone_states service."""
from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import ENTRY_ID, LIVING, OFFICE, make_entry, setup_entry, switch

MAIN_SWITCH = "switch.guest_mode"
LIVING_SWITCH = "switch.guest_mode_living"
OFFICE_SWITCH = "switch.guest_mode_office"

pytestmark = pytest.mark.usefixtures("entities")


def _two_zones():
    return make_entry({"living": dict(LIVING), "office": dict(OFFICE)})


async def test_setup_and_unload(hass: HomeAssistant) -> None:
    entry = _two_zones()
    await setup_entry(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    for entity_id in (MAIN_SWITCH, LIVING_SWITCH, OFFICE_SWITCH):
        assert hass.states.get(entity_id).state == "off"
    assert hass.states.get(MAIN_SWITCH).attributes["zone_count"] == 2

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_main_switch_toggles_all_zones(hass: HomeAssistant) -> None:
    await setup_entry(hass, _two_zones())

    await switch(hass, MAIN_SWITCH, True)
    assert hass.states.get(LIVING_SWITCH).state == "on"
    assert hass.states.get(OFFICE_SWITCH).state == "on"
    main = hass.states.get(MAIN_SWITCH)
    assert main.state == "on"
    assert sorted(main.attributes["active_zones"]) == ["Living", "Office"]

    await switch(hass, MAIN_SWITCH, False)
    assert hass.states.get(LIVING_SWITCH).state == "off"
    assert hass.states.get(OFFICE_SWITCH).state == "off"
    assert hass.states.get(MAIN_SWITCH).state == "off"


async def test_main_switch_on_while_any_zone_on(hass: HomeAssistant) -> None:
    await setup_entry(hass, _two_zones())

    await switch(hass, OFFICE_SWITCH, True)

    main = hass.states.get(MAIN_SWITCH)
    assert main.state == "on"
    assert main.attributes["active_zones"] == ["Office"]


async def test_restore_service_deactivates_zone(hass: HomeAssistant) -> None:
    calls = await setup_entry(hass, make_entry())
    await switch(hass, LIVING_SWITCH, True)
    calls.clear()

    await hass.services.async_call(
        "guest_mode", "restore_zone_states", {"zone_id": "living"}, blocking=True
    )
    await hass.async_block_till_done()

    assert hass.states.get(LIVING_SWITCH).state == "off"
    assert calls.entity_ids("automation", "turn_on") == ["automation.motion"]


async def test_restore_service_rejects_inactive_zone(hass: HomeAssistant) -> None:
    await setup_entry(hass, make_entry())

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "guest_mode", "restore_zone_states", {"zone_id": "living"}, blocking=True
        )


async def test_orphan_zone_entities_are_removed(hass: HomeAssistant) -> None:
    registry = er.async_get(hass)
    entry = make_entry()
    entry.add_to_hass(hass)
    registry.async_get_or_create(
        "switch",
        "guest_mode",
        f"guest_mode_zone_deleted_{ENTRY_ID}",
        config_entry=entry,
        suggested_object_id="guest_mode_deleted",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get("switch.guest_mode_deleted") is None
    assert registry.async_get(LIVING_SWITCH) is not None


async def test_zone_cannot_switch_guest_mode_itself(hass: HomeAssistant) -> None:
    zone = {**LIVING, "entities_off": ["switch.plug", MAIN_SWITCH]}
    calls = await setup_entry(hass, make_entry({"living": zone}))

    await switch(hass, LIVING_SWITCH, True)

    assert calls.entity_ids("homeassistant", "turn_off") == ["switch.plug"]
