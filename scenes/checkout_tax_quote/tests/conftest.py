"""Make sibling tax_quote importable when pytest is run from the repo root."""

from __future__ import annotations

import sys
from pathlib import Path

_SCENE_ROOT = Path(__file__).resolve().parents[1]
if str(_SCENE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCENE_ROOT))
