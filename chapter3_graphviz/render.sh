#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

DOT_BIN="${DOT_BIN:-}"
if [[ -z "${DOT_BIN}" ]]; then
  DOT_BIN="$(command -v dot || true)"
fi
if [[ -z "${DOT_BIN}" && -x /opt/homebrew/bin/dot ]]; then
  DOT_BIN="/opt/homebrew/bin/dot"
fi
if [[ -z "${DOT_BIN}" ]]; then
  echo "error: Graphviz 'dot' not found. Install graphviz or set DOT_BIN." >&2
  exit 1
fi

for file in *.dot; do
  "$DOT_BIN" -Tsvg "$file" -o "${file%.dot}.svg"
done
