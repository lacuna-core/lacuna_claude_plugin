import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest

SERVER_PATH = Path(__file__).parents[2] / "plugins" / "weather" / "server.py"


def load_server() -> ModuleType:
    spec = importlib.util.spec_from_file_location("weather_server", SERVER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


weather = load_server()

BERLIN = {
    "name": "Berlin",
    "admin1": "Land Berlin",
    "country": "Germany",
    "latitude": 52.52,
    "longitude": 13.41,
}

CURRENT = {
    "current_units": {
        "temperature_2m": "°C",
        "apparent_temperature": "°C",
        "relative_humidity_2m": "%",
        "wind_speed_10m": "km/h",
        "precipitation": "mm",
    },
    "current": {
        "time": "2026-10-21T14:00",
        "temperature_2m": 12.3,
        "apparent_temperature": 10.1,
        "relative_humidity_2m": 70,
        "weather_code": 3,
        "wind_speed_10m": 15.2,
        "precipitation": 0.0,
    },
}

DAILY = {
    "daily_units": {
        "temperature_2m_max": "°C",
        "precipitation_sum": "mm",
        "precipitation_probability_max": "%",
    },
    "daily": {
        "time": ["2026-10-21", "2026-10-22"],
        "weather_code": [61, 0],
        "temperature_2m_min": [8.0, 6.5],
        "temperature_2m_max": [14.0, 15.5],
        "precipitation_sum": [3.2, 0.0],
        "precipitation_probability_max": [80, 5],
    },
}


def mock_api(
    monkeypatch: pytest.MonkeyPatch, places: list[dict[str, Any]], forecast: dict[str, Any]
) -> list[httpx.Request]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host.startswith("geocoding-api"):
            return httpx.Response(200, json={"results": places} if places else {})
        return httpx.Response(200, json=forecast)

    monkeypatch.setattr(
        weather, "make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    return requests


async def test_current_weather(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_api(monkeypatch, [BERLIN], CURRENT)

    result = await weather.get_current_weather("Berlin")

    assert "Berlin, Land Berlin, Germany" in result
    assert "overcast" in result
    assert "12.3°C (feels like 10.1°C)" in result


async def test_forecast(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = mock_api(monkeypatch, [BERLIN], DAILY)

    result = await weather.get_forecast("Berlin", days=2)

    assert "2026-10-21: slight rain, 8.0–14.0°C, precipitation 3.2 mm (80% chance)" in result
    assert "2026-10-22: clear sky" in result
    assert requests[1].url.params["forecast_days"] == "2"


async def test_forecast_clamps_days_and_uses_imperial(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = mock_api(monkeypatch, [BERLIN], DAILY)

    await weather.get_forecast("Berlin", days=99, units="imperial")

    params = requests[1].url.params
    assert params["forecast_days"] == str(weather.MAX_FORECAST_DAYS)
    assert params["temperature_unit"] == "fahrenheit"


async def test_unknown_location(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_api(monkeypatch, [], CURRENT)

    assert (
        await weather.get_current_weather("Nowhereville")
        == "No place found matching 'Nowhereville'."
    )


async def test_tools_registered() -> None:
    names = {tool.name for tool in await weather.server.list_tools()}

    assert names == {"get_current_weather", "get_forecast"}
