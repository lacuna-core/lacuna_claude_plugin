# CLAUDE.md

## Project purpose

A sandbox for experimenting with Claude extensibility: plugin marketplaces, plugins, skills, slash commands, subagents, hooks, MCP servers/tools, and MCP Apps (interactive UI resources returned by MCP tools). Favor small, self-contained experiments over generalized frameworks. Each experiment should state what it tests, in its README, SKILL.md, or plugin description.

Layout:

- **`.claude-plugin/marketplace.json`**: the `lacuna` marketplace manifest at the repo root. Every plugin under `plugins/` must have an entry here with a relative `source` (`./plugins/<name>`), and its `version` must match the plugin's `plugin.json`.
- **`plugins/<plugin-name>/`**: one Claude Code plugin per directory, with `.claude-plugin/plugin.json`, plus any of `skills/<skill>/SKILL.md`, `commands/*.md`, `agents/*.md`, `hooks/hooks.json`, `.mcp.json`.
- **`src/lacuna_claude_plugin/`**: the `lacuna` helper CLI. Plugins must not depend on it.

Current plugins:

- **`weather`**: MCP server (`server.py`, Open-Meteo, no API key) with `get_current_weather` and `get_forecast` tools, plus a `weather` skill that tells Claude when and how to use them.

### Plugin conventions

- **Plugins are self-contained.** An installed plugin is copied into Claude Code's plugin cache, so nothing outside its own directory (no `../`, no `src/`) is available at runtime.
- **Python MCP servers are single-file [PEP 723](https://peps.python.org/pep-0723/) scripts** inside the plugin (`plugins/<name>/server.py`) with inline dependencies. `.mcp.json` launches them with `uv run --quiet --script ${CLAUDE_PLUGIN_ROOT}/server.py`. Use `${CLAUDE_PLUGIN_ROOT}`, never absolute paths.
- **MCP SDK is 2.x**: `from mcp.server.mcpserver import MCPServer` (`FastMCP` was renamed in 2.0). It's a dev dependency so mypy and tests can import plugin servers.
- Plugin code is linted and type-checked with the rest of the repo (ruff and mypy include `plugins/`). Tests live in `tests/plugins/test_<name>.py`. They load the server script with `importlib` and mock HTTP with `httpx.MockTransport`, so they never hit the network.
- Run `claude plugin validate .` (marketplace) and `claude plugin validate plugins/<name>` after changing manifests.

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

- Dependency injection: pass config explicitly to any client/service — never read the global `SETTINGS` inside library code.
- mypy is strict. All functions including tests need return type annotations.
- Git hooks (pre-commit) run ruff (fix + format) and mypy on every commit.
- CLI lazy imports: in `cli/app.py`, `lacuna_claude_plugin.*` imports must be inside the command function body, not at module level. `typer`, `rich`, and stdlib belong at the top of the file. This keeps `--help` fast and isolates heavy deps per command.
- **After every significant change** — new CLI command, new data pipeline, new dependency, changed directory layout — update `CLAUDE.md` (architecture / conventions), `README.md` (user-facing instructions), and `CONTRIBUTING.md` (dev setup / release process). Keep them in sync with the actual codebase.
