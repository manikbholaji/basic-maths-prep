import os
import sys
from pathlib import Path

# Enable E2E tests
os.environ['RUN_E2E'] = 'true'

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

if __name__ == '__main__':
    res = pytest.main(['-vv', '-r', 'a'])
    print('PYTEST_EXIT_CODE:', res)
    sys.exit(res)
