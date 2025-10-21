import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))


try:
    import settings
except ImportError:
    raise ImportError("Cannot import settings.py. Make sure PROJECT_ROOT is correct.")

def get_settings():
    return settings