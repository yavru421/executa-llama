import sys
import os
# Ensure project root is on sys.path for tests
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# Also add the package directory so imports like `import tools` (package-local) resolve in tests
PKG_DIR = os.path.join(ROOT, 'llamatrama_agent')
if os.path.isdir(PKG_DIR) and PKG_DIR not in sys.path:
    sys.path.insert(0, PKG_DIR)
