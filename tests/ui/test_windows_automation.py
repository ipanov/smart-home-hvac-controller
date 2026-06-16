"""Real UI tests for the Windows desktop automation wrapper.

These tests launch real Windows applications (Notepad and Calculator) and
interact with them via ``pywinauto``. They are marked with ``@pytest.mark.ui``
and are skipped automatically on headless/CI runners where no interactive
desktop session is available.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import time
from contextlib import contextmanager

import pytest

from smarthvac.desktop_automation import WindowsAutomation


pytestmark = pytest.mark.ui

_probe_result: bool | None = None


def _probe_desktop_interactivity() -> bool:
    """Quickly probe whether pywinauto can start and connect to a GUI app.

    Returns True if a real interactive desktop session is available and
    pywinauto can successfully launch and interact with Notepad. The probe uses
    a separate process with a short timeout so it cannot hang the test suite.
    """
    global _probe_result
    if _probe_result is not None:
        return _probe_result

    probe_script = (
        "import sys\n"
        "from pywinauto import Application\n"
        "try:\n"
        "    app = Application(backend='uia').start('notepad.exe')\n"
        "    window = app.top_window()\n"
        "    window.wait('visible', timeout=5)\n"
        "    window.type_keys('probe', with_spaces=True)\n"
        "    window.close()\n"
        "    print('OK')\n"
        "except Exception as exc:\n"
        "    print('FAIL', exc)\n"
        "    sys.exit(1)\n"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", probe_script],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if result.returncode == 0 and "OK" in result.stdout:
            _probe_result = True
            return True
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass

    # Cleanup any notepad left behind by a failed probe.
    try:
        subprocess.run(
            ["powershell.exe", "-Command", "Get-Process notepad -ErrorAction SilentlyContinue | Stop-Process -Force"],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass

    _probe_result = False
    return False


def _should_skip_ui() -> bool:
    """Return True if the current environment cannot run UI tests."""
    if platform.system() != "Windows":
        return True
    if os.environ.get("CI") or os.environ.get("SKIP_UI_TESTS"):
        return True
    if os.environ.get("GITHUB_ACTIONS"):
        return True
    if not _probe_desktop_interactivity():
        return True
    return False


UI_SKIP_REASON = (
    "UI tests require an interactive Windows desktop session. "
    "Set SKIP_UI_TESTS=1 to suppress this message."
)


@contextmanager
def _open_app(app_name: str):
    """Launch a Windows app and ensure it is closed on exit."""
    auto = WindowsAutomation(app_name, backend="uia")
    try:
        auto.launch(wait_for_window=True, timeout=15)
        yield auto
    finally:
        try:
            auto.close_window(discard_changes=True)
        except Exception:
            pass
        # Fallback: terminate any lingering process.
        try:
            if auto._app is not None:
                auto._app.kill()
        except Exception:
            pass


@pytest.mark.skipif(_should_skip_ui(), reason=UI_SKIP_REASON)
def test_notepad_typing():
    """Launch Notepad, type text, and verify it appears in the document."""
    with _open_app("notepad.exe") as auto:
        # Focus the document/editor and type the expected text.
        auto.type_text("Smart HVAC", clear_first=True)

        # Allow the UI to settle before reading the value back.
        time.sleep(0.5)

        # Modern Notepad exposes the editor as a Document or Edit control.
        doc = None
        for control_type in ("Document", "Edit"):
            candidate = auto._main_window.child_window(control_type=control_type)
            try:
                candidate.wait("visible", timeout=2)
                doc = candidate
                break
            except Exception:
                continue

        if doc is None:
            pytest.skip("Could not locate Notepad editor control")

        text = doc.window_text()
        assert "Smart HVAC" in text, f"Expected 'Smart HVAC' in Notepad text, got: {text!r}"


@pytest.mark.skipif(_should_skip_ui(), reason=UI_SKIP_REASON)
def test_calculator_basic_math():
    """Launch Calculator and verify that 2 + 2 equals 4.

    This test is skipped if Calculator cannot be automated on the current
    Windows version (e.g. older Windows 10 builds or unusual display scales).
    """
    with _open_app("calc.exe") as auto:
        # Use keyboard shortcuts/keystrokes which are more robust than hunting
        # for button names across locales and calculator modes.
        auto._main_window.type_keys("2{+}2{=}")
        time.sleep(1.0)

        try:
            display = auto._main_window.child_window(auto_id="CalculatorResults")
            display.wait("visible", timeout=10)
            result_text = display.window_text()
        except Exception as exc:
            pytest.skip(f"Calculator UI automation is not available on this system: {exc}")

        assert "4" in result_text, f"Expected result to contain '4', got: {result_text!r}"
