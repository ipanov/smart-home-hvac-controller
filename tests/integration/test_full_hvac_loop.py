"""Integration test covering a full HVAC control loop."""

from unittest.mock import MagicMock

import pytest

from smarthvac.battery_care import (
    BatteryCareConfig,
    BatteryCareLoop,
    RelayChargeController,
)
from smarthvac.config_generator import ConfigGenerator
from smarthvac.orchestrator import HvacDecision, HvacOrchestrator
from smarthvac.pid_controller import HvacPidController
from smarthvac.weather_client import (
    AirQualitySnapshot,
    WeatherService,
    WeatherSnapshot,
)


pytestmark = pytest.mark.integration


@pytest.fixture
def pid_controller() -> HvacPidController:
    """Default PID controller tuned for a 24 °C setpoint."""
    return HvacPidController(target_temp=24.0)


@pytest.fixture
def battery_loop() -> BatteryCareLoop:
    """Battery-care loop with a no-op relay controller."""
    return BatteryCareLoop(
        config=BatteryCareConfig(upper_threshold=80, lower_threshold=20),
        charge_controller=RelayChargeController(set_relay=lambda _state: None),
        battery_level_source=lambda: 50,
    )


def _weather_service(
    temp: float = 35.0,
    humidity: float = 45.0,
    forecast_high: float = 37.0,
    forecast_low: float = 22.0,
    pm25: float = 45.0,
) -> WeatherService:
    """Build a WeatherService backed by mocked HTTP clients."""
    openmeteo_client = MagicMock()
    openmeteo_client.get_current_weather.return_value = WeatherSnapshot(
        temperature=temp,
        humidity=humidity,
        forecast_high=forecast_high,
        forecast_low=forecast_low,
    )

    pollution_client = MagicMock()
    pollution_client.get_air_quality.return_value = AirQualitySnapshot(
        aqi=3,
        pm25=pm25,
        pm10=30.0,
        o3=40.0,
    )

    return WeatherService(
        openmeteo_client=openmeteo_client,
        pollution_client=pollution_client,
    )


def test_hot_day_triggers_cooling(pid_controller: HvacPidController, battery_loop: BatteryCareLoop) -> None:
    """On a hot day the AC cools and the purifier runs on high.

    Simulates a few ticks of a 24-hour-ish loop: outside 35 °C, forecast high
    37 °C / low 22 °C, inside around 28 °C, PM2.5 at 45 µg/m³.
    """
    weather_service = _weather_service(
        temp=35.0,
        humidity=45.0,
        forecast_high=37.0,
        forecast_low=22.0,
        pm25=45.0,
    )
    orchestrator = HvacOrchestrator(
        pid_controller=pid_controller,
        weather_service=weather_service,
        battery_care_loop=battery_loop,
    )

    decisions: list[HvacDecision] = []
    for inside_temp in (28.0, 28.5, 29.0):
        decision = orchestrator.tick(
            inside_temp=inside_temp,
            inside_humidity=45.0,
            battery_level=50,
        )
        decisions.append(decision)

    assert len(decisions) == 3
    assert all(d.ac.mode == "cool" for d in decisions)
    assert all(d.purifier.on is True for d in decisions)
    assert all(d.purifier.preset_mode == "high" for d in decisions)


def test_cold_day_keeps_ac_off(pid_controller: HvacPidController, battery_loop: BatteryCareLoop) -> None:
    """On a cold day the PID controller decides to keep the AC off."""
    weather_service = _weather_service(
        temp=-5.0,
        humidity=60.0,
        forecast_high=5.0,
        forecast_low=-10.0,
        pm25=10.0,
    )
    orchestrator = HvacOrchestrator(
        pid_controller=pid_controller,
        weather_service=weather_service,
        battery_care_loop=battery_loop,
    )

    decision = orchestrator.tick(
        inside_temp=18.0,
        inside_humidity=60.0,
        battery_level=50,
    )

    assert decision.ac.mode == "off"
    assert decision.purifier.on is False
    assert decision.purifier.preset_mode == "auto"


def test_high_pm25_turns_purifier_on(pid_controller: HvacPidController, battery_loop: BatteryCareLoop) -> None:
    """When PM2.5 exceeds the threshold the purifier is turned on high."""
    weather_service = _weather_service(
        temp=24.0,
        humidity=60.0,
        forecast_high=26.0,
        forecast_low=18.0,
        pm25=45.0,
    )
    orchestrator = HvacOrchestrator(
        pid_controller=pid_controller,
        weather_service=weather_service,
        battery_care_loop=battery_loop,
        purifier_pm25_threshold=35,
    )

    decision = orchestrator.tick(
        inside_temp=24.0,
        inside_humidity=60.0,
        battery_level=50,
    )

    assert decision.purifier.on is True
    assert decision.purifier.preset_mode == "high"


def test_battery_cycling_decisions(pid_controller: HvacPidController) -> None:
    """The orchestrator forwards battery-care decisions at the thresholds."""
    weather_service = _weather_service(
        temp=24.0,
        humidity=60.0,
        forecast_high=26.0,
        forecast_low=18.0,
        pm25=10.0,
    )
    battery_loop = BatteryCareLoop(
        config=BatteryCareConfig(upper_threshold=80, lower_threshold=20),
        charge_controller=RelayChargeController(set_relay=lambda _state: None),
        battery_level_source=lambda: 50,
    )
    orchestrator = HvacOrchestrator(
        pid_controller=pid_controller,
        weather_service=weather_service,
        battery_care_loop=battery_loop,
    )

    high = orchestrator.tick(
        inside_temp=24.0, inside_humidity=60.0, battery_level=85
    )
    low = orchestrator.tick(
        inside_temp=24.0, inside_humidity=60.0, battery_level=20
    )
    mid = orchestrator.tick(
        inside_temp=24.0, inside_humidity=60.0, battery_level=50
    )

    assert high.battery.action == "disable"
    assert high.battery.battery_level == 85
    assert low.battery.action == "enable"
    assert low.battery.battery_level == 20
    assert mid.battery.action == "noop"
    assert mid.battery.battery_level == 50


def test_generated_config_contains_all_integrations() -> None:
    """The generated Home Assistant config contains the expected automations."""
    generator = ConfigGenerator(
        latitude=41.9,
        longitude=21.4,
        elevation=240,
        time_zone="Europe/Skopje",
        openweather_api_key="test-key",
    )
    config = generator.generate_configuration()

    automation_ids = {a.get("id") for a in config.automation}
    assert "auto_purifier_high" in automation_ids
    assert "safety_turn_off_ac" in automation_ids

    purifier_automation = next(
        a for a in config.automation if a.get("id") == "auto_purifier_high"
    )
    trigger = purifier_automation["trigger"][0]
    assert trigger["entity_id"] == "sensor.openweathermap_pm25"
    assert trigger["above"] == 35
