#!/usr/bin/env bash
# Renames the project from "lacuna" to a user-supplied name.
# Run once after cloning the template, before your first commit.
#
# Usage:  bash shell/bootstrap.sh <new-name>
#         bash shell/bootstrap.sh myproject
#
# The script rewrites file contents and renames the source directory in-place.
# It is idempotent when re-run with the same name, and safe to abort mid-run
# because it validates inputs before touching anything.

set -euo pipefail

# ── helpers ──────────────────────────────────────────────────────────────────

usage() {
    echo "Usage: $0 <new-project-name>"
    echo ""
    echo "  <new-project-name>  lowercase letters, digits, and hyphens only"
    echo "                      (e.g. my-project, foobar, cool-tool)"
    exit 1
}

die() { echo "error: $1" >&2; exit 1; }

# Portable in-place sed (BSD/macOS vs GNU)
sed_i() {
    if sed --version 2>/dev/null | grep -q GNU; then
        sed -i "$@"
    else
        sed -i '' "$@"
    fi
}

# ── argument validation ───────────────────────────────────────────────────────

[[ $# -eq 1 ]] || usage

NEW_NAME="$1"

# Must be a valid Python project name: lowercase letters, digits, hyphens
[[ "$NEW_NAME" =~ ^[a-z][a-z0-9-]*$ ]] || \
    die "name must start with a lowercase letter and contain only lowercase letters, digits, and hyphens"

[[ "$NEW_NAME" != "lacuna" ]] || die "new name must differ from the current name (lacuna)"

OLD_NAME="lacuna"
OLD_PKG="lacuna"

# Python package name: hyphens → underscores
NEW_PKG="${NEW_NAME//-/_}"

# Title-case: capitalise first letter of each hyphen-separated word, rejoin with hyphen
# lacuna → Lacuna,  my-tool → My-Tool
OLD_TITLE="Lacuna"
NEW_TITLE="$(echo "$NEW_NAME" | awk -F'-' '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) substr($i,2); OFS="-"; print}')"

# ── locate repo root ──────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SRC_OLD="$ROOT/src/$OLD_PKG"
SRC_NEW="$ROOT/src/$NEW_PKG"

[[ -d "$SRC_OLD" ]] || die "source directory $SRC_OLD not found — already renamed?"

echo "Renaming '$OLD_NAME' → '$NEW_NAME' (package: $OLD_PKG → $NEW_PKG)"
echo ""

# ── files that contain text to replace ───────────────────────────────────────

TEXT_FILES=(
    "$ROOT/pyproject.toml"
    "$ROOT/README.md"
    "$ROOT/CONTRIBUTING.md"
    "$ROOT/CLAUDE.md"
    "$ROOT/.env.example"
)

# All Python source files under src/ and tests/
while IFS= read -r -d '' f; do
    TEXT_FILES+=("$f")
done < <(find "$ROOT/src" "$ROOT/tests" -name "*.py" -print0)

# ── text replacement ──────────────────────────────────────────────────────────
# Order matters: most-specific patterns first to avoid double-substitution.

for f in "${TEXT_FILES[@]}"; do
    [[ -f "$f" ]] || continue

    # 1. Title-case references  (Lacuna → My-Tool)
    # 2. Package/module name  (lacuna → new_pkg, covers imports, paths, pyproject fields)
    # pyproject authors line is excluded from both — left exactly as templated.
    if [[ "$f" == "$ROOT/pyproject.toml" ]]; then
        sed_i "/^authors/,/^\]/!s/${OLD_TITLE}/${NEW_TITLE}/g" "$f"
        sed_i "/^authors/,/^\]/!s/${OLD_PKG}/${NEW_PKG}/g" "$f"
    else
        sed_i "s/${OLD_TITLE}/${NEW_TITLE}/g" "$f"
        sed_i "s/${OLD_PKG}/${NEW_PKG}/g" "$f"
    fi

    # 3. If the project name uses hyphens, fix the pyproject `name` field and doc references
    #    that should use the hyphenated form (already replaced to underscored in step 2).
    if [[ "$NEW_NAME" != "$NEW_PKG" ]]; then
        sed_i "s/^name = \"${NEW_PKG}\"$/name = \"${NEW_NAME}\"/" "$f"
        sed_i "s/ ${NEW_PKG}\b/ ${NEW_NAME}/g" "$f"
    fi
done

# ── remove environment caches (contain absolute paths, must be rebuilt) ───────

rm -rf "$ROOT/.venv" "$ROOT/.mypy_cache" "$ROOT/.ruff_cache" "$ROOT/.pytest_cache"

# ── rename source directory ───────────────────────────────────────────────────

if [[ "$OLD_PKG" != "$NEW_PKG" ]]; then
    mv "$SRC_OLD" "$SRC_NEW"
    echo "Moved: src/$OLD_PKG/ → src/$NEW_PKG/"
fi

# ── self-destruct ─────────────────────────────────────────────────────────────

rm -- "${BASH_SOURCE[0]}"
rmdir "$ROOT/shell" 2>/dev/null || true  # remove dir only if now empty

# ── done ─────────────────────────────────────────────────────────────────────

echo ""
echo "Done. Next steps:"
echo "  1. Review the changes:  git diff"
echo "  2. Install deps:        uv sync --dev"
echo "  3. Run tests:           uv run pytest"
echo "  4. Commit:              git add -A && git commit -m 'chore: rename project to $NEW_NAME'"
