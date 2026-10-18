"""deep-research-os — an agent-native research operating system.

Modules under ``scripts/`` use flat imports (`from lib.util import ...`).
This file guarantees the ``scripts/`` directory is importable whether the code
is executed directly, imported as a package, or used from tests.
"""

import os as _os
import sys as _sys

_HERE = _os.path.dirname(_os.path.abspath(__file__))
if _HERE not in _sys.path:
    _sys.path.insert(0, _HERE)

__version__ = "1.0.0"
