"""Generate Home Assistant YAML configuration packages."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field


class HaConfig(BaseModel):
    """Entire generated Home Assistant configuration."""

    homeassistant: dict[str, Any]
    mqtt: dict[str, Any]
    logger: dict[str, Any]
    weather: list[dict[str, Any]]
    sensor: list[dict[str, Any]]
    template: list[dict[str, Any]]
    input_number: dict[str, Any]
    automation: list[dict[str, Any]]
    climate: Optional[list[dict[str, Any]]] = Field(default_factory=list)


class _Include(str):
    """YAML scalar that dumps as ``!include <value>``."""


class _IncludeDirNamed(str):
    """YAML scalar that dumps as ``!include_dir_named <value>``."""


class _HaDumper(yaml.SafeDumper):
    """Dumper that knows how to emit HA include tags."""


def _include_representer(dumper: yaml.Dumper, data: _Include) -> yaml.Node:
    return dumper.represent_scalar("!include", str(data))


def _include_dir_named_representer(
    dumper: yaml.Dumper, data: _IncludeDirNamed
) -> yaml.Node:
    return dumper.represent_scalar("!include_dir_named", str(data))


_HaDumper.add_representer(_Include, _include_representer)
_HaDumper.add_representer(_IncludeDirNamed, _include_dir_named_representer)


def _dump_yaml(data: Any, path: Path) -> None:
    """Dump *data* to *path* using the project YAML conventions."""
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            Dumper=_HaDumper,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )


class ConfigGenerator:
    """Render HA automations, sensors, and scripts from templates."""

    def __init__(
        self,
        latitude: float,
        longitude: float,
        elevation: float,
        time_zone: str,
        openweather_api_key: str,
    ) -> None:
        """Initialize generator with location and API credentials."""
        self.latitude = latitude
        self.longitude = longitude
        self.elevation = elevation
        self.time_zone = time_zone
        self.openweather_api_key = openweather_api_key

    def generate_configuration(self) -> HaConfig:
        """Return the complete generated HA configuration model."""
        homeassistant: dict[str, Any] = {
            "name": "SmartHVAC",
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation": self.elevation,
            "unit_system": "metric",
            "time_zone": self.time_zone,
        }
        mqtt: dict[str, Any] = {"broker": "127.0.0.1", "port": 1883}
        logger: dict[str, Any] = {"default": "info"}
        weather: list[dict[str, Any]] = [
            {
                "platform": "open_meteo",
                "name": "Open-Meteo Forecast",
                "latitude": self.latitude,
                "longitude": self.longitude,
            }
        ]
        sensor: list[dict[str, Any]] = [
            {
                "platform": "openweathermap",
                "api_key": self.openweather_api_key,
                "latitude": self.latitude,
                "longitude": self.longitude,
                "monitored_conditions": ["air_quality_index"],
            }
        ]
        template: list[dict[str, Any]] = [
            {
                "sensor": [
                    {
                        "name": "Outside Temperature",
                        "unique_id": "outside_temperature",
                        "state": (
                            "{{ state_attr('weather.open_meteo_forecast', "
                            "'temperature') }}"
                        ),
                        "unit_of_measurement": "°C",
                    },
                    {
                        "name": "Outside Humidity",
                        "unique_id": "outside_humidity",
                        "state": (
                            "{{ state_attr('weather.open_meteo_forecast', "
                            "'humidity') }}"
                        ),
                        "unit_of_measurement": "%",
                    },
                    {
                        "name": "Weather Forecast High",
                        "unique_id": "weather_forecast_high",
                        "state": (
                            "{{ state_attr('weather.open_meteo_forecast', "
                            "'temperature') | float(0) + 5 }}"
                        ),
                        "unit_of_measurement": "°C",
                    },
                ]
            }
        ]
        input_number: dict[str, Any] = {
            "hvac_target_temperature": {
                "name": "HVAC Target Temperature",
                "min": 16,
                "max": 30,
                "step": 0.5,
                "initial": 24,
            },
            "hvac_kp": {
                "name": "HVAC Kp",
                "min": 0,
                "max": 100,
                "step": 0.1,
                "initial": 1.0,
            },
            "hvac_ki": {
                "name": "HVAC Ki",
                "min": 0,
                "max": 100,
                "step": 0.01,
                "initial": 0.1,
            },
            "hvac_kd": {
                "name": "HVAC Kd",
                "min": 0,
                "max": 100,
                "step": 0.1,
                "initial": 0.5,
            },
        }
        automation: list[dict[str, Any]] = [
            {
                "id": "safety_turn_off_ac",
                "alias": "Turn off AC if inside temperature below 18°C",
                "trigger": [
                    {
                        "platform": "numeric_state",
                        "entity_id": "sensor.inside_temperature",
                        "below": 18,
                    }
                ],
                "action": [
                    {
                        "service": "climate.turn_off",
                        "target": {"entity_id": "climate.ac_unit"},
                    }
                ],
            },
            {
                "id": "auto_purifier_high",
                "alias": "Turn purifier to high when PM2.5 above 35",
                "trigger": [
                    {
                        "platform": "numeric_state",
                        "entity_id": "sensor.openweathermap_pm25",
                        "above": 35,
                    }
                ],
                "action": [
                    {
                        "service": "fan.set_percentage",
                        "target": {"entity_id": "fan.purifier"},
                        "data": {"percentage": 100},
                    }
                ],
            },
        ]
        climate: list[dict[str, Any]] = []

        return HaConfig(
            homeassistant=homeassistant,
            mqtt=mqtt,
            logger=logger,
            weather=weather,
            sensor=sensor,
            template=template,
            input_number=input_number,
            automation=automation,
            climate=climate,
        )

    def write_configs(self, output_dir: str) -> None:
        """Write the generated config to *output_dir* as HA YAML files."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        packages_dir = output_path / "packages"
        packages_dir.mkdir(exist_ok=True)

        config = self.generate_configuration()
        config_dict = config.model_dump(exclude_none=True)

        ordered_config: dict[str, Any] = {
            "homeassistant": {
                **config_dict["homeassistant"],
                "packages": _IncludeDirNamed("packages"),
            },
            "mqtt": config_dict["mqtt"],
            "logger": config_dict["logger"],
            "weather": config_dict["weather"],
            "sensor": config_dict["sensor"],
            "automation": _Include("automations.yaml"),
            "climate": config_dict.get("climate", []),
        }

        config_path = output_path / "configuration.yaml"
        with config_path.open("w", encoding="utf-8") as f:
            f.write("default_config:\n\n")
            yaml.dump(
                ordered_config,
                f,
                Dumper=_HaDumper,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

        _dump_yaml(config_dict["automation"], output_path / "automations.yaml")
        _dump_yaml(
            {"openweather_api_key": self.openweather_api_key},
            output_path / "secrets.yaml",
        )
        _dump_yaml(
            {"input_number": config_dict["input_number"]},
            packages_dir / "hvac_pid.yaml",
        )
        _dump_yaml(
            {"template": config_dict["template"]},
            packages_dir / "weather_feedforward.yaml",
        )

        battery_care: dict[str, Any] = {
            "automation": [
                {
                    "id": "battery_care_report",
                    "alias": "Report battery care status",
                    "trigger": [
                        {"platform": "time_pattern", "minutes": "/5"}
                    ],
                    "condition": [
                        {
                            "condition": "or",
                            "conditions": [
                                {
                                    "condition": "numeric_state",
                                    "entity_id": "sensor.phone_battery_level",
                                    "above": 80,
                                },
                                {
                                    "condition": "numeric_state",
                                    "entity_id": "sensor.phone_battery_level",
                                    "below": 20,
                                },
                            ],
                        }
                    ],
                    "action": [
                        {
                            "service": "notify.mobile_app_sm_g950f",
                            "data": {
                                "message": (
                                    "Battery care alert: "
                                    "{{ states('sensor.phone_battery_level') }}%"
                                )
                            },
                        }
                    ],
                }
            ]
        }
        _dump_yaml(battery_care, packages_dir / "battery_care.yaml")
