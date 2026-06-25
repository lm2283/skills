#!/usr/bin/env bash
# Convert a Markdown brief into a styled Word .docx using the pandoc pipeline
# and assets (reference.docx + lua filters) that live alongside this script.
#
# Usage:
#   ./build.sh path/to/brief.md   # absolute path, or relative to this script's parent
set -euo pipefail

# All build assets live alongside this script.
cd "$(dirname "$0")"

DOCS_DIR=".."  # skill root

build_one() {
  local src="$1"
  local out="${src%.md}.docx"
  local src_dir
  src_dir="$(dirname "$src")"

  # Sources are expected to be standard markdown (lists flush at top
  # level, 4-space indent for nested items, blank line before each list).
  # `lists_without_preceding_blankline` is kept as a tolerance for sources
  # that omit the blank line; it does no harm when one is present.
  pandoc \
    --from=markdown+lists_without_preceding_blankline \
    --reference-doc=reference.docx \
    -o "$out" \
    --resource-path="$src_dir:$DOCS_DIR:." \
    --lua-filter=figure-img.lua \
    --lua-filter=table-width.lua \
    --lua-filter=titlepage.lua \
    --lua-filter=sections.lua \
    "$src"

  # Print the output path
  echo "Built: $out"
}

if [[ $# -ne 1 ]]; then
  echo "Usage: build.sh path/to/brief.md" >&2
  exit 2
fi

arg="$1"
if [[ "$arg" = /* ]]; then
  src="$arg"
else
  src="$DOCS_DIR/$arg"
fi
[[ -f "$src" ]] || { echo "Not found: $arg" >&2; exit 1; }
build_one "$src"
