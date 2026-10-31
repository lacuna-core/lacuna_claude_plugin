# CLAUDE.md

## Project purpose

A sandbox for experimenting with Claude extensibility: plugin marketplaces, plugins, skills, slash commands, subagents, hooks, MCP servers/tools, and MCP Apps (interactive UI resources returned by MCP tools). Favor small, self-contained experiments over generalized frameworks. Each experiment should state what it tests, in its README, SKILL.md, or plugin description.

Layout:

- **`.claude-plugin/marketplace.json`**: the `lacuna` marketplace manifest at the repo root. Every plugin under `plugins/` must have an entry here with a relative `source` (`./plugins/<name>`), and its `version` must match the plugin's `plugin.json`.
- **`plugins/<plugin-name>/`**: one Claude Code plugin per directory, with `.claude-plugin/plugin.json`, plus any of `skills/<skill>/SKILL.md`, `commands/*.md`, `agents/*.md`, `hooks/hooks.json`, `.mcp.json`.
- **`src/lacuna_claude_plugin/`**: the `lacuna` helper CLI. Plugins must not depend on it.

Current plugins:

- **`weather`**: MCP server (`server.py`, Open-Meteo, no API key; the plugin's `.mcp.json` connects to it remotely at `https://steersman-nurture-sherry.ngrok-free.dev/mcp`, served by `server.py --http` through ngrok; `plugins/weather/Dockerfile` deploys the same server to Google Cloud Run instead) with `get_current_weather` and `get_forecast` tools, plus a `weather` skill that tells Claude when and how to use them. Both tools are MCP Apps bound to `ui://weather/card.html` (`widget.html`). The widget renders a current-conditions card or a forecast list from `structuredContent`; The current card's **Next 7/14 days** buttons call `get_forecast` from the widget (`tools/call`) and swap the card to the forecast, with a **← Now** button back; each switch is reported with `ui/update-model-context`. If the host rejects the `tools/call`, the button falls back to a `ui/message` user turn ("Show me the 7-day forecast for Lisbon."), so Claude calls `get_forecast` and a new forecast card appears in the chat.

### Plugin conventions

- **Plugins are self-contained.** An installed plugin is copied into Claude Code's plugin cache, so nothing outside its own directory (no `../`, no `src/`) is available at runtime.
- **Python MCP servers are single-file [PEP 723](https://peps.python.org/pep-0723/) scripts** inside the plugin (`plugins/<name>/server.py`) with inline dependencies. A stdio `.mcp.json` launches them with `uv run --quiet --script ${CLAUDE_PLUGIN_ROOT}/server.py`; use `${CLAUDE_PLUGIN_ROOT}`, never absolute paths. `--http` serves streamable HTTP at `/mcp` on `HOST`/`PORT` (default `127.0.0.1:8000`). Keep it stateful (no `stateless_http`): `client_supports_apps` reads the capabilities from the session's `initialize`, so a stateless server never detects MCP Apps. A remote `.mcp.json` uses `{"type": "http", "url": "https://<host>/mcp"}` instead (`weather` does this), and the plugin only works while that server is reachable.
- **MCP SDK is 2.x**: `from mcp.server.mcpserver import MCPServer` (`FastMCP` was renamed in 2.0). It's a dev dependency so mypy and tests can import plugin servers.
- Plugin code is linted and type-checked with the rest of the repo (ruff and mypy include `plugins/`). Tests live in `tests/plugins/test_<name>.py`. They load the server script with `importlib` and mock HTTP with `httpx.MockTransport`, so they never hit the network.
- Run `claude plugin validate .` (marketplace) and `claude plugin validate plugins/<name>` after changing manifests.

### MCP Apps conventions

- Use the SDK's extension, `mcp.server.apps.Apps`: `@apps.tool(resource_uri="ui://<plugin>/<view>.html")` plus `apps.add_html_resource(...)`, passed as `MCPServer(extensions=[apps])`. **Construct `MCPServer` after all `@apps.tool` definitions.** It collects extension tools at construction, so tools defined later are silently missing.
- UI-bound tools return `CallToolResult(content=[text], structured_content={...})`. The widget renders `structuredContent`, while the text `content` is what the model reads and what non-Apps hosts (like the Claude Code terminal) show, so it must be a complete answer on its own. Give `structuredContent` a `kind` field so one widget can render several views.
- Widgets are a single self-contained HTML file next to `server.py`, with inline CSS, JS and SVG. The host's default CSP blocks external scripts, styles, fonts and `fetch`. Data comes only from tool results. Declare `ResourceCsp` domains if a widget ever needs network access.
- Widgets speak the MCP Apps protocol (`2026-01-26`) directly over `postMessage`, with no SDK and no bundler. The handshake is `ui/initialize` (with `appInfo`), then `ui/notifications/initialized`. Handle `tool-input`, `tool-result`, `host-context-changed` (theme, CSS variables) and `resource-teardown`, and report height with `ui/notifications/size-changed`.
- Style widgets with the host's CSS variables (`--color-background-primary`, `--color-text-primary`, `--font-sans`, …) with fallbacks, and support light and dark themes (`hostContext.theme`, then `prefers-color-scheme`).
- After an in-widget action changes what the user sees, call `ui/update-model-context` so Claude can answer follow-up questions about it.
- **Claude as host** (per Anthropic's `build-mcp-app` skill in `anthropics/claude-plugins-official`): widgets are supported for remote (streamable-HTTP) servers and MCPB bundles. A plain local stdio server is not a documented path, and app-initiated `tools/call` failed there with "IPC not available for MCP tool call". Claude Desktop caches UI resources aggressively, so after editing a widget fully quit (⌘Q) and relaunch. Closing the window isn't enough. To test in claude.ai, run the server over streamable HTTP and add it as a custom connector (through a tunnel for local dev).
- **The card is the answer.** When the client supports MCP Apps (`client_supports_apps(ctx)`; tools take `ctx: Context | None = None`, which the SDK injects and hides from the input schema), add a note telling Claude not to summarize, so no duplicate text appears under the card. **Put it in `structuredContent` (`note_for_assistant`, first key) as well as the text.** Claude Code gives the model `structuredContent` *instead of* the text `content` whenever it's present. Claude Code announces the MCP Apps capability only when the Desktop app hosts it (env `CLAUDE_CODE_MCP_APPS_HOST`). To reproduce that locally, run `CLAUDE_CODE_MCP_APPS_HOST=1 claude -p "..." --plugin-dir ./plugins/<name>`. Note that in a real terminal Claude may sensibly ignore the note and answer in text. **Don't ask for an empty reply**: Claude Code rejects a turn with no visible output (it injects "Your previous response had no visible output…") and Claude then writes the full summary. Ask for one short line with no values instead. Text-only clients get the plain answer. The server logs the detected mode to stderr, which ends up in the host's MCP log.

### Plugin dev and release flow

- **Dev:** test from the working tree with `claude --plugin-dir ./plugins/<name>` (session-only, no install, picks up uncommitted edits on relaunch). To test the real install path, use `claude plugin marketplace add ./` and then `claude plugin install <name>@lacuna`.
- **Production:** users install from GitHub with `claude plugin install <name> --marketplace lacuna-core/lacuna_claude_plugin`. They get updates only through `claude plugin marketplace update lacuna` followed by `claude plugin update <name>`.
- **Release:** installed plugins are cached by `version`, so any change meant to reach users needs a version bump. Bump it in **both** `plugin.json` and the plugin's `marketplace.json` entry (they must match), commit as `chore(plugin): release <name> x.y.z`, push, then run `claude plugin tag plugins/<name> --push`. That creates a `<name>--vx.y.z` tag, which doesn't trigger the repo's `v*.*.*` release workflow.
- Don't bump plugin versions for repo-only changes (tests, docs outside the plugin directory).

## Commands

```bash
uv sync --dev                        # install all dependencies
uv run pre-commit install            # wire up git hooks (once per clone)

uv run pytest                        # run all tests with coverage
uv run pytest tests/cli/             # run a single test directory
uv run pytest -k test_version        # run a single test by name

uv run ruff check                    # lint (src/, tests/, plugins/)
uv run ruff check --fix              # lint with auto-fix
uv run ruff format                   # format
uv run mypy                          # type-check (strict, src/, tests/, plugins/)

uv run lacuna --help                 # run the CLI

claude plugin validate .                     # validate the marketplace manifest
claude plugin validate plugins/weather       # validate one plugin
uv run --script plugins/weather/server.py    # run a plugin's MCP server standalone (stdio)
uv run --script plugins/weather/server.py --http   # streamable HTTP on 127.0.0.1:8000/mcp (tunnel: ngrok http 8000 --host-header=rewrite)
gcloud run deploy weather-mcp --project weather-mcp-andrey --source plugins/weather --region us-central1 --allow-unauthenticated --max-instances 1   # deploy to Cloud Run
```

## Architecture

`src/lacuna_claude_plugin/` follows a layered structure:

- **`config.py`** — frozen `Settings` (pydantic-settings, `LACUNA_` env prefix). Calls `load_dotenv()` at import time. The singleton `SETTINGS` is imported by the CLI and passed explicitly to clients — nothing reads `SETTINGS` internally.
- **`cli/app.py`** — Typer CLI. Sub-command groups live in separate files (e.g. `cli/foo.py`) and are registered via `app.add_typer(...)`.

Logging is configured once in `__init__.py`: loguru handler removed and re-added with the level from `SETTINGS.log_level`. Set `LACUNA_LOG_LEVEL=DEBUG` to see debug output.

## Commit Message Convention

This project follows **Conventional Commits** (https://www.conventionalcommits.org).
All commits generated or suggested by Claude must conform to this spec.

### Format
<type>[optional scope]: <description>
[optional body]
[optional footer(s)]

### Allowed types

- feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert

### Scopes for this project (pick the closest match)

- python, research, plugin, skill, mcp, marketplace

### Rules

1. Subject line ≤ 72 characters, lowercase, no trailing period.
2. Use imperative mood: "add feature" not "added feature".
3. Breaking changes: append `!` to the type OR add a `BREAKING CHANGE:` footer.
4. Never squash unrelated changes into one commit — split them.

## Key conventions and guidelines

- **Docs: prefer itemized instructions over text blobs.** Write multi-step procedures (in README, CONTRIBUTING, SKILL.md, etc.) as numbered steps with one action each and commands in their own code blocks, and put caveats in bullets rather than long paragraphs.
- Dependency injection: pass config explicitly to any client/service — never read the global `SETTINGS` inside library code.
- mypy is strict. All functions including tests need return type annotations.
- Git hooks (pre-commit) run ruff (fix + format) and mypy on every commit.
- CLI lazy imports: in `cli/app.py`, `lacuna_claude_plugin.*` imports must be inside the command function body, not at module level. `typer`, `rich`, and stdlib belong at the top of the file. This keeps `--help` fast and isolates heavy deps per command.
- **After every significant change** — new CLI command, new data pipeline, new dependency, changed directory layout — update `CLAUDE.md` (architecture / conventions), `README.md` (user-facing instructions), and `CONTRIBUTING.md` (dev setup / release process). Keep them in sync with the actual codebase.
