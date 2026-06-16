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
    """Repeated large-error updates produce a stable, saturated cooling output."""
    outputs: list[float] = []
    for _ in range(10):
        state = controller.update(inside_temp=50.0, outside_temp=24.0, humidity=60.0)
        outputs.append(state.pid_output)

    # Once saturated, further identical updates do not change the output.
    assert outputs[-1] == pytest.approx(outputs[-2])
    assert state.mode == "cool"


def test_target_temperature_clamped() -> None:
    """Rounded target temperature is always within the 16-30 range."""
    high_controller = HvacPidController(target_temp=30.0)
    extreme_high = high_controller.update(
        inside_temp=30.0, outside_temp=80.0, humidity=60.0
    )
    assert extreme_high.target_temperature == 30

    low_controller = HvacPidController(target_temp=10.0)
    extreme_low = low_controller.update(
        inside_temp=10.0, outside_temp=-50.0, humidity=60.0
    )
    assert extreme_low.target_temperature == 16


def test_target_temperature_is_int(controller: HvacPidController) -> None:
    """PidState target_temperature is an integer."""
    state = controller.update(inside_temp=24.0, outside_temp=24.0, humidity=60.0)

    assert isinstance(state.target_temperature, int)


def test_reset_restores_response(controller: HvacPidController) -> None:
    """After reset, the controller responds identically to the same input."""
    first = controller.update(inside_temp=28.0, outside_temp=24.0, humidity=60.0)

    controller.reset()

    second = controller.update(inside_temp=28.0, outside_temp=24.0, humidity=60.0)

    assert first == second


def test_fan_speed_proportional(controller: HvacPidController) -> None:
    """Large errors drive high fan; smaller cooling errors drive medium fan."""
    high = controller.update(inside_temp=28.0, outside_temp=24.0, humidity=60.0)
    controller.reset()
    medium = controller.update(inside_temp=25.0, outside_temp=24.0, humidity=60.0)

    assert high.fan_mode == "high"
    assert medium.fan_mode == "medium"
    assert 0.5 < medium.pid_output <= 1.0


def test_deadband_keeps_fan_only(controller: HvacPidController) -> None:
    """When the error is within the deadband the controller stays in fan_only."""
    # Set gains so output magnitude depends only on a small error.
    controller.kp = 1.0
    controller.ki = 0.0
    controller.kd = 0.0

    state = controller.update(inside_temp=24.2, outside_temp=24.0, humidity=60.0)

    assert abs(state.pid_output) <= controller.deadband
    assert state.mode == "fan_only"
    assert state.fan_mode == "low"


def test_fan_mode_boundaries(controller: HvacPidController) -> None:
    """Fan mode transitions occur at the defined PID output thresholds."""
    controller.kp = 1.0
    controller.ki = 0.0
    controller.kd = 0.0

    just_below_cool = controller.update(inside_temp=24.4, outside_temp=24.0, humidity=60.0)
    assert just_below_cool.mode == "fan_only"
    assert just_below_cool.fan_mode == "low"

    controller.reset()
    just_above_cool = controller.update(inside_temp=24.6, outside_temp=24.0, humidity=60.0)
    assert just_above_cool.mode == "cool"
    assert just_above_cool.fan_mode == "medium"

    controller.reset()
    just_below_high = controller.update(inside_temp=24.9, outside_temp=24.0, humidity=60.0)
    assert just_below_high.mode == "cool"
    assert just_below_high.fan_mode == "medium"

    controller.reset()
    just_above_high = controller.update(inside_temp=25.1, outside_temp=24.0, humidity=60.0)
    assert just_above_high.mode == "cool"
    assert just_above_high.fan_mode == "high"


def test_dt_used_for_integral_and_derivative(controller: HvacPidController) -> None:
    """A smaller dt produces a smaller integral growth and larger derivative."""
    state_short = controller.update(
        inside_temp=26.0, outside_temp=24.0, humidity=60.0, dt=1.0
    )
    controller.reset()
    state_long = controller.update(
        inside_temp=26.0, outside_temp=24.0, humidity=60.0, dt=60.0
    )

    assert state_long.pid_output > state_short.pid_output


@pytest.mark.parametrize(
    "kwargs",
    [
        {"inside_temp": -60.0, "outside_temp": 24.0, "humidity": 60.0},
        {"inside_temp": 90.0, "outside_temp": 24.0, "humidity": 60.0},
        {"inside_temp": 24.0, "outside_temp": -60.0, "humidity": 60.0},
        {"inside_temp": 24.0, "outside_temp": 90.0, "humidity": 60.0},
        {"inside_temp": 24.0, "outside_temp": 24.0, "humidity": -1.0},
        {"inside_temp": 24.0, "outside_temp": 24.0, "humidity": 110.0},
        {"inside_temp": 24.0, "outside_temp": 24.0, "humidity": 60.0, "dt": 0.0},
        {"inside_temp": 24.0, "outside_temp": 24.0, "humidity": 60.0, "dt": -5.0},
    ],
)
def test_invalid_inputs_raise(controller: HvacPidController, kwargs: dict) -> None:
    """Out-of-range inputs are rejected."""
    with pytest.raises(ValueError):
        controller.update(**kwargs)
