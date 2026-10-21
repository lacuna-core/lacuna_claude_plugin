# lacuna_claude_plugin

A sandbox for experimenting with the Claude extension ecosystem: plugin **marketplaces**, **plugins**, **skills**, **slash commands**, **subagents**, **hooks**, **MCP servers/tools**, and **MCP Apps** (interactive UI returned by MCP tools).

This is a learning and prototyping repo, not a product. Each experiment should be small and self-contained, with a short note on what it tests and what we learned.

## What's in here

| Area | Location | Status |
|------|----------|--------|
| Plugin marketplace | `.claude-plugin/marketplace.json` | planned |
| Plugins (skills, commands, agents, hooks) | `plugins/<plugin-name>/` | planned |
| MCP servers (Python) | `src/lacuna_claude_plugin/mcp/` | planned |
| MCP Apps (UI resources) | `src/lacuna_claude_plugin/mcp/apps/` | planned |
| Helper CLI | `src/lacuna_claude_plugin/cli/` | `version` only |

Planned layout of a plugin (the standard Claude Code plugin structure):

```
plugins/<plugin-name>/
├── .claude-plugin/plugin.json   # manifest: name, version, description
├── skills/<skill>/SKILL.md      # model-invoked skills
├── commands/<command>.md        # slash commands
├── agents/<agent>.md            # subagents
├── hooks/hooks.json             # lifecycle hooks
└── .mcp.json                    # MCP servers bundled with the plugin
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Claude Code](https://docs.claude.com/en/docs/claude-code) — to install and run the plugins

## Install

```bash
git clone <repo-url> lacuna_claude_plugin
cd lacuna_claude_plugin
uv sync --dev
uv run pre-commit install
```

## Try the plugins in Claude Code

Add this repo as a local marketplace, then install a plugin from it:

```
/plugin marketplace add ./
/plugin install <plugin-name>@<marketplace-name>
```

Restart Claude Code after installing or changing a plugin so it picks up the new skills, commands, hooks, and MCP servers.

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

## References

- [Claude Code plugins](https://docs.claude.com/en/docs/claude-code/plugins) and [plugin marketplaces](https://docs.claude.com/en/docs/claude-code/plugin-marketplaces)
- [Agent Skills](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview)
- [Model Context Protocol](https://modelcontextprotocol.io) and the [MCP Apps extension](https://github.com/modelcontextprotocol/ext-apps)

## Releases

Releases are published to [GitHub Releases](../../releases). Each tag (`v*.*.*`) triggers a draft release with auto-generated notes via [git-cliff](https://git-cliff.org/).
