# Guest Mode Integration for Home Assistant

Guest Mode lets you toggle a set of automations, scripts, and entities for one or more zones with a single switch. It is designed for quickly adjusting your home when guests arrive (and restoring the previous state afterward).

## Key features

- **Main guest mode switch** to enable/disable all configured zones at once.
- **Per-zone switches** to control guest mode behavior in specific areas.
- **Full state restore** for everything the integration toggles. Lights, climate, covers, media players and similar entities get their brightness, setpoints, positions etc. back, not just on/off. Restore data survives restarts.
- **Auto-off timer** per zone: switch the zone off automatically after a set number of hours.
- **Preview before saving** — when you add or edit a zone you see what will be turned on/off and which entities no longer exist. Missing entities also show up under **Settings → Repairs**.
- **Optional global WiFi handling** so you can force a guest WiFi device on or off while Guest Mode is active.
- **Searchable entity pickers** in the UI — find entities by friendly name or entity ID.
- **Live reconfiguration** — add, edit, or delete zones at any time without restarting Home Assistant.

## How it works

Each zone defines:

- Automations to turn **OFF**
- Automations to turn **ON**
- Scripts to turn **OFF**
- Scripts to turn **ON**
- Entities to turn **OFF**
- Entities to turn **ON**

When you turn a zone **ON**:

1. Current states for all configured entities are saved.
2. Automations/scripts/entities are turned **ON/OFF** as configured.
3. If global WiFi is configured and this is the **first active zone**, WiFi is set to the selected mode.

When you turn a zone **OFF**:

1. Saved states for that zone are restored.
2. If global WiFi is configured and this is the **last active zone**, WiFi is set to the opposite mode.

Turning a zone on while it is already on does nothing, so the saved original states are never overwritten.

The **main Guest Mode switch** toggles all zones at once and is **on while any zone is on**.

## Installation

1. Copy the `custom_components/guest_mode` folder into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the **Guest Mode** integration via **Settings → Devices & Services → Add Integration**.

### HACS installation

1. Open **HACS → Integrations**.
2. Click **⋮ → Custom repositories**.
3. Add `https://github.com/KrX3D/HomeAssistantGuestMode` as **Integration**.
4. Install **Guest Mode** from HACS.
5. Restart Home Assistant.
6. Add the **Guest Mode** integration via **Settings → Devices & Services → Add Integration**.

## Configuration

Configuration is done entirely through the UI (Config Flow).

### Initial setup menu

- **Add zone**: define a zone and the entities it should control.
- **Set up WiFi**: optionally define a WiFi entity and the desired mode when Guest Mode is ON.
- **Finish**: finish configuration.

Only one Guest Mode instance can be configured.

### Reconfiguration (after setup)

Open **Settings → Devices & Services → Guest Mode → Configure** to manage your setup:

- **Add zone**: create a new zone.
- **Edit zone**: modify an existing zone's name or entity assignments.
- **Delete zone**: remove a zone. The corresponding switch entity is removed immediately.
- **Set up / Edit WiFi**: configure or update the global WiFi entity.
- **Done**: save and close.

### Zone options

For each zone you can configure:

- **Zone name** — used as the switch label and to generate the entity ID (e.g. `Living Room` → `switch.guest_mode_living_room`).
- Automations to turn **OFF**
- Automations to turn **ON**
- Scripts to turn **OFF**
- Scripts to turn **ON**
- Entities to turn **OFF**
- Entities to turn **ON**
- **Auto-off after (hours)** — `0` disables the timer.
- When editing: **Also update the switch entity ID** renames the entity ID to match a new zone name.

All entity fields support **search** — type a friendly name or entity ID to filter the list.

### Global WiFi options

- **WiFi entity**: a switch or similar entity representing WiFi access (for example, a UniFi WiFi enable/disable switch).
- **WiFi mode**: whether WiFi should be **ON** or **OFF** while Guest Mode is active.

## Entities

After setup, the integration creates a **Guest Mode** device containing:

- `switch.guest_mode` — main switch (toggles all zones at once)
- `switch.guest_mode_<zone_id>` — one switch per configured zone

Zone switches are displayed under the Guest Mode device using just the zone name (e.g. `Downstairs`, `Kitchen`).

## Services

### `guest_mode.restore_zone_states`

Switches an active zone off and restores the states saved when it was switched on (same as turning the zone switch off, including WiFi handling).

| Field   | Required | Description               |
|---------|----------|---------------------------|
| zone_id | Yes      | ID of the zone to restore (e.g. `living_room`) |

## Usage examples

### Toggle a zone manually

1. Go to **Settings → Devices & Services → Guest Mode**.
2. Turn on the zone switch for the area you want.
3. Turn it off to restore all previous states for that zone.

### Toggle all zones at once

Use the main `Guest Mode` switch to enable or disable every configured zone simultaneously.

## Limitations / notes

- WiFi is toggled only when the first zone turns on or the last zone turns off, to avoid flipping the WiFi state while other zones are still active.
- When WiFi is configured, it is always set to the **opposite** of the configured mode when Guest Mode is disabled.
- Entities that no longer exist at the time a zone is activated are skipped and a warning is logged.
- Zone IDs are derived from the zone name at creation time. Renaming a zone via Edit updates the display name but only changes the entity ID if you tick **Also update the switch entity ID**.
- Deleting an active zone restores its saved states first.
- Requires Home Assistant 2024.11 or newer.

## Support

If you run into issues, feel free to open an issue on the GitHub repository.