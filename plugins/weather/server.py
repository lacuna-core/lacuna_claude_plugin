# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
#     "mcp>=2.3.0",
# ]
# ///
"""Weather MCP server backed by the free, keyless Open-Meteo API.

Both tools are MCP Apps: they carry `_meta.ui.resourceUri` pointing at a `ui://`
widget (widget.html) that hosts supporting MCP Apps render as a weather card.
The widget gets its data from the tool result's `structuredContent`; the text
`content` is the fallback for hosts without MCP Apps and is what the model reads.
The current-weather card's "Next 7/14 days" buttons call get_forecast from the
widget (app-to-server `tools/call`) and swap the card to the forecast. Hosts that
refuse app-initiated tool calls get a `ui/message` instead, so Claude calls it.

Run standalone with: uv run --script plugins/weather/server.py
Add --http to serve streamable HTTP at http://127.0.0.1:8000/mcp instead of stdio
(HOST and PORT env vars override the address, e.g. in the Dockerfile for Cloud Run).
"""

import os
import sys
from pathlib import Path
from typing import Any, Literal

import httpx
from mcp.server.apps import Apps, client_supports_apps
from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, TextContent

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = 30.0
MAX_FORECAST_DAYS = 16
DAILY_FIELDS = (
    "weather_code,temperature_2m_max,temperature_2m_min,"
    "precipitation_sum,precipitation_probability_max"
)

WIDGET_URI = "ui://weather/card.html"
WIDGET_HTML = (Path(__file__).parent / "widget.html").read_text(encoding="utf-8")

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

apps = Apps()
apps.add_html_resource(
    WIDGET_URI,
    WIDGET_HTML,
    name="Weather card",
    description="Renders current conditions or a daily forecast as a card",
    prefers_border=False,
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


def place_info(place: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": place.get("name"),
        "region": place.get("admin1"),
        "country": place.get("country"),
        "label": place_label(place),
        "latitude": place["latitude"],
        "longitude": place["longitude"],
    }


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


def daily_days(data: dict[str, Any]) -> list[dict[str, Any]]:
    daily = data["daily"]
    return [
        {
            "date": date,
            "condition": describe(daily["weather_code"][i]),
            "weather_code": daily["weather_code"][i],
            "temp_min": daily["temperature_2m_min"][i],
            "temp_max": daily["temperature_2m_max"][i],
            "precipitation": daily["precipitation_sum"][i],
            "precipitation_probability": daily["precipitation_probability_max"][i],
        }
        for i, date in enumerate(daily["time"])
    ]


# Prepended to the model-facing text when the host renders the card, so Claude
# lets the card be the answer instead of restating it underneath.
CARD_SHOWN_NOTE = (
    "[Displayed as a card: the client announced MCP Apps support "
    "(io.modelcontextprotocol/ui), so it renders this result as an interactive weather "
    "card directly above your reply. This holds even if your environment looks like a "
    "terminal: the user is in a graphical app (e.g. the Claude desktop app) and already "
    "sees every value below. Reply with exactly one short line that names the place and "
    'repeats no values, e.g. "Here\'s the current weather in Toronto." - no numbers, '
    "conditions, lists or summary. Only if the user asked a specific question the card "
    "doesn't directly answer, answer just that in one short sentence instead.]"
)
CARD_TOOL_NOTE = (
    "When the host renders the result as a weather card, the card is the complete answer: "
    "reply with one short line and no values, not a text summary."
)

_logged_client_support = False


def card_shown(ctx: Context | None) -> bool:
    """Whether the client renders MCP Apps, i.e. the user sees the card."""
    global _logged_client_support
    supported = ctx is not None and client_supports_apps(ctx)
    if not _logged_client_support:
        # stderr lands in the host's MCP server log (e.g. Claude's mcp-server-weather.log).
        print(f"weather: client supports MCP Apps: {supported}", file=sys.stderr)
        _logged_client_support = True
    return supported


def card_result(text: str, card: dict[str, Any], ctx: Context | None) -> CallToolResult:
    if card_shown(ctx):
        # Some hosts (Claude Code) give the model structuredContent instead of the
        # text content, so the note goes in both, first so it's read before the data.
        text = f"{CARD_SHOWN_NOTE}\n\n{text}"
        card = {"note_for_assistant": CARD_SHOWN_NOTE, **card}
    return CallToolResult(content=[TextContent(type="text", text=text)], structured_content=card)


def not_found(error: LocationNotFoundError) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=str(error))],
        structured_content={"kind": "error", "message": str(error)},
    )


def current_text(card: dict[str, Any]) -> str:
    c, u = card["current"], card["unit_labels"]
    return "\n".join(
        [
            f"Current weather in {card['location']['label']} (as of {c['time']} local time):",
            f"- Conditions: {c['condition']}",
            f"- Temperature: {c['temperature']}{u['temperature']}"
            f" (feels like {c['apparent_temperature']}{u['temperature']})",
            f"- Humidity: {c['humidity']}%",
            f"- Wind: {c['wind_speed']} {u['wind_speed']}",
            f"- Precipitation: {c['precipitation']} {u['precipitation']}",
        ]
    )


def forecast_text(card: dict[str, Any]) -> str:
    u = card["unit_labels"]
    lines = [f"{len(card['days'])}-day forecast for {card['location']['label']}:"]
    for d in card["days"]:
        lines.append(
            f"- {d['date']}: {d['condition']}, "
            f"{d['temp_min']}–{d['temp_max']}{u['temperature']}, "
            f"precipitation {d['precipitation']} {u['precipitation']} "
            f"({d['precipitation_probability']}% chance)"
        )
    return "\n".join(lines)


@apps.tool(resource_uri=WIDGET_URI)
async def get_current_weather(
    location: str, units: Units = "metric", ctx: Context | None = None
) -> CallToolResult:
    """Get current weather conditions for a place, shown as a weather card.

    When the host renders the result as a weather card, the card is the complete
    answer: reply with one short line and no values, not a text summary.

    Args:
        location: Place name, optionally with ", region" or ", country", e.g. "Portland, Maine".
        units: "metric" (°C, km/h, mm) or "imperial" (°F, mph, inch).
    """
    async with make_client() as client:
        try:
            place = await geocode(client, location)
        except LocationNotFoundError as e:
            return not_found(e)
        data = await fetch_forecast(
            client,
            place,
            {
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                "weather_code,wind_speed_10m,precipitation,is_day",
                **unit_params(units),
            },
        )

    current, u = data["current"], data["current_units"]
    card = {
        "kind": "current",
        "query": location,
        "units": units,
        "location": place_info(place),
        "unit_labels": {
            "temperature": u["temperature_2m"],
            "wind_speed": u["wind_speed_10m"],
            "precipitation": u["precipitation"],
        },
        "current": {
            "time": current["time"],
            "condition": describe(current.get("weather_code")),
            "weather_code": current.get("weather_code"),
            "is_day": bool(current.get("is_day", 1)),
            "temperature": current["temperature_2m"],
            "apparent_temperature": current["apparent_temperature"],
            "humidity": current["relative_humidity_2m"],
            "wind_speed": current["wind_speed_10m"],
            "precipitation": current["precipitation"],
        },
    }
    return card_result(current_text(card), card, ctx)


@apps.tool(resource_uri=WIDGET_URI)
async def get_forecast(
    location: str, days: int = 3, units: Units = "metric", ctx: Context | None = None
) -> CallToolResult:
    """Get a daily weather forecast for a place, shown as a weather card.

    When the host renders the result as a weather card, the card is the complete
    answer: reply with one short line and no values, not a text summary.

    Args:
        location: Place name, optionally with ", region" or ", country", e.g. "Portland, Maine".
        days: Number of days to forecast, starting today (1-16).
        units: "metric" (°C, mm) or "imperial" (°F, inch).
    """
    days = max(1, min(days, MAX_FORECAST_DAYS))
    async with make_client() as client:
        try:
            place = await geocode(client, location)
        except LocationNotFoundError as e:
            return not_found(e)
        data = await fetch_forecast(
            client,
            place,
            {
                "daily": DAILY_FIELDS,
                "forecast_days": days,
                **unit_params(units),
            },
        )

    u = data["daily_units"]
    card = {
        "kind": "forecast",
        "query": location,
        "units": units,
        "location": place_info(place),
        "unit_labels": {
            "temperature": u["temperature_2m_max"],
            "precipitation": u["precipitation_sum"],
        },
        "days": daily_days(data),
    }
    return card_result(forecast_text(card), card, ctx)


# Built after the @apps.tool definitions: MCPServer collects extension tools at construction.
server = MCPServer(
    name="weather",
    instructions=(
        "Weather lookups for any place name worldwide. "
        "Use get_current_weather for conditions right now and get_forecast for upcoming days. "
        "In hosts that support MCP Apps, results render as an interactive weather card. "
        + CARD_TOOL_NOTE
    ),
    extensions=[apps],
)


if __name__ == "__main__":
    if "--http" in sys.argv:
        # Streamable HTTP at /mcp. The defaults (127.0.0.1:8000) suit an ngrok tunnel;
        # containers such as Cloud Run set HOST=0.0.0.0 and PORT.
        server.run(
            transport="streamable-http",
            host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", "8000")),
        )
    else:
        server.run()
