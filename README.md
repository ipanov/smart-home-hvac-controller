# Smart Home HVAC Controller

A 24/7 autonomous HVAC brain for a **Vivax R+ multi-split** air conditioner, running on a rooted **Samsung Galaxy S8**. It integrates Xiaomi BLE temperature/humidity sensors and a Xiaomi air purifier, fetches local weather, forecast and air-pollution data, and keeps the phone battery cycling between **20% and 80%** charge.

> **Public repo:** https://github.com/ipanov/smart-home-hvac-controller

---

## Features

- **PID + feed-forward climate control** tuned with outside temperature, humidity and weather forecast.
- **Weather & pollution integration**: Open-Meteo for temperature/humidity/forecast, OpenWeatherMap for AQI/PM2.5/PM10/O3.
- **Battery care**: kernel-level or relay-based 20–80% charge cycling to preserve the always-plugged S8 battery.
- **Xiaomi ecosystem**: BLE temperature/humidity sensors and Miio air purifier support.
- **Vivax R+ AC control**: via Tuya/SmartLife local API when available, with ESPHome IR-blaster fallback.
- **Web dashboard**: FastAPI-based status page and target-temperature control.
- **Desktop automation helpers**: Windows UI automation (`pywinauto`) for phone-rooting and app-install workflows.
- **Comprehensive test suite**: unit, integration and UI tests with `pytest` and `Playwright`.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Samsung Galaxy S8                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Termux     │  │   Docker     │  │  Home Assistant  │  │
│  │  (ADB/root)  │  │              │  │    Container     │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│         │                  │                    │           │
│         ▼                  ▼                    ▼           │
│   Battery care scripts  Mosquitto MQTT    Xiaomi BLE/Miio   │
│   Phone location        Vivax Tuya/IR     Weather/Pollution │
└─────────────────────────────────────────────────────────────┘
```

The Python package in `src/smarthvac/` contains the reusable control logic and is fully tested independently of the phone hardware.

---

## Repository Layout

```
.
├── src/smarthvac/                  # Core Python package
│   ├── pid_controller.py           # PID + weather-feedforward algorithm
│   ├── weather_client.py           # Open-Meteo + OpenWeatherMap clients
│   ├── battery_care.py             # 20-80% charge logic
│   ├── config_generator.py         # Generate Home Assistant YAML
│   ├── orchestrator.py             # Full HVAC decision orchestrator
│   ├── dashboard.py                # FastAPI web dashboard
│   ├── desktop_automation.py       # Windows UI automation helpers
│   └── templates/dashboard.html    # Dashboard UI
├── tests/                          # Test suite
│   ├── unit/                       # 48 unit tests
│   ├── integration/                # 5 integration tests
│   └── ui/                         # 5 UI tests (Playwright + pywinauto)
├── ha-config/                      # Generated Home Assistant configs
├── phone-scripts/                  # Termux/ADB deployment scripts
├── firmware/                       # ESPHome IR-blaster fallback
├── docker-compose.yml              # Home Assistant + Mosquitto
├── pyproject.toml                  # Package metadata + test config
└── .github/workflows/ci.yml        # GitHub Actions CI
```

---

## Quick Start

### 1. Install Python dependencies

```bash
cd D:/Repos/home-automation
python -m pip install --upgrade pip
pip install -e ".[test]"
playwright install chromium
```

### 2. Run the test suite

```bash
python -m pytest -v
```

Expected output:
```text
56 passed, 2 skipped, 1 warning
```

UI tests that require an interactive Windows desktop session are skipped in headless/CI environments.

### 3. Run the dashboard locally

```bash
uvicorn smarthvac.dashboard:create_app --factory --reload
```

Open http://localhost:8000 in a browser.

---

## Phone Deployment

> **Warning:** rooting and bootloader unlocking will wipe the phone. Back up data first.

### Prerequisites

- Samsung Galaxy S8 (SM-G950F or similar Exynos model)
- USB cable connected to a Windows PC with ADB/fastboot installed
- OEM unlocking enabled in Developer options
- USB debugging enabled

### Automated steps

The `phone-scripts/` directory contains the deployment automation:

1. **Install ADB/fastboot** (already handled via Chocolatey):
   ```powershell
   choco install adb -y
   ```

2. **Root the phone** using the TWRP + Magisk flow documented in `docs/hardware-notes.md`. Some steps require tapping the phone screen (OEM unlock confirmation, TWRP install).

3. **Install Termux and Termux:API** from F-Droid.

4. **Push the project to the phone**:
   ```bash
   adb push D:/Repos/home-automation /sdcard/Download/home-automation
   adb shell su -c "cp -r /sdcard/Download/home-automation /data/data/com.termux/files/home/"
   ```

5. **Run Termux setup and start Home Assistant**:
   ```bash
   adb shell "bash /data/data/com.termux/files/home/home-automation/phone-scripts/termux-setup.sh"
   adb shell "bash /data/data/com.termux/files/home/home-automation/phone-scripts/start-ha.sh"
   ```

6. **Enable 20-80% battery cycling**:
   ```bash
   adb shell su -c "sh /data/data/com.termux/files/home/home-automation/phone-scripts/battery-care.sh"
   ```

Detailed per-step commands are in `docs/hardware-notes.md` (generated during deployment).

---

## Home Assistant Configuration

Run the config generator to produce the Home Assistant YAML:

```bash
python -c "
from smarthvac.config_generator import ConfigGenerator
cg = ConfigGenerator(42.0, 21.0, 250, 'Europe/Belgrade', 'YOUR_OPENWEATHER_API_KEY')
cg.write_configs('ha-config')
"
```

Then start Home Assistant with the generated configs:

```bash
docker compose up -d
```

---

## Control Algorithm

The HVAC brain uses a **PID controller** with two feed-forward terms:

- **Outside-temperature feed-forward**: raises the effective target temperature when it is hot outside, reducing unnecessary over-cooling.
- **Humidity compensation**: lowers the effective target when humidity is low (dry air feels cooler).

```python
feedforward = 0.04 * max(0, outside_temp - 24)
humidity_comp = -0.02 * max(0, 60 - humidity)
adjusted_target = target_temp + feedforward + humidity_comp
```

The PID output decides AC mode and fan speed, with a configurable deadband to prevent rapid cycling.

---

## Contributing / Extending

- Add new sensors by extending `HvacOrchestrator`.
- Add new AC protocols by implementing a `ClimateEntity` adapter in Home Assistant.
- Tune PID gains via the `input_number.hvac_*` helpers in Home Assistant.

---

## License

MIT License — see [LICENSE](LICENSE) if present, otherwise this project is provided as-is.
