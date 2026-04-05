#!/usr/bin/env python3
"""
Iterative Graphviz renderer for this directory.

Features:
- Rebuilds both PNG and SVG when any *.dot file in this folder changes.
- Auto-finds Graphviz `dot` (respects DOT_BIN env, then PATH, then /opt/homebrew/bin/dot).
- Prints which files were re-rendered; keeps looping until interrupted (Ctrl-C).

Usage:
  ./graphviz_watch.py        # watch and rebuild on change
  DOT_BIN=/opt/homebrew/bin/dot ./graphviz_watch.py
"""

import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def find_dot():
    dot_bin = os.environ.get("DOT_BIN")
    if dot_bin and Path(dot_bin).is_file():
        return dot_bin
    for candidate in ("dot", "/opt/homebrew/bin/dot"):
        path = shutil.which(candidate) if candidate == "dot" else candidate
        if path and Path(path).is_file():
            return path
    raise FileNotFoundError(
        "Graphviz 'dot' not found. Install graphviz or set DOT_BIN to the dot binary."
    )


def render(dot_bin: str, dot_file: Path):
    svg_out = dot_file.with_suffix(".svg")
    png_out = dot_file.with_suffix(".png")
    for out, fmt in ((svg_out, "svg"), (png_out, "png")):
        subprocess.run(
            [dot_bin, f"-T{fmt}", str(dot_file), "-o", str(out)],
            check=True,
        )


def snapshot_mtimes():
    return {
        p: p.stat().st_mtime
        for p in ROOT.glob("*.dot")
    }


def main():
    dot_bin = find_dot()
    print(f"[watch] using dot: {dot_bin}")
    mtimes = snapshot_mtimes()
    # initial render
    for p in sorted(mtimes):
        render(dot_bin, p)
        print(f"[render] {p.name} -> svg/png")

    try:
        while True:
            time.sleep(1.0)
            current = snapshot_mtimes()
            changed = [p for p, t in current.items() if mtimes.get(p) != t]
            if changed:
                for p in sorted(changed):
                    render(dot_bin, p)
                    print(f"[render] {p.name} -> svg/png (changed)")
                mtimes = current
    except KeyboardInterrupt:
        print("\n[watch] stopped")


if __name__ == "__main__":
    import shutil
    main()
