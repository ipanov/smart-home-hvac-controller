"""PID controller with weather feedforward and humidity compensation."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


class PidState(BaseModel):
    """Output state of the HVAC PID controller."""

    mode: Literal["cool", "off", "fan_only"] = Field(
        ..., description="Active HVAC mode decided by the PID output."
    )
    target_temperature: float = Field(
        ..., description="Rounded and clamped target temperature in Celsius."
    )
    fan_mode: Literal["low", "medium", "high"] = Field(
        ..., description="Fan speed selected from the PID output magnitude."
    )
    adjusted_target: float = Field(
        ..., description="Target temperature after weather and humidity adjustments."
    )
    pid_output: float = Field(..., description="Raw PID controller output.")


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
            deadband: Unused deadband around the setpoint.
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
        self, inside_temp: float, outside_temp: float, humidity: float
    ) -> PidState:
        """Compute the next controller state.

        Args:
            inside_temp: Current indoor temperature in Celsius.
            outside_temp: Current outdoor temperature in Celsius.
            humidity: Current relative humidity percentage.

        Returns:
            A PidState containing the chosen mode, fan speed, and diagnostics.
        """
        feedforward = 0.04 * max(0.0, outside_temp - 24.0)
        humidity_compensation = -0.02 * max(0.0, 60.0 - humidity)
        adjusted_target = self.target_temp + feedforward + humidity_compensation

        error = inside_temp - adjusted_target

        self._integral += error
        self._integral = max(-self.windup_limit, min(self.windup_limit, self._integral))

        if self._last_error is None:
            derivative = 0.0
        else:
            derivative = error - self._last_error
        self._last_error = error

        pid_output = self.kp * error + self.ki * self._integral + self.kd * derivative

        if pid_output > 0.5:
            mode = "cool"
            fan_mode = "high" if pid_output > 1.0 else "medium"
        elif pid_output < -0.5:
            mode = "off"
            fan_mode = "low"
        else:
            mode = "fan_only"
            fan_mode = "low"

        target_temperature = round(adjusted_target)
        target_temperature = max(16, min(30, target_temperature))

        return PidState(
            mode=mode,
            target_temperature=float(target_temperature),
            fan_mode=fan_mode,
            adjusted_target=adjusted_target,
            pid_output=pid_output,
        )

    def reset(self) -> None:
        """Clear integral and last error state."""
        self._integral = 0.0
        self._last_error = None
