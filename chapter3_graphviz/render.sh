#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

for file in *.dot; do
  dot -Tsvg "$file" -o "${file%.dot}.svg"
done
