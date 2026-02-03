# Guest Mode Integration for Home Assistant

Guest Mode lets you toggle a set of automations, scripts, and entities for one or more zones with a single switch. It is designed for quickly adjusting your home when guests arrive (and restoring the previous state afterward).

## Key features

- **Main guest mode switch** to enable/disable all configured zones at once.
- **Per-zone switches** to control guest mode behavior in specific areas.
- **State restore** for everything the integration toggles.
- **Optional global WiFi handling** so you can force a guest WiFi device on or off while Guest Mode is active.

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

The **main Guest Mode switch** simply toggles all zones at once.

## Installation

1. Copy the `custom_components/guest_mode` folder into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the **Guest Mode** integration via **Settings → Devices & Services → Add Integration**.

## Configuration

Configuration is done entirely through the UI (Config Flow).

### Main setup menu

- **Set up first zone**: define a zone and the entities it should control.
- **Set up WiFi**: optionally define a WiFi entity and the desired mode when Guest Mode is ON.
- **Done**: finish configuration.

### Zone options

For each zone you can configure:

- Automations to turn **OFF**
- Automations to turn **ON**
- Scripts to turn **OFF**
- Scripts to turn **ON**
- Entities to turn **OFF**
- Entities to turn **ON**

### Global WiFi options

- **WiFi entity**: a switch or similar entity representing WiFi access.
- **WiFi mode**: whether WiFi should be **ON** or **OFF** while Guest Mode is active.

## Entities

After setup, the integration creates:

- `switch.guest_mode` (main switch)
- `switch.guest_mode_<zone_id>` for each configured zone

## Services

### `guest_mode.restore_zone_states`

Restores saved states for a specific zone.

| Field   | Required | Description          |
|---------|----------|----------------------|
| zone_id | Yes      | ID of the zone to restore |

## Usage examples

### Toggle a zone manually

1. Go to **Settings → Devices & Services → Guest Mode**.
2. Turn on the zone switch you want.
3. Turn it off to restore previous states.

### Toggle all zones

Use the main `Guest Mode` switch to enable or disable every zone at once.

## Limitations / notes

- WiFi is toggled only when the first zone turns on or the last zone turns off, to avoid flipping WiFi while other zones are still active.
- When WiFi is configured, it is set to the opposite mode when guest mode is disabled (per current configuration design).

## Ideas for future improvements

- Store and restore the original WiFi state instead of flipping to the opposite mode.
- Add per-zone WiFi settings.
- Add optional delays or schedules per zone.
- Support notifications when guest mode changes state.

## Support

If you run into issues, feel free to open an issue on the GitHub repository.
