"""Saving and restoring the pre-guest-mode states."""
from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from .conftest import (
    LIVING,
    install_recorder,
    make_entry,
    seed_storage,
    setup_entry,
    stored_records,
    switch,
)

LIVING_SWITCH = "switch.guest_mode_living"

pytestmark = pytest.mark.usefixtures("entities")


async def test_activate_saves_states_and_applies_zone(hass: HomeAssistant, hass_storage) -> None:
    calls = await setup_entry(hass, make_entry())
    assert hass.states.get(LIVING_SWITCH).state == "off"

    await switch(hass, LIVING_SWITCH, True)

    assert hass.states.get(LIVING_SWITCH).state == "on"
    assert calls.entity_ids("automation", "turn_off") == ["automation.motion"]
    assert calls.entity_ids("script", "turn_on") == ["script.welcome"]
    assert calls.entity_ids("homeassistant", "turn_off") == ["light.lamp", "switch.plug"]

    saved = stored_records(hass_storage)["living"]["entities"]
    assert saved["automation.motion"] == {"state": "on", "attributes": {}}
    assert saved["script.welcome"] == {"state": "off", "attributes": {}}
    assert saved["switch.plug"] == {"state": "on", "attributes": {}}
    # Rich domains keep their attributes so scene.apply can restore them.
    assert saved["light.lamp"]["state"] == "on"
    assert saved["light.lamp"]["attributes"]["brightness"] == 120

    attrs = hass.states.get(LIVING_SWITCH).attributes
    assert attrs["active_since"] is not None
    assert attrs["auto_off_at"] is None
    assert set(attrs["saved_entities"]) == set(saved)


async def test_deactivate_restores_saved_states(hass: HomeAssistant, hass_storage) -> None:
    calls = await setup_entry(hass, make_entry())
    await switch(hass, LIVING_SWITCH, True)
    calls.clear()

    await switch(hass, LIVING_SWITCH, False)

    assert hass.states.get(LIVING_SWITCH).state == "off"
    assert calls.entity_ids("automation", "turn_on") == ["automation.motion"]
    assert calls.entity_ids("script", "turn_off") == ["script.welcome"]
    assert calls.entity_ids("homeassistant", "turn_on") == ["switch.plug"]
    [scene] = calls.of("scene", "apply")
    assert scene["entities"]["light.lamp"]["state"] == "on"
    assert scene["entities"]["light.lamp"]["brightness"] == 120
    assert stored_records(hass_storage) == {}


async def test_activate_twice_keeps_original_states(hass: HomeAssistant, hass_storage) -> None:
    calls = await setup_entry(hass, make_entry())
    await switch(hass, LIVING_SWITCH, True)
    original = stored_records(hass_storage)["living"]

    # Guest mode changed things; a second "on" must not save these as originals.
    hass.states.async_set("light.lamp", "off")
    hass.states.async_set("automation.motion", "off")
    calls.clear()
    await switch(hass, LIVING_SWITCH, True)

    assert calls.calls == []
    assert stored_records(hass_storage)["living"] == original


async def test_active_zone_survives_restart(hass: HomeAssistant, hass_storage) -> None:
    seed_storage(
        hass_storage,
        {
            "living": {
                "entities": {
                    "automation.motion": {"state": "on", "attributes": {}},
                    "light.lamp": {"state": "on", "attributes": {"brightness": 42}},
                },
                "since": "2026-01-01T00:00:00+00:00",
                "until": None,
            }
        },
    )
    calls = await setup_entry(hass, make_entry())
    assert hass.states.get(LIVING_SWITCH).state == "on"

    await switch(hass, LIVING_SWITCH, False)

    assert calls.entity_ids("automation", "turn_on") == ["automation.motion"]
    [scene] = calls.of("scene", "apply")
    assert scene["entities"]["light.lamp"] == {"brightness": 42, "state": "on"}


async def test_legacy_records_are_upgraded(hass: HomeAssistant, hass_storage) -> None:
    """Older versions stored {zone: {entity_id: state}}."""
    seed_storage(hass_storage, {"living": {"automation.motion": "on", "switch.plug": "off"}})
    calls = await setup_entry(hass, make_entry())
    assert hass.states.get(LIVING_SWITCH).state == "on"

    await switch(hass, LIVING_SWITCH, False)

    assert calls.entity_ids("automation", "turn_on") == ["automation.motion"]
    assert calls.entity_ids("homeassistant", "turn_off") == ["switch.plug"]


async def test_restore_skips_unavailable_and_unknown(hass: HomeAssistant, hass_storage) -> None:
    seed_storage(
        hass_storage,
        {
            "living": {
                "entities": {
                    "automation.motion": {"state": "unavailable", "attributes": {}},
                    "switch.plug": {"state": "unknown", "attributes": {}},
                    "light.lamp": {"state": "unavailable", "attributes": {}},
                },
                "since": None,
                "until": None,
            }
        },
    )
    calls = await setup_entry(hass, make_entry())

    await switch(hass, LIVING_SWITCH, False)

    assert calls.calls == []


async def test_restore_skips_removed_rich_entity(hass: HomeAssistant, hass_storage) -> None:
    seed_storage(
        hass_storage,
        {
            "living": {
                "entities": {"light.gone": {"state": "on", "attributes": {"brightness": 1}}},
                "since": None,
                "until": None,
            }
        },
    )
    calls = await setup_entry(hass, make_entry())

    await switch(hass, LIVING_SWITCH, False)

    assert calls.of("scene", "apply") == []


async def test_missing_entities_are_skipped_and_reported(hass: HomeAssistant, hass_storage) -> None:
    zone = {**LIVING, "entities_off": ["light.lamp", "light.deleted"]}
    calls = await setup_entry(hass, make_entry({"living": zone}))

    await switch(hass, LIVING_SWITCH, True)

    assert calls.entity_ids("homeassistant", "turn_off") == ["light.lamp"]
    assert "light.deleted" not in stored_records(hass_storage)["living"]["entities"]

    issue = ir.async_get(hass).async_get_issue("guest_mode", "missing_entities_test_entry_living")
    assert issue is not None
    assert issue.translation_placeholders["entities"] == "light.deleted"


async def test_failing_service_does_not_abort_zone(hass: HomeAssistant) -> None:
    await setup_entry(hass, make_entry())
    calls = install_recorder(hass)

    async def _fail_for_lamp(call: ServiceCall) -> None:
        if call.data["entity_id"] == "light.lamp":
            raise HomeAssistantError("boom")
        calls.calls.append(("homeassistant", "turn_off", dict(call.data)))

    hass.services.async_register("homeassistant", "turn_off", _fail_for_lamp)

    await switch(hass, LIVING_SWITCH, True)

    assert hass.states.get(LIVING_SWITCH).state == "on"
    assert calls.entity_ids("homeassistant", "turn_off") == ["switch.plug"]


async def test_zone_deleted_while_active_is_restored(hass: HomeAssistant, hass_storage) -> None:
    seed_storage(
        hass_storage,
        {
            "removed": {
                "entities": {"automation.motion": {"state": "on", "attributes": {}}},
                "since": None,
                "until": None,
            }
        },
    )
    entry = make_entry()
    entry.add_to_hass(hass)
    # Record calls from the very start: the restore runs during setup.
    calls = install_recorder(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert calls.entity_ids("automation", "turn_on") == ["automation.motion"]
    assert stored_records(hass_storage) == {}
