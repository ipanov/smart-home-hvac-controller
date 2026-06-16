"""Weather and pollution client for Open-Meteo and OpenWeatherMap."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests
from pydantic import BaseModel, Field, ValidationError


class WeatherClientError(Exception):
    """Raised when a weather or pollution client request fails."""


class WeatherSnapshot(BaseModel):
    """Current weather and today's forecast from Open-Meteo."""

    temperature: float = Field(..., description="Current temperature in °C")
    humidity: float = Field(..., description="Current relative humidity in %")
    forecast_high: float = Field(..., description="Today's forecast high in °C")
    forecast_low: float = Field(..., description="Today's forecast low in °C")


class AirQualitySnapshot(BaseModel):
    """Air quality snapshot from OpenWeatherMap."""

    aqi: int = Field(..., description="Air Quality Index (1-5)")
    pm25: float = Field(..., description="PM2.5 concentration in µg/m³", ge=0)
    pm10: float = Field(..., description="PM10 concentration in µg/m³", ge=0)
    o3: float = Field(..., description="Ozone concentration in µg/m³", ge=0)


class CombinedSnapshot(BaseModel):
    """Combined weather and air quality snapshot."""

    temperature: float
    humidity: float
    forecast_high: float
    forecast_low: float
    aqi: int
    pm25: float
    pm10: float
    o3: float
    timestamp: datetime


class OpenMeteoClient:
    """Fetch current weather and daily forecast from Open-Meteo."""

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, latitude: float, longitude: float) -> None:
        """Initialize with geographic coordinates."""
        self.latitude = latitude
        self.longitude = longitude

    def _build_url(self) -> str:
        params = (
            f"latitude={self.latitude}&longitude={self.longitude}"
            "&current=temperature_2m,relative_humidity_2m"
            "&daily=temperature_2m_max,temperature_2m_min"
            "&timezone=auto"
        )
        return f"{self.BASE_URL}?{params}"

    def get_current_weather(self) -> WeatherSnapshot:
        """Fetch and parse the current weather snapshot."""
        try:
            response = requests.get(self._build_url(), timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise WeatherClientError(f"Open-Meteo request failed: {exc}") from exc
        except ValueError as exc:
            raise WeatherClientError(f"Invalid JSON from Open-Meteo: {exc}") from exc

        try:
            current = data["current"]
            daily = data["daily"]
            return WeatherSnapshot(
                temperature=float(current["temperature_2m"]),
                humidity=float(current["relative_humidity_2m"]),
                forecast_high=float(daily["temperature_2m_max"][0]),
                forecast_low=float(daily["temperature_2m_min"][0]),
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise WeatherClientError(f"Unexpected Open-Meteo data shape: {exc}") from exc


class OpenWeatherPollutionClient:
    """Fetch air quality data from OpenWeatherMap."""

    BASE_URL = "http://api.openweathermap.org/data/2.5/air_pollution"

    def __init__(self, api_key: str, latitude: float, longitude: float) -> None:
        """Initialize with API key and coordinates."""
        if not api_key:
            raise WeatherClientError("OpenWeather API key is required")
        self.api_key = api_key
        self.latitude = latitude
        self.longitude = longitude

    def _build_url(self) -> str:
        params = (
            f"lat={self.latitude}&lon={self.longitude}"
            f"&appid={self.api_key}"
        )
        return f"{self.BASE_URL}?{params}"

    def get_air_quality(self) -> AirQualitySnapshot:
        """Fetch and parse the air quality snapshot."""
        try:
            response = requests.get(self._build_url(), timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise WeatherClientError(f"OpenWeather request failed: {exc}") from exc
        except ValueError as exc:
            raise WeatherClientError(f"Invalid JSON from OpenWeather: {exc}") from exc

        try:
            entry = data["list"][0]
            components = entry["components"]
            return AirQualitySnapshot(
                aqi=int(entry["main"]["aqi"]),
                pm25=float(components["pm2_5"]),
                pm10=float(components["pm10"]),
                o3=float(components["o3"]),
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise WeatherClientError(f"Unexpected OpenWeather data shape: {exc}") from exc


class WeatherService:
    """Combine weather and air quality into a single snapshot."""

    def __init__(
        self,
        openmeteo_client: OpenMeteoClient,
        pollution_client: OpenWeatherPollutionClient,
    ) -> None:
        """Initialize with the two underlying clients."""
        self.openmeteo_client = openmeteo_client
        self.pollution_client = pollution_client

    def get_combined_snapshot(self) -> CombinedSnapshot:
        """Return a combined snapshot with a UTC timestamp."""
        weather = self.openmeteo_client.get_current_weather()
        air_quality = self.pollution_client.get_air_quality()

        return CombinedSnapshot(
            temperature=weather.temperature,
            humidity=weather.humidity,
            forecast_high=weather.forecast_high,
            forecast_low=weather.forecast_low,
            aqi=air_quality.aqi,
            pm25=air_quality.pm25,
            pm10=air_quality.pm10,
            o3=air_quality.o3,
            timestamp=datetime.now(timezone.utc),
        )
