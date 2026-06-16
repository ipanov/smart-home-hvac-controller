"""PID controller with weather feedforward and humidity compensation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


OUTSIDE_TEMP_FEEDFORWARD_BASE: float = 24.0
HUMIDITY_COMPENSATION_BASE: float = 60.0
COOL_THRESHOLD: float = 0.5
OFF_THRESHOLD: float = -0.5
HIGH_FAN_THRESHOLD: float = 1.0
MIN_TARGET_TEMP: int = 16
MAX_TARGET_TEMP: int = 30
MIN_VALID_TEMP: float = -50.0
MAX_VALID_TEMP: float = 80.0


class PidState(BaseModel):
    """Output state of the HVAC PID controller."""

    mode: Literal["cool", "off", "fan_only"] = Field(
        ..., description="Active HVAC mode decided by the PID output."
    )
    target_temperature: int = Field(
        ..., description="Rounded and clamped target temperature in Celsius."
    )
    fan_mode: Literal["low", "medium", "high"] = Field(
        ..., description="Fan speed selected from the PID output magnitude."
    )
    adjusted_target: float = Field(
        ..., description="Target temperature after weather and humidity adjustments."
    )
    pid_output: float = Field(..., description="Raw PID controller output.")


class PidInputs(BaseModel):
    """Validated inputs for a controller update."""

    inside_temp: float = Field(
        ..., ge=MIN_VALID_TEMP, le=MAX_VALID_TEMP, description="Indoor temperature in Celsius."
    )
    outside_temp: float = Field(
        ..., ge=MIN_VALID_TEMP, le=MAX_VALID_TEMP, description="Outdoor temperature in Celsius."
    )
    humidity: float = Field(
        ..., ge=0.0, le=100.0, description="Relative humidity percentage."
    )
    dt: float = Field(..., gt=0.0, description="Elapsed time since last update in seconds.")


class HvacPidController:
    """PID-based HVAC controller with optional feedforward terms."""

    def __init__(
        self,
        kp: float = 0.5,
        ki: float = 0.05,
        kd: float = 0.2,
        target_temp: float = 24.0,
        deadband: float = 0.5,
        windup_limit: float = 10.0,
    ) -> None:
        """Initialize controller gains and state.

        Args:
            kp: Proportional gain.
            ki: Integral gain.
            kd: Derivative gain.
            target_temp: Desired indoor temperature in Celsius.
            deadband: Deadband around the setpoint where only fan runs.
            windup_limit: Maximum absolute value for the integral accumulator.
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.target_temp = target_temp
        self.deadband = deadband
        self.windup_limit = windup_limit

        self._integral: float = 0.0
        self._last_error: float | None = None

    def update(
        self,
        inside_temp: float,
        outside_temp: float,
        humidity: float,
        dt: float = 60.0,
    ) -> PidState:
        """Compute the next controller state.

        Args:
            inside_temp: Current indoor temperature in Celsius.
            outside_temp: Current outdoor temperature in Celsius.
            humidity: Current relative humidity percentage.
            dt: Elapsed time since the last update in seconds.

        Returns:
            A PidState containing the chosen mode, fan speed, and diagnostics.
        """
        inputs = PidInputs(
            inside_temp=inside_temp,
            outside_temp=outside_temp,
            humidity=humidity,
            dt=dt,
        )

        feedforward = 0.04 * max(
            0.0, inputs.outside_temp - OUTSIDE_TEMP_FEEDFORWARD_BASE
        )
        humidity_compensation = -0.02 * max(
            0.0, HUMIDITY_COMPENSATION_BASE - inputs.humidity
        )
        adjusted_target = self.target_temp + feedforward + humidity_compensation

        error = inputs.inside_temp - adjusted_target

        self._integral += error * inputs.dt
        self._integral = max(
            -self.windup_limit, min(self.windup_limit, self._integral)
        )

        if self._last_error is None:
            derivative = 0.0
        else:
            derivative = (error - self._last_error) / inputs.dt

        if inputs.dt > 0:
            self._last_error = error

        pid_output = (
            self.kp * error + self.ki * self._integral + self.kd * derivative
        )

        if abs(error) <= self.deadband:
            mode = "fan_only"
            fan_mode = "low"
        elif pid_output > COOL_THRESHOLD:
            mode = "cool"
            fan_mode = "high" if pid_output > HIGH_FAN_THRESHOLD else "medium"
        elif pid_output < OFF_THRESHOLD:
            mode = "off"
            fan_mode = "low"
        else:
            mode = "fan_only"
            fan_mode = "low"

        target_temperature = round(adjusted_target)
        target_temperature = max(
            MIN_TARGET_TEMP, min(MAX_TARGET_TEMP, target_temperature)
        )

        return PidState(
            mode=mode,
            target_temperature=target_temperature,
            fan_mode=fan_mode,
            adjusted_target=adjusted_target,
            pid_output=pid_output,
        )

    def reset(self) -> None:
        """Clear integral and last error state."""
        self._integral = 0.0
        self._last_error = None
