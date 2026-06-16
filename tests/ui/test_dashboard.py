"""UI tests for the Smart HVAC dashboard."""

import pytest

pytestmark = pytest.mark.ui


def test_dashboard_title(page, dashboard_url):
    """The dashboard page title contains the expected text."""
    page.goto(dashboard_url)
    assert "Smart HVAC Dashboard" in page.title()


def test_status_api_visible(page, dashboard_url):
    """Key status labels are rendered on the dashboard."""
    page.goto(dashboard_url)
    assert page.locator("text=AC Mode").is_visible()
    assert page.locator("text=Battery").is_visible()


def test_update_target_temp(page, dashboard_url):
    """Updating the target temperature is reflected on the page."""
    page.goto(dashboard_url)
    page.locator("input#target-temp").fill("25.0")
    page.locator("button#update-target").click()
    page.locator("text=25.0°C").wait_for()
    assert page.locator("text=25.0°C").is_visible()
