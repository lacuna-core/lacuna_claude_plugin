# lacuna

TODO: one-sentence project description.

## Bootstrap

```bash
gh repo create <your-project-name> --template lacuna-core/lacuna_template --public --clone
cd <your-project-name>
bash shell/bootstrap.sh <your-project-name>
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — Python package manager

## Install

```bash
git clone <repo-url> lacuna
cd lacuna
uv sync --dev
uv run pre-commit install
```

## Configure

Copy `.env.example` to `.env` and set values:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `LACUNA_LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LACUNA_REQUEST_TIMEOUT` | `30` | HTTP request timeout in seconds |

## Usage

```bash
uv run lacuna --help
```

## Releases

Releases are published to [GitHub Releases](../../releases). Each tag (`v*.*.*`) triggers a draft release with auto-generated notes via [git-cliff](https://git-cliff.org/).
