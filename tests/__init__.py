import sys
from pathlib import Path

# Tests import the app's top-level modules (farm, chart, ...) like island.py does.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
