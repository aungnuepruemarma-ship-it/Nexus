import sys
from pathlib import Path

# Make the repo root importable so `import ccs` works under pytest and scripts.
sys.path.insert(0, str(Path(__file__).resolve().parent))
