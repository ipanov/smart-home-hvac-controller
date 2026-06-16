"""Unit tests for battery care logic."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from smarthvac.battery_care import (
    BatteryCareConfig,
    BatteryCareError,
    BatteryCareLoop,
    RelayChargeController,
    SamsungKernelChargeController,
)


def test_disable_at_upper_threshold() -> None:
    """Charging is disabled when the battery reaches the upper threshold."""
    config = BatteryCareConfig(upper_threshold=80, lower_threshold=20)
    controller = Mock(spec=SamsungKernelChargeController)
    loop = BatteryCareLoop(
        config=config,
        charge_controller=controller,
        battery_level_source=lambda: 80,
    )

    decision = loop.tick()

    assert decision.action == "disable"
    assert decision.battery_level == 80
    controller.disable_charging.assert_called_once()
    controller.enable_charging.assert_not_called()


def test_enable_at_lower_threshold() -> None:
    """Charging is enabled when the battery drops to the lower threshold."""
    config = BatteryCareConfig(upper_threshold=80, lower_threshold=20)
    controller = Mock(spec=SamsungKernelChargeController)
    loop = BatteryCareLoop(
        config=config,
        charge_controller=controller,
        battery_level_source=lambda: 20,
    )

    decision = loop.tick()

    assert decision.action == "enable"
    assert decision.battery_level == 20
    controller.enable_charging.assert_called_once()
    controller.disable_charging.assert_not_called()


def test_noop_in_hysteresis_zone() -> None:
    """No action is taken while the battery level is between thresholds."""
    config = BatteryCareConfig(upper_threshold=80, lower_threshold=20)
    controller = Mock(spec=SamsungKernelChargeController)
    loop = BatteryCareLoop(
        config=config,
        charge_controller=controller,
        battery_level_source=lambda: 50,
    )

    decision = loop.tick()

    assert decision.action == "noop"
    assert decision.battery_level == 50
    controller.enable_charging.assert_not_called()
    controller.disable_charging.assert_not_called()


def test_config_validation_upper_below_lower() -> None:
    """upper_threshold must be greater than lower_threshold."""
    with pytest.raises(ValidationError):
        BatteryCareConfig(upper_threshold=20, lower_threshold=80)


def test_config_validation_out_of_range() -> None:
    """Thresholds must be within 0-100."""
    with pytest.raises(ValidationError):
        BatteryCareConfig(upper_threshold=101, lower_threshold=20)

    with pytest.raises(ValidationError):
        BatteryCareConfig(upper_threshold=80, lower_threshold=-1)


def test_kernel_controller_reads_and_writes(tmp_path: Path) -> None:
    """SamsungKernelChargeController reads/writes the batt_slate_mode node."""
    fake_node = tmp_path / "batt_slate_mode"
    fake_node.write_text("0", encoding="ascii")

    controller = SamsungKernelChargeController(path=fake_node)

    assert controller.is_charging() is True

    controller.disable_charging()
    assert fake_node.read_text(encoding="ascii").strip() == "1"
    assert controller.is_charging() is False

    controller.enable_charging()
    assert fake_node.read_text(encoding="ascii").strip() == "0"
    assert controller.is_charging() is True


def test_kernel_controller_missing_node_raises(tmp_path: Path) -> None:
    """A missing sysfs node raises BatteryCareError."""
    missing_node = tmp_path / "missing_batt_slate_mode"

    with pytest.raises(BatteryCareError):
        SamsungKernelChargeController(path=missing_node)


def test_relay_controller_tracks_state() -> None:
    """RelayChargeController forwards commands and tracks the relay state."""
    set_relay = Mock()
    controller = RelayChargeController(set_relay=set_relay)

    assert controller.is_charging() is False

    controller.enable_charging()
    assert controller.is_charging() is True
    set_relay.assert_called_once_with(True)

    controller.disable_charging()
    assert controller.is_charging() is False
    set_relay.assert_called_with(False)


@pytest.mark.parametrize(
    "invalid_level",
    [101, -1, None, "fully charged", 50.5],
)
def test_invalid_battery_level_raises(invalid_level) -> None:
    """Battery level sources outside 0-100 or wrong type raise BatteryCareError."""
    config = BatteryCareConfig(upper_threshold=80, lower_threshold=20)
    controller = Mock(spec=SamsungKernelChargeController)
    loop = BatteryCareLoop(
        config=config,
        charge_controller=controller,
        battery_level_source=lambda: invalid_level,
    )

    with pytest.raises(BatteryCareError):
        loop.tick()
