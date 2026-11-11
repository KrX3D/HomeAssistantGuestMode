"""Config flow and options flow."""
from __future__ import annotations

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import LIVING, make_entry, setup_entry

pytestmark = pytest.mark.usefixtures("entities")


async def _add_zone(hass: HomeAssistant, flow, flow_id: str, data: dict):
    result = await flow.async_configure(flow_id, {"next_step_id": "add_zone"})
    assert result["step_id"] == "add_zone"
    result = await flow.async_configure(flow_id, data)
    if result["type"] is FlowResultType.FORM and result["step_id"] == "preview":
        result = await flow.async_configure(flow_id, {})
    return result


async def test_full_config_flow(hass: HomeAssistant) -> None:
    flow = hass.config_entries.flow
    result = await flow.async_init("guest_mode", context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.MENU

    result = await flow.async_configure(result["flow_id"], {"next_step_id": "add_zone"})
    result = await flow.async_configure(
        result["flow_id"],
        {"zone_name": " Living Room ", "entities_off": ["light.lamp"], "auto_off_hours": 3},
    )
    assert result["step_id"] == "preview"
    assert "light.lamp" in result["description_placeholders"]["turn_off"]
    assert result["description_placeholders"]["auto_off"] == "3 h"
    result = await flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.MENU

    result = await flow.async_configure(result["flow_id"], {"next_step_id": "wifi"})
    result = await flow.async_configure(
        result["flow_id"], {"wifi_entity": "switch.guest_wifi", "wifi_mode": "on"}
    )
    result = await flow.async_configure(result["flow_id"], {"next_step_id": "finish"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    zone = result["data"]["zones"]["living_room"]
    assert zone["name"] == "Living Room"
    assert zone["entities_off"] == ["light.lamp"]
    assert zone["auto_off_hours"] == 3.0
    assert result["data"]["global_wifi"] == {"entity": "switch.guest_wifi", "mode": "on"}


@pytest.mark.parametrize(
    ("name", "error"),
    [("   ", "zone_name_required"), ("!!!", "zone_name_invalid"), ("living", "zone_name_duplicate")],
)
async def test_zone_name_validation(hass: HomeAssistant, name: str, error: str) -> None:
    flow = hass.config_entries.flow
    result = await flow.async_init("guest_mode", context={"source": config_entries.SOURCE_USER})
    await _add_zone(hass, flow, result["flow_id"], {"zone_name": "Living"})

    result = await flow.async_configure(result["flow_id"], {"next_step_id": "add_zone"})
    result = await flow.async_configure(result["flow_id"], {"zone_name": name})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"zone_name": error}


async def test_single_instance(hass: HomeAssistant) -> None:
    make_entry().add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "guest_mode", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_delete_zone(hass: HomeAssistant) -> None:
    entry = make_entry({"living": dict(LIVING), "office": {**LIVING, "name": "Office"}})
    await setup_entry(hass, entry)

    flow = hass.config_entries.options
    result = await flow.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await flow.async_configure(result["flow_id"], {"next_step_id": "select_delete"})
    result = await flow.async_configure(result["flow_id"], {"zone": "office"})
    result = await flow.async_configure(result["flow_id"], {"next_step_id": "finish"})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert list(entry.data["zones"]) == ["living"]
    assert hass.states.get("switch.guest_mode_office") is None
