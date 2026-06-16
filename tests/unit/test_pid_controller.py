"""Unit tests for PID controller."""

import pytest

from smarthvac.pid_controller import HvacPidController, PidState


@pytest.fixture
def controller() -> HvacPidController:
    """Return a fresh controller with default tuning."""
    return HvacPidController()


def test_cool_when_too_hot(controller: HvacPidController) -> None:
    """A hot indoor temperature should trigger cooling."""
    state = controller.update(inside_temp=28.0, outside_temp=24.0, humidity=60.0)

    assert isinstance(state, PidState)
    assert state.mode == "cool"
    assert state.pid_output > 0.5


def test_off_when_too_cold(controller: HvacPidController) -> None:
    """A cold indoor temperature should keep the HVAC off."""
    state = controller.update(inside_temp=20.0, outside_temp=24.0, humidity=60.0)

    assert state.mode == "off"
    assert state.pid_output < -0.5


def test_feedforward_raises_target(controller: HvacPidController) -> None:
    """Higher outside temperature increases the adjusted target."""
    hot_day = controller.update(inside_temp=24.0, outside_temp=35.0, humidity=60.0)
    controller.reset()
    cool_day = controller.update(inside_temp=24.0, outside_temp=20.0, humidity=60.0)

    assert hot_day.adjusted_target > cool_day.adjusted_target
    assert hot_day.adjusted_target == pytest.approx(24.44)
    assert cool_day.adjusted_target == pytest.approx(24.0)


def test_humidity_compensation(controller: HvacPidController) -> None:
    """Low humidity lowers the effective target temperature."""
    dry = controller.update(inside_temp=24.0, outside_temp=24.0, humidity=30.0)
    controller.reset()
    normal = controller.update(inside_temp=24.0, outside_temp=24.0, humidity=60.0)

    assert dry.adjusted_target < normal.adjusted_target
    assert dry.adjusted_target == pytest.approx(23.4)
    assert normal.adjusted_target == pytest.approx(24.0)


def test_windup_limit(controller: HvacPidController) -> None:
    """The integral term clamps at the configured windup limit."""
    for _ in range(10):
        state = controller.update(inside_temp=50.0, outside_temp=24.0, humidity=60.0)

    # Internal integral is capped at +windup_limit.
    assert controller._integral == pytest.approx(controller.windup_limit)
    assert state.mode == "cool"


def test_target_temperature_clamped(controller: HvacPidController) -> None:
    """Rounded target temperature is always within the 16-30 range."""
    extreme = controller.update(inside_temp=24.0, outside_temp=200.0, humidity=60.0)

    assert extreme.target_temperature <= 30.0
    assert extreme.target_temperature == 30.0


def test_reset_clears_state(controller: HvacPidController) -> None:
    """Reset clears the integral and last error."""
    controller.update(inside_temp=28.0, outside_temp=24.0, humidity=60.0)
    assert controller._integral != 0.0
    assert controller._last_error is not None

    controller.reset()
    assert controller._integral == 0.0
    assert controller._last_error is None


def test_fan_speed_proportional(controller: HvacPidController) -> None:
    """Large errors drive high fan; smaller cooling errors drive medium fan."""
    high = controller.update(inside_temp=28.0, outside_temp=24.0, humidity=60.0)
    controller.reset()
    medium = controller.update(inside_temp=25.0, outside_temp=24.0, humidity=60.0)

    assert high.fan_mode == "high"
    assert medium.fan_mode == "medium"
    assert 0.5 < medium.pid_output <= 1.0
