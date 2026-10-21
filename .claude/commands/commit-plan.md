Analyze all uncommitted changes using `git diff HEAD` and `git status --short`.

Propose a grouping plan for atomic commits following Conventional Commits.
Use scopes defined in CLAUDE.md.

Output format (exactly):
---
PROPOSED COMMIT PLAN
─────────────────────────────────────────
Group 1: `feat(auth): add OAuth2 PKCE flow`
  Files:
    - src/auth/pkce.py
    - src/auth/oauth.py
    - tests/auth/test_pkce.py

Group 2: `fix(api): correct 422 response schema for validation errors`
  Files:
    - src/api/error_handlers.py

Group 3: `chore(deps): bump httpx from 0.26 to 0.27`
  Files:
    - pyproject.toml
    - poetry.lock
---

Rules:
- Never group unrelated changes together
- If a file contains changes spanning multiple concerns, flag it for `git add -p`
- If any grouping is uncertain, mark it with ⚠️ and explain why

DO NOT stage or commit anything. Wait for approval.
