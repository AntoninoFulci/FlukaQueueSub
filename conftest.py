import sys
from pathlib import Path

# Run tests without installing: put this repo on sys.path for `backends` / `core`.
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
