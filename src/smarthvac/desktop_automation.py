"""Windows UI automation helpers for desktop interaction.

This module provides wrappers around pywinauto for controlling Windows desktop
applications, plus helpers for Chocolatey package installation, ADB-based Android
device setup, and a Playwright-based Home Assistant onboarding stub.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Any


try:
    from pywinauto import Desktop, Application
    from pywinauto.findwindows import ElementNotFoundError
except ImportError as exc:  # pragma: no cover - handled gracefully at runtime
    Application = None
    Desktop = None
    ElementNotFoundError = Exception
    _IMPORT_ERROR = exc


class WindowsAutomation:
    """Wrap ``pywinauto`` helpers for controlling a Windows application."""

    def __init__(self, app_name_or_path: str, backend: str = "uia"):
        """Initialize automation backend for the target application.

        Args:
            app_name_or_path: Executable name (e.g. ``notepad.exe``) or full path.
            backend: ``pywinauto`` backend to use (``win32`` or ``uia``). UIA is
                the default because it supports both classic and UWP apps.
        """
        if Application is None:
            raise RuntimeError("pywinauto is not installed") from _IMPORT_ERROR

        self.app_name_or_path = app_name_or_path
        self.backend = backend
        self._app: Any | None = None
        self._main_window: Any | None = None

    def launch(self, wait_for_window: bool = True, timeout: int = 10) -> Any:
        """Launch the application and return its ``Application`` object.

        Args:
            wait_for_window: If ``True``, block until the main window exists.
            timeout: Seconds to wait for the main window.

        Returns:
            The started ``pywinauto.Application`` instance.
        """
        self._app = Application(backend=self.backend).start(self.app_name_or_path)
        if wait_for_window:
            self._main_window = self.find_window()
            self._main_window.wait("visible", timeout=timeout)
        return self._app

    def find_window(self, title_re: str | None = None, class_name: str | None = None) -> Any:
        """Return a ``WindowSpecification`` matching the given criteria.

        If no criteria are supplied, returns the top-level window of the
        launched application.

        Args:
            title_re: Regular expression matched against the window title.
            class_name: Windows class name of the target window.

        Returns:
            A ``pywinauto.WindowSpecification``.
        """
        if self._app is None:
            raise RuntimeError("Application has not been launched. Call launch() first.")

        kwargs: dict[str, Any] = {}
        if title_re:
            kwargs["title_re"] = title_re
        if class_name:
            kwargs["class_name"] = class_name

        if kwargs:
            window = self._app.window(**kwargs)
        else:
            window = self._app.top_window()

        self._main_window = window
        return window

    def click_button(self, name: str) -> None:
        """Click a button inside the main window by its accessible name.

        Args:
            name: The visible/accessible name of the button (e.g. ``"OK"``).
        """
        window = self._ensure_window()
        button = window.child_window(control_type="Button", name=name)
        button.wait("visible", timeout=10)
        button.click_input()

    def type_text(self, text: str, control_name: str | None = None, clear_first: bool = False) -> None:
        """Type text into the main window or a named control.

        Args:
            text: Text to type.
            control_name: Optional accessible name of the target edit/document
                control. If omitted, text is sent to the main window.
            clear_first: If ``True``, clear the target control before typing.
        """
        window = self._ensure_window()

        if control_name:
            control = window.child_window(control_type="Edit", name=control_name)
            try:
                control.wait("visible", timeout=5)
            except Exception:
                control = window.child_window(control_type="Document", name=control_name)
                control.wait("visible", timeout=5)

            if clear_first:
                control.type_keys("^a{DELETE}")
            control.type_keys(text, with_spaces=True)
        else:
            if clear_first:
                window.type_keys("^a{DELETE}")
            window.type_keys(text, with_spaces=True)

    def close_window(self, discard_changes: bool = False) -> None:
        """Close the main application window.

        Args:
            discard_changes: If ``True``, automatically confirm "Don't save"
                style prompts when closing.
        """
        window = self._ensure_window()
        try:
            window.close()
        except Exception:
            pass

        if discard_changes:
            try:
                desktop = Desktop(backend=self.backend)
                confirm = desktop.window(title_re=".*Notepad|.*Save")
                confirm.child_window(name="Don't save").click_input()
            except Exception:
                pass

    def wait_for_text(self, text: str, timeout: int = 10) -> Any:
        """Wait until an element with the given text becomes visible.

        Args:
            text: Exact visible text to wait for.
            timeout: Maximum wait time in seconds.

        Returns:
            The matched wrapper element.
        """
        window = self._ensure_window()
        element = window.child_window(title=text)
        element.wait("visible", timeout=timeout)
        return element

    def _ensure_window(self) -> Any:
        """Return the current main window, raising if absent."""
        if self._main_window is None:
            raise RuntimeError("No window available. Call launch() or find_window() first.")
        return self._main_window


class ChocolateyInstaller:
    """Helper for installing packages via Chocolatey and checking PATH."""

    @staticmethod
    def install(package_name: str, args: str = "-y --no-progress") -> tuple[bool, str]:
        """Install a Chocolatey package.

        Args:
            package_name: Name of the Chocolatey package.
            args: Additional arguments passed to ``choco install``.

        Returns:
            ``(success, stdout)`` tuple.
        """
        command = ["choco", "install", package_name, *args.split()]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                shell=True,
                check=False,
            )
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as exc:  # pragma: no cover
            return False, str(exc)

    @staticmethod
    def is_installed(executable: str) -> bool:
        """Return ``True`` if *executable* can be found on PATH."""
        return shutil.which(executable) is not None


class AndroidSetupAutomation:
    """High-level helper for preparing an Android device for automation."""

    def __init__(self, installer: ChocolateyInstaller | None = None):
        self.installer = installer or ChocolateyInstaller()

    def install_adb(self) -> tuple[bool, str]:
        """Install the Android Debug Bridge via Chocolatey."""
        return self.installer.install("adb")

    def wait_for_device(self, timeout: int = 60) -> bool:
        """Poll ``adb devices`` until at least one authorized device appears.

        Args:
            timeout: Maximum time to wait, in seconds.

        Returns:
            ``True`` if a device appeared, ``False`` if the timeout expired.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                result = subprocess.run(
                    ["adb", "devices"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                for line in result.stdout.splitlines()[1:]:
                    parts = line.strip().split()
                    if len(parts) == 2 and parts[1] == "device":
                        return True
            except Exception:  # pragma: no cover
                pass
            time.sleep(2)
        return False

    def enable_oem_unlock_instructions(self) -> str:
        """Return human-readable steps for enabling OEM unlocking."""
        return (
            "1. On the Android device, open Settings > About phone.\n"
            "2. Tap 'Build number' seven times to enable Developer options.\n"
            "3. Go to Settings > System > Developer options.\n"
            "4. Enable 'OEM unlocking' and 'USB debugging'.\n"
            "5. Connect the device to this PC via USB and authorize the RSA key."
        )


class HomeAssistantOnboardingAutomation:
    """Stub/wrapper to drive the Home Assistant onboarding wizard via Playwright."""

    def __init__(self, browser_page: Any):
        """Initialize with a Playwright ``Page`` object.

        Args:
            browser_page: An existing Playwright page instance.
        """
        self.page = browser_page

    def complete_onboarding(
        self,
        name: str,
        username: str,
        password: str,
        location: str,
    ) -> None:
        """Click through the Home Assistant onboarding wizard.

        This is intentionally a high-level stub; the exact selectors vary by HA
        version. It fills the common onboarding fields and submits each step.

        Args:
            name: Display name for the owner account.
            username: Login username.
            password: Account password.
            location: Location name for the installation.
        """
        page = self.page

        # Initial welcome / create account step
        page.wait_for_selector("text=Create account, text=Next, text=Welcome", timeout=10000)
        if page.locator("input#name, input[name='name']").count():
            page.locator("input#name, input[name='name']").fill(name)
        if page.locator("input#username, input[name='username']").count():
            page.locator("input#username, input[name='username']").fill(username)
        if page.locator("input#password, input[name='password']").count():
            page.locator("input#password, input[name='password']").fill(password)
        if page.locator("text=Next, text=Create account, text=Continue").count():
            page.locator("text=Next, text=Create account, text=Continue").first.click()

        # Location / timezone detection step
        page.wait_for_load_state("networkidle")
        if page.locator("text=Detect, text=Set location, text=Next").count():
            if page.locator("input#location, input[name='location']").count():
                page.locator("input#location, input[name='location']").fill(location)
            page.locator("text=Next, text=Finish").first.click()

        # Final summary / done step
        page.wait_for_load_state("networkidle")
        if page.locator("text=Finish, text=Done, text=Take me to my Home Assistant").count():
            page.locator("text=Finish, text=Done, text=Take me to my Home Assistant").first.click()
