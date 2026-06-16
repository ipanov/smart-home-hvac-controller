"""Orchestrate PID, weather, and battery-care into a single HVAC decision."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from smarthvac.battery_care import BatteryCareLoop
from smarthvac.pid_controller import HvacPidController
from smarthvac.weather_client import WeatherService


class AcDecision(BaseModel):
    """AC decision produced by the orchestrator."""

    mode: Literal["cool", "off", "fan_only"]
    target_temperature: int
    fan_mode: Literal["low", "medium", "high"]


class PurifierDecision(BaseModel):
    """Air purifier decision produced by the orchestrator."""

    on: bool
    preset_mode: str


class BatteryDecision(BaseModel):
    """Battery-care decision produced by the orchestrator."""

    action: Literal["enable", "disable", "noop"]
    battery_level: int


class HvacDecision(BaseModel):
    """Combined HVAC decision for one tick."""

    ac: AcDecision
    purifier: PurifierDecision
    battery: BatteryDecision


class HvacOrchestrator:
    """Combine PID controller, weather service, and battery care into decisions.

    Each *tick* fetches a combined weather/air-quality snapshot, runs the PID
    controller against the current indoor conditions, evaluates the purifier
    threshold, and asks the battery-care loop for a charging decision.
    """

    def __init__(
        self,
        pid_controller: HvacPidController,
        weather_service: WeatherService,
        battery_care_loop: BatteryCareLoop,
        purifier_pm25_threshold: float = 35,
    ) -> None:
        """Initialize the orchestrator with its subsystems.

        Args:
            pid_controller: The HVAC PID controller.
            weather_service: Service providing weather and air-quality snapshots.
            battery_care_loop: Battery-care charge-cycling loop.
            purifier_pm25_threshold: PM2.5 level above which the purifier runs
                on high.
        """
        self.pid_controller = pid_controller
        self.weather_service = weather_service
        self.battery_care_loop = battery_care_loop
        self.purifier_pm25_threshold = purifier_pm25_threshold

    def tick(
        self,
        inside_temp: float,
        inside_humidity: float,
        battery_level: int,
    ) -> HvacDecision:
        """Run one orchestration tick.

        Args:
            inside_temp: Current indoor temperature in Celsius.
            inside_humidity: Current indoor relative humidity percentage.
            battery_level: Current battery level (0-100).

        Returns:
            A combined HVAC decision.
        """
        snapshot = self.weather_service.get_combined_snapshot()

        pid_state = self.pid_controller.update(
            inside_temp=inside_temp,
            outside_temp=snapshot.temperature,
            humidity=inside_humidity,
            dt=60.0,
        )

        purifier_on = snapshot.pm25 > self.purifier_pm25_threshold

        battery_decision = self.battery_care_loop.tick(battery_level=battery_level)

        return HvacDecision(
            ac=AcDecision(
                mode=pid_state.mode,
                target_temperature=pid_state.target_temperature,
                fan_mode=pid_state.fan_mode,
            ),
            purifier=PurifierDecision(
                on=purifier_on,
                preset_mode="high" if purifier_on else "auto",
            ),
            battery=BatteryDecision(
                action=battery_decision.action,
                battery_level=battery_decision.battery_level,
            ),
        )
