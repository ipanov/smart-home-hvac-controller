"""20-80% charge cycling logic for the rooted controller phone."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, Field, model_validator


class BatteryCareError(Exception):
    """Raised when battery-care hardware or configuration is unusable."""


class BatteryCareConfig(BaseModel):
    """Configuration for battery-care charge cycling."""

    upper_threshold: int = Field(
        default=80,
        ge=0,
        le=100,
        description="Charge stops when battery level is at or above this value.",
    )
    lower_threshold: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Charge resumes when battery level is at or below this value.",
    )
    check_interval_seconds: int = Field(default=60, gt=0)

    @model_validator(mode="after")
    def _check_threshold_order(self) -> "BatteryCareConfig":
        if self.upper_threshold <= self.lower_threshold:
            raise ValueError(
                f"upper_threshold ({self.upper_threshold}) must be greater than "
                f"lower_threshold ({self.lower_threshold})"
            )
        return self


class ChargeController(ABC):
    """Abstract interface for enabling/disabling battery charging."""

    @abstractmethod
    def enable_charging(self) -> None:
        """Enable battery charging."""

    @abstractmethod
    def disable_charging(self) -> None:
        """Disable battery charging."""

    @abstractmethod
    def is_charging(self) -> bool:
        """Return True if charging is currently enabled."""


class SamsungKernelChargeController(ChargeController):
    """Charge controller using Samsung's batt_slate_mode sysfs node.

    ``1`` disables charging, ``0`` enables charging.
    """

    BATT_SLATE_MODE_PATH: Path = Path(
        "/sys/class/power_supply/battery/batt_slate_mode"
    )

    def __init__(self, path: Path | None = None) -> None:
        self._path = path if path is not None else self.BATT_SLATE_MODE_PATH
        if not self._path.exists():
            raise BatteryCareError(f"Kernel node not found: {self._path}")

    def _write(self, value: int) -> None:
        try:
            self._path.write_text(str(value), encoding="ascii")
        except OSError as exc:
            raise BatteryCareError(
                f"Cannot write to kernel node {self._path}: {exc}"
            ) from exc

    def enable_charging(self) -> None:
        self._write(0)

    def disable_charging(self) -> None:
        self._write(1)

    def is_charging(self) -> bool:
        try:
            raw = self._path.read_text(encoding="ascii").strip()
        except OSError as exc:
            raise BatteryCareError(
                f"Cannot read kernel node {self._path}: {exc}"
            ) from exc
        return raw == "0"


class RelayChargeController(ChargeController):
    """Charge controller backed by an arbitrary relay callback."""

    def __init__(self, set_relay: Callable[[bool], None]) -> None:
        self._set_relay = set_relay
        self._charging = False

    def enable_charging(self) -> None:
        self._set_relay(True)
        self._charging = True

    def disable_charging(self) -> None:
        self._set_relay(False)
        self._charging = False

    def is_charging(self) -> bool:
        return self._charging


class ChargeDecision(BaseModel):
    """Result of a single battery-care tick."""

    action: Literal["enable", "disable", "noop"]
    battery_level: int
    reason: str


class BatteryCareLoop:
    """Evaluates battery level against thresholds and drives a charge controller."""

    def __init__(
        self,
        config: BatteryCareConfig,
        charge_controller: ChargeController,
        battery_level_source: Callable[[], int],
    ) -> None:
        self._config = config
        self._controller = charge_controller
        self._battery_level_source = battery_level_source

    def _get_battery_level(self) -> int:
        level = self._battery_level_source()
        if not isinstance(level, int) or not 0 <= level <= 100:
            raise BatteryCareError(
                f"Invalid battery level: {level!r}; expected int in range 0-100"
            )
        return level

    def tick(self) -> ChargeDecision:
        """Evaluate thresholds and return the charge decision."""
        level = self._get_battery_level()

        if level >= self._config.upper_threshold:
            self._controller.disable_charging()
            return ChargeDecision(
                action="disable",
                battery_level=level,
                reason=(
                    f"Battery level {level}% reached upper threshold "
                    f"{self._config.upper_threshold}%"
                ),
            )

        if level <= self._config.lower_threshold:
            self._controller.enable_charging()
            return ChargeDecision(
                action="enable",
                battery_level=level,
                reason=(
                    f"Battery level {level}% reached lower threshold "
                    f"{self._config.lower_threshold}%"
                ),
            )

        return ChargeDecision(
            action="noop",
            battery_level=level,
            reason=(
                f"Battery level {level}% is within hysteresis zone "
                f"({self._config.lower_threshold}-"
                f"{self._config.upper_threshold})"
            ),
        )
