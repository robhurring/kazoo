#!/usr/bin/env bash
# Build the example graphs in your XDG kazoo dir.
#
# Default: import from the gzipped snapshots (fast).
# --rebuild: drop and re-seed from schema.cypher + seed.cypher (slow, source of truth).
#
# Usage: ./examples/build.sh [--rebuild] [office|social|all]
set -euo pipefail

cd "$(dirname "$0")"

rebuild=false
if [[ "${1:-}" == "--rebuild" ]]; then
  rebuild=true
  shift
fi

import_one() {
  local name="$1"
  echo "==> importing '$name'"
  gunzip -c "$name/$name.graph.gz" | kazoo --db "$name" db import --force
}

rebuild_one() {
  local name="$1"
  echo "==> rebuilding '$name'"
  kazoo --db "$name" db rm --yes >/dev/null 2>&1 || true
  kazoo --db "$name" db init >/dev/null
  kazoo --db "$name" schema apply < "$name/schema.cypher"
  kazoo --db "$name" schema apply --no-atomic < "$name/seed.cypher"
  kazoo --db "$name" db stats
  kazoo --db "$name" db export | gzip -9 > "$name/$name.graph.gz"
}

do_one() { if $rebuild; then rebuild_one "$1"; else import_one "$1"; fi; }

target="${1:-all}"
case "$target" in
  office|social) do_one "$target" ;;
  all) do_one office; do_one social ;;
  *) echo "usage: $0 [--rebuild] [office|social|all]" >&2; exit 2 ;;
esac
