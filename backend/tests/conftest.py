import sys
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="boss-workbench-tests-"))
os.environ.setdefault("BOSS_WORKBENCH_DATA_DIR", str(TEST_DATA_DIR))
