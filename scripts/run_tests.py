import sys
import os
from pathlib import Path

# Ensure project root is on sys.path when tests import 'app'
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ['PYTHONPATH'] = str(ROOT)

import pytest

if __name__ == '__main__':
    # Run the full test suite
    raise SystemExit(pytest.main(['-q']))
