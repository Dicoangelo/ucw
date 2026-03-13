#!/usr/bin/env bash
# UCW Setup — One command to install and configure
# Usage: curl -fsSL <url>/setup.sh | bash
#   or:  ./setup.sh

set -euo pipefail

echo "==================================="
echo "  UCW — Universal Cognitive Wallet"
echo "==================================="
echo

# 1. Check Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python 3.10+ required. Install from https://python.org"
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "ERROR: Python 3.10+ required (found $PY_VER)"
    exit 1
fi
echo "[1/5] Python $PY_VER ✓"

# 2. Install UCW
if command -v pipx &>/dev/null; then
    echo "[2/5] Installing via pipx..."
    pipx install ucw 2>/dev/null || pipx install . 2>/dev/null || {
        echo "  pipx install failed, falling back to pip..."
        python3 -m pip install --user . 2>/dev/null || python3 -m pip install .
    }
elif python3 -m pip install --help &>/dev/null; then
    echo "[2/5] Installing via pip..."
    python3 -m pip install --user . 2>/dev/null || python3 -m pip install .
else
    echo "ERROR: pip not found. Install pip first."
    exit 1
fi

# Verify install
if ! python3 -c "import ucw" 2>/dev/null; then
    echo "ERROR: UCW import failed after install"
    exit 1
fi
echo "  UCW installed ✓"

# 3. Initialize
echo "[3/5] Initializing UCW..."
python3 -m ucw init

# 4. Generate MCP config
echo "[4/5] MCP configuration:"
echo
MCP_JSON=$(python3 -c "
import json, shutil, sys
ucw_path = shutil.which('ucw') or sys.executable
config = {'mcpServers': {'ucw': {'command': ucw_path, 'args': ['server']}}}
print(json.dumps(config, indent=2))
")
echo "$MCP_JSON"
echo

# 5. Instructions
echo "[5/5] Next steps:"
echo
echo "  Claude Desktop:"
echo "    1. Settings > Developer > Edit Config"
echo "    2. Paste the JSON above"
echo "    3. Restart Claude Desktop"
echo
echo "  Claude Code:"
echo "    Add to ~/.claude/settings.json:"
echo "    $MCP_JSON"
echo
echo "  Verify it works:"
echo "    ucw status"
echo
echo "==================================="
echo "  UCW ready. Start a conversation!"
echo "==================================="
