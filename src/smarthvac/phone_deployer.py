"""ADB-based deployment orchestrator for the Home Assistant controller phone."""

from __future__ import annotations

import logging
import subprocess
import webbrowser
from pathlib import Path

_logger = logging.getLogger(__name__)


class PhoneDeployer:
    """Orchestrate ADB commands to deploy the home-automation stack to a phone."""

    TERMUX_FDROID_URL = "https://f-droid.org/packages/com.termux/"

    def __init__(self, phone_path: str = "/data/data/com.termux/files/home/home-automation") -> None:
        self.phone_path = phone_path

    def _run(self, command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        """Run a command and return the completed process."""
        _logger.info("Running command: %s", " ".join(command))
        return subprocess.run(
            command,
            check=check,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def check_device(self) -> list[str]:
        """List connected ADB devices and return non-header lines."""
        result = self._run(["adb", "devices"])
        lines = result.stdout.strip().splitlines()
        # Skip the first "List of devices attached" header line.
        return lines[1:] if lines else []

    def push_project(self, local_path: str | Path) -> subprocess.CompletedProcess[str]:
        """Push the local project directory to the phone."""
        src = Path(local_path)
        if not src.exists():
            raise FileNotFoundError(f"Project path not found: {src}")
        return self._run(["adb", "push", str(src), f"{self.phone_path}/"])

    def install_termux(self) -> None:
        """Open the Termux F-Droid page in the default browser."""
        _logger.info("Opening Termux F-Droid page: %s", self.TERMUX_FDROID_URL)
        webbrowser.open(self.TERMUX_FDROID_URL)

    def run_setup(self) -> subprocess.CompletedProcess[str]:
        """Run the Termux setup script on the phone."""
        script_path = f"{self.phone_path}/phone-scripts/termux-setup.sh"
        return self._run(["adb", "shell", f"bash {script_path}"])

    def start_home_assistant(self) -> subprocess.CompletedProcess[str]:
        """Start Home Assistant via the phone start script."""
        script_path = f"{self.phone_path}/phone-scripts/start-ha.sh"
        return self._run(["adb", "shell", f"bash {script_path}"])

    def enable_battery_care(self) -> subprocess.CompletedProcess[str]:
        """Run the battery care script as root on the phone."""
        script_path = f"{self.phone_path}/phone-scripts/battery-care.sh"
        return self._run(["adb", "shell", f"su -c 'sh {script_path}'"])
