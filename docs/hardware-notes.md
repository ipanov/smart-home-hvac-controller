# Home Automation Controller Phone — Hardware Notes

This document records the hardware setup for running the SmartHVAC home-automation stack on a rooted Android phone.

## Phone model and prerequisites

- **Recommended minimum**: Android 10+ phone with unlockable bootloader and root support.
- **Storage**: at least 32 GB internal storage for Docker images, Home Assistant, and logs.
- **Network**: Wi-Fi or wired ethernet via USB adapter; MQTT and Home Assistant require reliable LAN access.
- **Power**: keep the device plugged in; battery-care scripts will cycle charging between 20% and 80%.

## Enabling developer options and OEM unlock

1. Open **Settings → About phone** and tap **Build number** seven times until developer mode is enabled.
2. Go to **Settings → System → Developer options**.
3. Enable **OEM unlocking** and **USB debugging**.
4. Connect the phone to a PC and authorize the debugging key when prompted.

## Unlocking bootloader

> **Warning**: This will wipe all user data.

1. Reboot into bootloader: `adb reboot bootloader`.
2. Run: `fastboot oem unlock` or `fastboot flashing unlock` depending on the device.
3. Follow the on-screen confirmation.
4. Reboot and complete initial setup again.

## Flashing TWRP recovery

1. Download the correct TWRP image for your device model.
2. Reboot to bootloader: `adb reboot bootloader`.
3. Flash recovery: `fastboot flash recovery twrp-<version>.img`.
4. Boot into recovery: `fastboot boot twrp-<version>.img`.
5. (Optional) flash TWRP permanently from within TWRP.

## Flashing Magisk for root

1. Download the latest Magisk APK and rename it to `.zip` if flashing via TWRP.
2. Boot into TWRP recovery.
3. Install the Magisk ZIP.
4. Reboot to system.
5. Open the Magisk app and verify that root is active.

## Verifying root

From an ADB shell:

```bash
adb shell
su -c 'id'
```

Expected output includes `uid=0(root)`.

## Installing Termux and Termux:API

1. Install F-Droid from <https://f-droid.org/>.
2. Install **Termux** and **Termux:API** from F-Droid.
3. Install the Termux:API app as a system app or grant permissions manually.

## Pushing the project and starting Home Assistant

1. From the project root on the PC:

   ```bash
   python -m smarthvac.phone_deployer
   ```

   or use `adb push` directly:

   ```bash
   adb push . /data/data/com.termux/files/home/home-automation
   ```

2. In Termux, run:

   ```bash
   bash home-automation/phone-scripts/termux-setup.sh
   bash home-automation/phone-scripts/start-ha.sh
   ```

3. Home Assistant will be available at `http://<phone-ip>:8123`.

## Configuring 20-80% battery care

The `battery-care.sh` script reads `/sys/class/power_supply/battery/capacity` and writes to `/sys/class/power_supply/battery/batt_slate_mode`.

- `echo 1 > batt_slate_mode` disables charging at ≥80%.
- `echo 0 > batt_slate_mode` enables charging at ≤20%.

To run every minute as root, schedule it via `crond` or Termux boot:

```bash
su -c "crond -c /data/data/com.termux/files/home/home-automation/phone-scripts/cron"
```

If the sysfs node is not writable, use a relay-based fallback via `smarthvac.battery_care.RelayChargeController`.

## Pairing Xiaomi BLE sensors

1. Enable Bluetooth on the phone.
2. Use Home Assistant's **Bluetooth** integration or the `bluetoothctl` CLI.
3. Place the sensor in pairing mode (usually a long press on the button).
4. Add the device in Home Assistant and rename it (e.g., `sensor.living_room_temperature`).

## Connecting Vivax R+ AC (Tuya/SmartLife or IR fallback)

### Tuya/SmartLife cloud integration

1. Create a Tuya IoT project at <https://iot.tuya.com/>.
2. Add the Vivax R+ device to the SmartLife app.
3. In Home Assistant, add the **Tuya** integration and provide your cloud credentials.

### IR fallback

If cloud control is unreliable, use a BroadLink RM Mini 3 (or similar IR blaster):

1. Add the **Broadlink** integration in Home Assistant.
2. Learn the IR commands for power, mode, temperature, and fan speed.
3. Create `climate` or `remote` entities for each learned command.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `adb devices` shows `unauthorized` | Missing PC RSA key acceptance | Revoke USB debugging authorizations on the phone and reconnect. |
| Docker daemon fails to start | Kernel lacks cgroups/modules | Try an alternate Termux Docker build or use a device with mainline kernel support. |
| `batt_slate_mode` not writable | Samsung-specific node absent | Use the relay fallback or a different charge-control sysfs node. |
| MQTT messages not arriving | Broker not running or firewall | Verify Mosquitto with `mosquitto_sub -t '#' -v`; check Termux networking. |
| `termux-location` hangs | Location permission denied | Run `phone-scripts/grant-location.sh` as root. |
| Home Assistant unreachable | Docker compose not started | Run `phone-scripts/start-ha.sh` and check `docker logs`. |
