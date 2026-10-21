# Contributing

## Dev environment

```bash
git clone <repo-url> lacuna
cd lacuna
uv sync --dev
uv run pre-commit install   # runs ruff + mypy on every commit
```

## Running tests

```bash
uv run pytest                        # all tests with coverage
uv run pytest tests/cli/             # single directory
uv run pytest -k test_version        # single test
```

## Lint and type-check

```bash
uv run ruff check --fix   # lint + auto-fix
uv run ruff format        # format
uv run mypy               # strict type-check
```

## Architecture

`src/lacuna/` is layered:

- **`config.py`** — pydantic-settings with `LACUNA_` env prefix
- **`cli/app.py`** — Typer CLI; add sub-commands as `cli/<name>.py` and register via `app.add_typer(...)`

See `CLAUDE.md` for coding conventions.

## Commit conventions

This project uses [Conventional Commits](https://www.conventionalcommits.org):

```
<type>[optional scope]: <description>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

Subject line ≤ 72 chars, lowercase, imperative mood, no trailing period.

## Cutting a release

1. Update `version` in `pyproject.toml` and `src/lacuna/__init__.py`.
2. Commit: `chore: bump version to x.y.z`
3. Tag: `git tag vx.y.z && git push origin vx.y.z`
4. The Release workflow generates a draft release with notes from git-cliff — review and publish.
