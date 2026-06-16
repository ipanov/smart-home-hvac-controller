"""Unit tests for weather and pollution clients."""

import pytest
import responses

from smarthvac.weather_client import (
    AirQualitySnapshot,
    CombinedSnapshot,
    OpenMeteoClient,
    OpenWeatherPollutionClient,
    WeatherClientError,
    WeatherService,
    WeatherSnapshot,
)


@pytest.fixture
def openmeteo_client():
    return OpenMeteoClient(latitude=42.0, longitude=21.4)


@pytest.fixture
def pollution_client():
    return OpenWeatherPollutionClient(api_key="test-key", latitude=42.0, longitude=21.4)


@responses.activate
def test_open_meteo_success(openmeteo_client):
    responses.get(
        "https://api.open-meteo.com/v1/forecast",
        json={
            "current": {
                "temperature_2m": 18.5,
                "relative_humidity_2m": 62.0,
            },
            "daily": {
                "temperature_2m_max": [24.3],
                "temperature_2m_min": [12.1],
            },
        },
        status=200,
    )

    snapshot = openmeteo_client.get_current_weather()

    assert isinstance(snapshot, WeatherSnapshot)
    assert snapshot.temperature == 18.5
    assert snapshot.humidity == 62.0
    assert snapshot.forecast_high == 24.3
    assert snapshot.forecast_low == 12.1


@responses.activate
def test_open_meteo_http_error(openmeteo_client):
    responses.get(
        "https://api.open-meteo.com/v1/forecast",
        json={"error": True},
        status=500,
    )

    with pytest.raises(WeatherClientError):
        openmeteo_client.get_current_weather()


@responses.activate
def test_open_meteo_invalid_json(openmeteo_client):
    responses.get(
        "https://api.open-meteo.com/v1/forecast",
        body="not valid json",
        status=200,
    )

    with pytest.raises(WeatherClientError):
        openmeteo_client.get_current_weather()


@responses.activate
def test_openweather_pollution_success(pollution_client):
    responses.get(
        "http://api.openweathermap.org/data/2.5/air_pollution",
        json={
            "list": [
                {
                    "main": {"aqi": 3},
                    "components": {
                        "pm2_5": 12.5,
                        "pm10": 25.0,
                        "o3": 48.2,
                    },
                }
            ]
        },
        status=200,
    )

    snapshot = pollution_client.get_air_quality()

    assert isinstance(snapshot, AirQualitySnapshot)
    assert snapshot.aqi == 3
    assert snapshot.pm25 == 12.5
    assert snapshot.pm10 == 25.0
    assert snapshot.o3 == 48.2


def test_openweather_missing_api_key():
    with pytest.raises(WeatherClientError):
        OpenWeatherPollutionClient(api_key="", latitude=42.0, longitude=21.4)


@responses.activate
def test_weather_service_combined(openmeteo_client, pollution_client):
    responses.get(
        "https://api.open-meteo.com/v1/forecast",
        json={
            "current": {
                "temperature_2m": 20.0,
                "relative_humidity_2m": 55.0,
            },
            "daily": {
                "temperature_2m_max": [26.0],
                "temperature_2m_min": [14.0],
            },
        },
        status=200,
    )
    responses.get(
        "http://api.openweathermap.org/data/2.5/air_pollution",
        json={
            "list": [
                {
                    "main": {"aqi": 2},
                    "components": {
                        "pm2_5": 8.0,
                        "pm10": 18.0,
                        "o3": 35.0,
                    },
                }
            ]
        },
        status=200,
    )

    service = WeatherService(openmeteo_client, pollution_client)
    combined = service.get_combined_snapshot()

    assert isinstance(combined, CombinedSnapshot)
    assert combined.temperature == 20.0
    assert combined.humidity == 55.0
    assert combined.forecast_high == 26.0
    assert combined.forecast_low == 14.0
    assert combined.aqi == 2
    assert combined.pm25 == 8.0
    assert combined.pm10 == 18.0
    assert combined.o3 == 35.0
    assert combined.timestamp is not None


@responses.activate
def test_air_quality_ranges(pollution_client):
    responses.get(
        "http://api.openweathermap.org/data/2.5/air_pollution",
        json={
            "list": [
                {
                    "main": {"aqi": 4},
                    "components": {
                        "pm2_5": 33.7,
                        "pm10": 55.2,
                        "o3": 72.1,
                    },
                }
            ]
        },
        status=200,
    )

    snapshot = pollution_client.get_air_quality()

    assert snapshot.pm25 >= 0
    assert snapshot.pm10 >= 0
    assert snapshot.o3 >= 0
