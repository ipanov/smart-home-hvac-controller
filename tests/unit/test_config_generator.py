"""Unit tests for HA config generator."""

from pathlib import Path

import pytest
import yaml

from smarthvac.config_generator import ConfigGenerator, HaConfig


@pytest.fixture(autouse=True)
def _register_ha_yaml_tags() -> None:
    """Allow yaml.safe_load to parse HA include tags as plain strings."""

    def _constructor(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> str:
        return str(loader.construct_scalar(node))

    for tag in ("!include", "!include_dir_named"):
        yaml.SafeLoader.add_constructor(tag, _constructor)


def test_configuration_yaml_has_required_keys(tmp_path: Path) -> None:
    """configuration.yaml contains every top-level key HA expects."""
    generator = ConfigGenerator(41.9, 21.4, 240, "Europe/Skopje", "test-api-key")
    generator.write_configs(tmp_path)

    config = yaml.safe_load((tmp_path / "configuration.yaml").read_text())

    required = {
        "default_config",
        "homeassistant",
        "mqtt",
        "logger",
        "weather",
        "sensor",
        "automation",
        "climate",
    }
    assert required.issubset(config.keys())


def test_secrets_yaml_contains_api_key(tmp_path: Path) -> None:
    """secrets.yaml stores the OpenWeatherMap API key."""
    generator = ConfigGenerator(
        41.9, 21.4, 240, "Europe/Skopje", "super-secret-key"
    )
    generator.write_configs(tmp_path)

    secrets = yaml.safe_load((tmp_path / "secrets.yaml").read_text())

    assert secrets.get("openweather_api_key") == "super-secret-key"


def test_automations_list_not_empty(tmp_path: Path) -> None:
    """automations.yaml is a non-empty list with the required automations."""
    generator = ConfigGenerator(41.9, 21.4, 240, "Europe/Skopje", "test-key")
    generator.write_configs(tmp_path)

    automations = yaml.safe_load((tmp_path / "automations.yaml").read_text())

    assert isinstance(automations, list)
    assert len(automations) > 0
    assert any(a.get("id") == "safety_turn_off_ac" for a in automations)
    assert any(a.get("id") == "auto_purifier_high" for a in automations)


def test_packages_directory_created(tmp_path: Path) -> None:
    """write_configs creates the packages directory and its files."""
    generator = ConfigGenerator(41.9, 21.4, 240, "Europe/Skopje", "test-key")
    generator.write_configs(tmp_path)

    packages_dir = tmp_path / "packages"
    assert packages_dir.is_dir()
    assert (packages_dir / "hvac_pid.yaml").is_file()
    assert (packages_dir / "weather_feedforward.yaml").is_file()
    assert (packages_dir / "battery_care.yaml").is_file()


def test_weather_integration_configured() -> None:
    """The generated config contains Open-Meteo and OpenWeatherMap entries."""
    generator = ConfigGenerator(41.9, 21.4, 240, "Europe/Skopje", "test-key")
    config = generator.generate_configuration()

    assert any(w.get("platform") == "open_meteo" for w in config.weather)
    assert any(s.get("platform") == "openweathermap" for s in config.sensor)


def test_input_numbers_within_range() -> None:
    """PID helpers and target temperature input_numbers are within bounds."""
    generator = ConfigGenerator(41.9, 21.4, 240, "Europe/Skopje", "test-key")
    config = generator.generate_configuration()

    target = config.input_number["hvac_target_temperature"]
    assert target["min"] == 16
    assert target["max"] == 30
    assert target["initial"] == 24

    for name in ("hvac_kp", "hvac_ki", "hvac_kd"):
        pid = config.input_number[name]
        assert pid["min"] >= 0
        assert pid["max"] <= 100


def test_round_trip_yaml_loadable(tmp_path: Path) -> None:
    """Every generated YAML file can be loaded back with yaml.safe_load."""
    generator = ConfigGenerator(41.9, 21.4, 240, "Europe/Skopje", "test-key")
    generator.write_configs(tmp_path)

    files = [
        tmp_path / "configuration.yaml",
        tmp_path / "automations.yaml",
        tmp_path / "secrets.yaml",
        tmp_path / "packages" / "hvac_pid.yaml",
        tmp_path / "packages" / "weather_feedforward.yaml",
        tmp_path / "packages" / "battery_care.yaml",
    ]

    for path in files:
        data = yaml.safe_load(path.read_text())
        assert data is not None


def test_ha_config_model_validates_full_config() -> None:
    """HaConfig accepts the structure produced by ConfigGenerator."""
    generator = ConfigGenerator(41.9, 21.4, 240, "Europe/Skopje", "test-key")
    config = generator.generate_configuration()

    assert isinstance(config, HaConfig)
    assert config.homeassistant["time_zone"] == "Europe/Skopje"
    assert config.mqtt["broker"] == "127.0.0.1"
    assert config.mqtt["port"] == 1883
