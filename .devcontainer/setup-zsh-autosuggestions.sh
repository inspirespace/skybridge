#!/usr/bin/env bash
set -euo pipefail

ZSHRC="${HOME}/.zshrc"

# Remove zsh-autosuggestions to prevent paste duplication in the devcontainer terminal.
if [[ -f "${ZSHRC}" ]]; then
  python - "$ZSHRC" <<'PY'
import pathlib
import re
import sys

zshrc_path = pathlib.Path(sys.argv[1])
content = zshrc_path.read_text()

def strip_plugin(match: re.Match) -> str:
    current = match.group(1).strip()
    items = [p for p in current.split() if p]
    items = [p for p in items if p != "zsh-autosuggestions"]
    return f"plugins=({' '.join(items)})" if items else "plugins=()"

if "plugins=(" in content:
    updated = re.sub(r"plugins=\(([^)]*)\)", strip_plugin, content, count=1)
    zshrc_path.write_text(updated)
PY
fi
