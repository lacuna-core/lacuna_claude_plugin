# lacuna_claude_plugin

A sandbox for experimenting with the Claude extension ecosystem: plugin **marketplaces**, **plugins**, **skills**, **slash commands**, **subagents**, **hooks**, **MCP servers/tools**, and **MCP Apps** (interactive UI returned by MCP tools).

This is a learning and prototyping repo, not a product. Each experiment should be small and self-contained, with a short note on what it tests and what we learned.

## What's in here

| Area | Location | Status |
|------|----------|--------|
| Plugin marketplace (`lacuna`) | `.claude-plugin/marketplace.json` | 1 plugin |
| Plugins | `plugins/<plugin-name>/` | `weather` |
| MCP servers (Python) | `plugins/<plugin-name>/server.py` | `weather` |
| Skills | `plugins/<plugin-name>/skills/` | `weather` |
| Commands, agents, hooks | `plugins/<plugin-name>/` | planned |
| MCP Apps (UI resources) | `plugins/<plugin-name>/widget.html` | `weather` |
| Helper CLI | `src/lacuna_claude_plugin/cli/` | `version` only |

### Plugins

| Plugin | What it does | What it exercises |
|--------|--------------|-------------------|
| [`weather`](plugins/weather) | Current weather and up-to-16-day forecasts for any place, from [Open-Meteo](https://open-meteo.com) (free, no API key), rendered as weather cards. The current-conditions card has **Next 7 days** / **Next 14 days** buttons | Python MCP server packaged in a plugin; a skill that steers tool use; an MCP App (`ui://` widget whose buttons send `ui/message`, so card actions become user input to Claude) |

Layout of a plugin (the standard Claude Code plugin structure):

```
plugins/<plugin-name>/
├── .claude-plugin/plugin.json   # manifest: name, version, description
├── skills/<skill>/SKILL.md      # model-invoked skills
├── commands/<command>.md        # slash commands
├── agents/<agent>.md            # subagents
├── hooks/hooks.json             # lifecycle hooks
├── .mcp.json                    # MCP servers bundled with the plugin
├── server.py                    # MCP server: a self-contained uv script (PEP 723)
└── widget.html                  # MCP App UI: one self-contained HTML file, served as a ui:// resource
```

Installed plugins are copied into Claude Code's plugin cache, so each plugin must be self-contained. It can't import code from `src/` or from other plugins.

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

## Using the plugins

MCP servers in these plugins run via `uv`, so `uv` must be on your `PATH`. Once a plugin is loaded, try something like *"will it rain in Lisbon this weekend?"*

### Production: install from GitHub

Install the released plugin from `main` on GitHub:

```bash
claude plugin install weather --marketplace lacuna-core/lacuna_claude_plugin
# or, inside Claude Code:
/plugin install weather --marketplace lacuna-core/lacuna_claude_plugin
```

This adds the `lacuna` marketplace (a local snapshot of the repo) and installs the plugin from that snapshot. Installed plugins **don't follow GitHub automatically**. To pick up a newer release:

```bash
claude plugin marketplace update lacuna   # refresh the marketplace snapshot from GitHub
claude plugin update weather              # install the newer plugin version
```

Then restart Claude Code. A plugin only updates when its `version` changes, so pushing code without a version bump does nothing for installed users.

### Development: run from your working tree

**Fast loop: load the plugin for one session, no install.** This picks up uncommitted edits on every launch:

```bash
claude --plugin-dir ./plugins/weather   # one plugin
claude --plugin-dir ./plugins           # every plugin in the repo
```

Edit the skill, manifest, or `server.py`, then quit and relaunch to see the change. If the same plugin is also installed from a marketplace, uninstall it first (`claude plugin uninstall weather`) so you know which copy is running.

**Full install test: exercise the real install path from the local clone.** This checks the marketplace entry and that the plugin works once copied into the plugin cache:

```bash
claude plugin marketplace add ./
claude plugin install weather@lacuna
# after further edits:
claude plugin marketplace update lacuna && claude plugin update weather
```

**Before pushing**, run the checks:

```bash
uv run ruff check && uv run mypy && uv run pytest
claude plugin validate .                  # marketplace manifest
claude plugin validate plugins/weather    # plugin manifest, skills
```

To debug an MCP server outside Claude Code, run it directly: `uv run --script plugins/weather/server.py` (it speaks MCP over stdio). Inside Claude Code, `/mcp` shows whether the server connected.

**Remote server over HTTP with ngrok.** The plugin's `.mcp.json` points at the remote endpoint `https://steersman-nurture-sherry.ngrok-free.dev/mcp`, so the server and tunnel must be running for the plugin's tools to work:

1. Install ngrok and log in (one time). Get the authtoken from https://dashboard.ngrok.com:

   ```bash
   brew install ngrok
   ngrok config add-authtoken <YOUR_TOKEN>
   ```

2. Start the server over streamable HTTP. It listens on `http://127.0.0.1:8000/mcp`:

   ```bash
   uv run --script plugins/weather/server.py --http
   ```

3. Optional: check the server locally with the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) (needs Node.js). In a second terminal, run:

   ```bash
   npx @modelcontextprotocol/inspector
   ```

   - It opens the Inspector UI in your browser (`http://localhost:6274`).
   - Set **Transport Type** to `Streamable HTTP` and **URL** to `http://127.0.0.1:8000/mcp`, then click **Connect**.
   - Under **Tools**, click **List Tools** and run `get_current_weather` with a `location`, e.g. `Lisbon`.
   - After step 4 you can connect to `https://steersman-nurture-sherry.ngrok-free.dev/mcp` the same way to check the tunnel.

4. In another terminal, start the tunnel on the static domain:

   ```bash
   ngrok http 8000 --host-header=rewrite --url=https://steersman-nurture-sherry.ngrok-free.dev
   ```

   - `--host-header=rewrite` is required. The SDK only accepts `localhost`/`127.0.0.1` Host headers and answers anything else with `421 Invalid Host header`.

5. Connect a client to `https://steersman-nurture-sherry.ngrok-free.dev/mcp`:
   - **Claude Code:** nothing to do. The plugin's `.mcp.json` already uses this URL. Check with `/mcp`.
   - **claude.ai / Claude Desktop chat:** Settings → Connectors → Add custom connector, paste the URL, and leave the OAuth fields empty.

6. Stop ngrok (Ctrl+C) when you're done. The server has no authentication, so anyone with the URL can call it.

**MCP Apps widgets only render in hosts that support MCP Apps**, such as the Claude desktop and web apps. Claude Code in the terminal gets the tools' text output instead, which is a complete answer on its own. To see the cards, add the server to a host that renders MCP Apps, for example in Claude Desktop's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "weather": {
      "command": "uv",
      "args": ["run", "--quiet", "--script", "/absolute/path/to/lacuna_claude_plugin/plugins/weather/server.py"]
    }
  }
}
```

### Releasing a plugin

1. Bump `version` in **both** `plugins/<name>/.claude-plugin/plugin.json` and that plugin's entry in `.claude-plugin/marketplace.json`. They must match.
2. Commit (`chore(plugin): release weather 0.2.0`) and push to `main`.
3. Tag the release: `claude plugin tag plugins/<name> --push`. This creates `<name>--v<version>`, checking first that the two manifests agree. Plugin tags don't trigger the repo's `v*.*.*` release workflow.

Users then get it with `claude plugin marketplace update lacuna && claude plugin update <name>`.

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
