#!/usr/bin/env bash
# deep-research-os installer wrapper.
#   ./install.sh                      # copy into every detected agent skills dir
#   ./install.sh --platform opencode --link   # symlink into opencode only
#   ./install.sh --deps              # also create .venv and install requirements
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/scripts/install.py" "$@"
