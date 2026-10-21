# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
#     "mcp>=2.3.0",
# ]
# ///
"""Weather MCP server backed by the free, keyless Open-Meteo API.

Run standalone with: uv run --script plugins/weather/server.py
"""

from typing import Any, Literal

import httpx
from mcp.server.mcpserver import MCPServer

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = 30.0
MAX_FORECAST_DAYS = 16

type Units = Literal["metric", "imperial"]

# WMO weather interpretation codes, as returned by Open-Meteo.
WEATHER_CODES: dict[int, str] = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}

server = MCPServer(
    name="weather",
    instructions=(
        "Weather lookups for any place name worldwide. "
        "Use get_current_weather for conditions right now and get_forecast for upcoming days."
    ),
)


class LocationNotFoundError(Exception):
    pass


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=REQUEST_TIMEOUT)


def describe(code: int | None) -> str:
    if code is None:
        return "unknown"
    return WEATHER_CODES.get(code, f"weather code {code}")


def unit_params(units: Units) -> dict[str, str]:
    if units == "imperial":
        return {
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
        }
    return {}


async def geocode(client: httpx.AsyncClient, location: str) -> dict[str, Any]:
    response = await client.get(
        GEOCODING_URL, params={"name": location, "count": 1, "language": "en", "format": "json"}
    )
    response.raise_for_status()
    results: list[dict[str, Any]] = response.json().get("results") or []
    if not results:
        raise LocationNotFoundError(f"No place found matching {location!r}.")
    return results[0]


def place_label(place: dict[str, Any]) -> str:
    parts = [place.get("name"), place.get("admin1"), place.get("country")]
    return ", ".join(str(p) for p in parts if p)


async def fetch_forecast(
    client: httpx.AsyncClient, place: dict[str, Any], params: dict[str, Any]
) -> dict[str, Any]:
    response = await client.get(
        FORECAST_URL,
        params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "timezone": "auto",
            **params,
        },
    )
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return data


@server.tool()
async def get_current_weather(location: str, units: Units = "metric") -> str:
    """Get current weather conditions for a place.

    Args:
        location: Place name, e.g. "Berlin" or "Portland, Oregon".
        units: "metric" (°C, km/h, mm) or "imperial" (°F, mph, inch).
    """
    async with make_client() as client:
        try:
            place = await geocode(client, location)
        except LocationNotFoundError as e:
            return str(e)
        data = await fetch_forecast(
            client,
            place,
            {
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                "weather_code,wind_speed_10m,precipitation",
                **unit_params(units),
            },
        )

    current = data["current"]
    u = data["current_units"]
    return "\n".join(
        [
            f"Current weather in {place_label(place)} (as of {current['time']} local time):",
            f"- Conditions: {describe(current.get('weather_code'))}",
            f"- Temperature: {current['temperature_2m']}{u['temperature_2m']}"
            f" (feels like {current['apparent_temperature']}{u['apparent_temperature']})",
            f"- Humidity: {current['relative_humidity_2m']}{u['relative_humidity_2m']}",
            f"- Wind: {current['wind_speed_10m']} {u['wind_speed_10m']}",
            f"- Precipitation: {current['precipitation']} {u['precipitation']}",
        ]
    )


@server.tool()
async def get_forecast(location: str, days: int = 3, units: Units = "metric") -> str:
    """Get a daily weather forecast for a place.

    Args:
        location: Place name, e.g. "Berlin" or "Portland, Oregon".
        days: Number of days to forecast, starting today (1-16).
        units: "metric" (°C, mm) or "imperial" (°F, inch).
    """
    days = max(1, min(days, MAX_FORECAST_DAYS))
    async with make_client() as client:
        try:
            place = await geocode(client, location)
        except LocationNotFoundError as e:
            return str(e)
        data = await fetch_forecast(
            client,
            place,
            {
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_sum,precipitation_probability_max",
                "forecast_days": days,
                **unit_params(units),
            },
        )

    daily = data["daily"]
    u = data["daily_units"]
    lines = [f"{days}-day forecast for {place_label(place)}:"]
    for i, date in enumerate(daily["time"]):
        lines.append(
            f"- {date}: {describe(daily['weather_code'][i])}, "
            f"{daily['temperature_2m_min'][i]}–{daily['temperature_2m_max'][i]}{u['temperature_2m_max']}, "
            f"precipitation {daily['precipitation_sum'][i]} {u['precipitation_sum']} "
            f"({daily['precipitation_probability_max'][i]}{u['precipitation_probability_max']} chance)"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    server.run()
