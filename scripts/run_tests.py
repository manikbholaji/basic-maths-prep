import sys
import os

# Ensure project root is on sys.path when tests import 'app'
ROOT = r'f:/My Project/shapers_academic_advisor'
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ['PYTHONPATH'] = ROOT

import pytest

if __name__ == '__main__':
    # Run the full test suite
    raise SystemExit(pytest.main(['-q']))
