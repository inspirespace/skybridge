#!/usr/bin/env bash
set -euo pipefail

ZSHRC="${HOME}/.zshrc"
ZSH_CUSTOM="${ZSH_CUSTOM:-${HOME}/.oh-my-zsh/custom}"
PLUGIN_DIR="${ZSH_CUSTOM}/plugins/zsh-autosuggestions"

if [[ ! -d "${PLUGIN_DIR}" ]]; then
  git clone https://github.com/zsh-users/zsh-autosuggestions "${PLUGIN_DIR}"
elif command -v git >/dev/null 2>&1; then
  git -C "${PLUGIN_DIR}" pull --ff-only || true
fi

if [[ -f "${ZSHRC}" ]] && ! grep -q "zsh-autosuggestions" "${ZSHRC}"; then
  python - "$ZSHRC" <<'PY'
import pathlib
import re
import sys

zshrc_path = pathlib.Path(sys.argv[1])
content = zshrc_path.read_text()

def add_plugin(match: re.Match) -> str:
    current = match.group(1).strip()
    items = [p for p in current.split() if p]
    if "zsh-autosuggestions" not in items:
        items.append("zsh-autosuggestions")
    return f"plugins=({' '.join(items)})"

if "plugins=(" in content:
    updated = re.sub(r"plugins=\(([^)]*)\)", add_plugin, content, count=1)
else:
    updated = content.rstrip() + "\nplugins=(git zsh-autosuggestions)\n"

zshrc_path.write_text(updated)
PY
fi
