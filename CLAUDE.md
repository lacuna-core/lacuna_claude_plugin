# CLAUDE.md

## Project purpose

A sandbox for experimenting with Claude extensibility: plugin marketplaces, plugins, skills, slash commands, subagents, hooks, MCP servers/tools, and MCP Apps (interactive UI resources returned by MCP tools). Favor small, self-contained experiments over generalized frameworks. Each experiment should state what it tests, in its README, SKILL.md, or plugin description.

Target layout (create directories as experiments need them):

- **`.claude-plugin/marketplace.json`**: marketplace manifest at the repo root, listing plugins under `plugins/` by relative `source` path.
- **`plugins/<plugin-name>/`**: one Claude Code plugin per directory, with `.claude-plugin/plugin.json`, plus any of `skills/<skill>/SKILL.md`, `commands/*.md`, `agents/*.md`, `hooks/hooks.json`, `.mcp.json`.
- **`src/lacuna_claude_plugin/mcp/`**: Python MCP servers (and MCP App UI resources) that plugins reference from their `.mcp.json`, typically launched with `uv run`.

When a plugin's MCP server lives in `src/`, reference it from `.mcp.json` via `${CLAUDE_PLUGIN_ROOT}`, not via absolute paths.

## Commands

```bash
uv sync --dev                        # install all dependencies
uv run pre-commit install            # wire up git hooks (once per clone)

uv run pytest                        # run all tests with coverage
uv run pytest tests/cli/             # run a single test directory
uv run pytest -k test_version        # run a single test by name

uv run ruff check                    # lint (src/ and tests/)
uv run ruff check --fix              # lint with auto-fix
uv run ruff format                   # format
uv run mypy                          # type-check (strict, src/ and tests/)

uv run lacuna --help                 # run the CLI
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
