# Container for deploying the weather MCP server over streamable HTTP (e.g. Cloud Run).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
COPY server.py widget.html ./
# Resolve the script's inline (PEP 723) dependencies at build time, not on cold start.
RUN uv sync --script server.py

ENV HOST=0.0.0.0 PORT=8080
CMD ["uv", "run", "--quiet", "--script", "server.py", "--http"]
