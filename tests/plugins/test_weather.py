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

DAILY: dict[str, Any] = {
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


def text_of(result: Any) -> str:
    return "\n".join(block.text for block in result.content)


async def test_current_weather(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_api(monkeypatch, [BERLIN], CURRENT)

    result = await weather.get_current_weather("Berlin")

    text = text_of(result)
    assert "Berlin, Land Berlin, Germany" in text
    assert "overcast" in text
    assert "12.3°C (feels like 10.1°C)" in text
    card = result.structured_content
    assert card["kind"] == "current"
    assert card["query"] == "Berlin"
    assert card["location"]["label"] == "Berlin, Land Berlin, Germany"
    assert card["current"]["temperature"] == 12.3
    assert card["current"]["condition"] == "overcast"
    assert card["unit_labels"] == {"temperature": "°C", "wind_speed": "km/h", "precipitation": "mm"}


async def test_forecast(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = mock_api(monkeypatch, [BERLIN], DAILY)

    result = await weather.get_forecast("Berlin", days=2)

    text = text_of(result)
    assert "2026-10-21: slight rain, 8.0–14.0°C, precipitation 3.2 mm (80% chance)" in text
    assert "2026-10-22: clear sky" in text
    assert requests[1].url.params["forecast_days"] == "2"
    card = result.structured_content
    assert card["kind"] == "forecast"
    assert [d["date"] for d in card["days"]] == ["2026-10-21", "2026-10-22"]
    assert card["days"][0] == {
        "date": "2026-10-21",
        "condition": "slight rain",
        "weather_code": 61,
        "temp_min": 8.0,
        "temp_max": 14.0,
        "precipitation": 3.2,
        "precipitation_probability": 80,
    }


async def test_forecast_clamps_days_and_uses_imperial(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = mock_api(monkeypatch, [BERLIN], DAILY)

    result = await weather.get_forecast("Berlin", days=99, units="imperial")

    params = requests[1].url.params
    assert params["forecast_days"] == str(weather.MAX_FORECAST_DAYS)
    assert params["temperature_unit"] == "fahrenheit"
    assert result.structured_content["units"] == "imperial"


async def test_unknown_location(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_api(monkeypatch, [], CURRENT)

    result = await weather.get_current_weather("Nowhereville")

    assert text_of(result) == "No place found matching 'Nowhereville'."
    assert result.structured_content == {
        "kind": "error",
        "message": "No place found matching 'Nowhereville'.",
    }


async def test_tools_bound_to_widget() -> None:
    tools = {tool.name: tool for tool in await weather.server.list_tools()}

    assert set(tools) == {"get_current_weather", "get_forecast"}
    for tool in tools.values():
        assert tool.meta == {"ui": {"resourceUri": weather.WIDGET_URI}}


async def test_widget_resource_served_as_mcp_app() -> None:
    [contents] = await weather.server.read_resource(weather.WIDGET_URI)

    assert contents.mime_type == "text/html;profile=mcp-app"
    assert "ui/initialize" in contents.content
    assert "Next 7 days" in contents.content
    # Card buttons turn into user input for Claude rather than local view changes.
    assert '"ui/message"' in contents.content


async def test_card_hosts_get_no_summary_note(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_api(monkeypatch, [BERLIN], CURRENT)
    monkeypatch.setattr(weather, "client_supports_apps", lambda ctx: True)

    result = await weather.get_current_weather("Berlin", ctx=object())

    text = text_of(result)
    assert text.startswith(weather.CARD_SHOWN_NOTE)
    assert "12.3°C" in text  # data stays available for follow-up questions
    # Claude Code shows the model structuredContent, not the text: the note must be there too.
    assert next(iter(result.structured_content)) == "note_for_assistant"
    assert result.structured_content["note_for_assistant"] == weather.CARD_SHOWN_NOTE


async def test_text_only_hosts_get_plain_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_api(monkeypatch, [BERLIN], DAILY)
    monkeypatch.setattr(weather, "client_supports_apps", lambda ctx: False)

    result = await weather.get_forecast("Berlin", days=2, ctx=object())

    assert weather.CARD_SHOWN_NOTE not in text_of(result)
    assert "note_for_assistant" not in result.structured_content
    assert text_of(result).startswith("2-day forecast for Berlin")


async def test_context_param_not_exposed_to_model() -> None:
    for tool in await weather.server.list_tools():
        assert "ctx" not in tool.input_schema["properties"]
