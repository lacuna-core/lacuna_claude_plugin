---
name: weather
description: Answer questions about current weather or upcoming forecasts for a place, e.g. "what's the weather in Lisbon", "will it rain in Berlin this weekend", "should I bring a jacket to Paris tomorrow". Uses the weather plugin's MCP tools.
---

# Weather

Use the `weather` MCP server's tools to answer weather questions. Don't guess conditions from memory.

## Picking a tool

- Conditions right now ("what's it like outside", "is it raining") → `get_current_weather`.
- Anything about later today, tomorrow, the weekend, or a trip → `get_forecast`, with `days` just large enough to cover the asked-about dates (max 16).
- Both, if the question needs both.

## Arguments

- `location`: a place name, optionally followed by a comma and a region or country to disambiguate: "Portland, Maine", "Paris, France". Always use the comma ("Portland Maine" finds nothing). A bare "Portland" resolves to the most populous match (Oregon). If the tool says no place was found, retry once with just the place name, then ask the user.
- `units`: default `metric`. Use `imperial` if the user writes in °F/mph, or asks for it, or is clearly in the US.

## Answering

- Lead with the direct answer to the question asked ("Yes, rain is likely Saturday afternoon"), then the supporting numbers.
- Name the resolved place so the user can catch a wrong match.
- Keep it short. Don't dump the full tool output unless asked.

## Weather cards (MCP Apps)

Both tools are MCP Apps. In hosts that support them (e.g. the Claude apps), each result renders as a card: current conditions, or a day-by-day forecast list. The current-conditions card has **Next 7 days** / **Next 14 days** buttons. A click posts a user message such as "Show me the 7-day forecast for Lisbon."

- **When a card is shown, the card is the answer.** Reply with one short line that names the place and repeats no values ("Here's the current weather in Toronto."): no numbers, conditions, lists or summary. An empty reply doesn't work, because Claude Code then asks for a visible response. The tool result starts with a note when the host renders cards. The only exception is a specific question the card doesn't directly answer ("do I need an umbrella?"); answer just that in one short sentence.
- To show both current conditions and a forecast, prefer one `get_current_weather` call: the user can expand the forecast from the card. Call `get_forecast` yourself when the question is about future days.
- When such a message comes from a card button, call `get_forecast` with that location, that number of `days`, and the same units. The forecast renders as its own card, so reply with just one short line ("Here's the 7-day forecast for Lisbon.").
