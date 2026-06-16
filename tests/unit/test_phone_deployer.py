"""Unit tests for the ADB phone deployer."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from smarthvac.phone_deployer import PhoneDeployer


@pytest.fixture
def deployer() -> PhoneDeployer:
    return PhoneDeployer()


def _called_args(mock_run: MagicMock) -> list[str]:
    """Return the positional command list passed to subprocess.run."""
    return list(mock_run.call_args.args[0])


@patch("smarthvac.phone_deployer.subprocess.run")
def test_check_device_parses_output(mock_run: MagicMock, deployer: PhoneDeployer) -> None:
    mock_run.return_value.stdout = (
        "List of devices attached\n"
        "abc123    device\n"
        "xyz789    offline\n"
    )
    mock_run.return_value.returncode = 0

    devices = deployer.check_device()

    assert devices == ["abc123    device", "xyz789    offline"]
    mock_run.assert_called_once()
    assert _called_args(mock_run) == ["adb", "devices"]


@patch("smarthvac.phone_deployer.subprocess.run")
def test_push_project_calls_adb_push(
    mock_run: MagicMock, deployer: PhoneDeployer, tmp_path: Path
) -> None:
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = ""
    project_dir = tmp_path / "home-automation"
    project_dir.mkdir()

    deployer.push_project(project_dir)

    mock_run.assert_called_once()
    assert _called_args(mock_run) == [
        "adb",
        "push",
        str(project_dir),
        f"{deployer.phone_path}/",
    ]


@patch("smarthvac.phone_deployer.subprocess.run")
def test_run_setup_calls_shell(mock_run: MagicMock, deployer: PhoneDeployer) -> None:
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = ""

    deployer.run_setup()

    mock_run.assert_called_once()
    assert _called_args(mock_run) == [
        "adb",
        "shell",
        f"bash {deployer.phone_path}/phone-scripts/termux-setup.sh",
    ]


@patch("smarthvac.phone_deployer.subprocess.run")
def test_enable_battery_care_uses_su(mock_run: MagicMock, deployer: PhoneDeployer) -> None:
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = ""

    deployer.enable_battery_care()

    mock_run.assert_called_once()
    assert _called_args(mock_run) == [
        "adb",
        "shell",
        f"su -c 'sh {deployer.phone_path}/phone-scripts/battery-care.sh'",
    ]
