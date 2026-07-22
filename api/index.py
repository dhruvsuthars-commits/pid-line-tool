import sys
import os

# Absolute path resolution for Vercel serverless environment & local static analyzers
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INNER_DIR = os.path.join(ROOT_DIR, "pid-line-tool")

for path_entry in [ROOT_DIR, INNER_DIR]:
    if path_entry not in sys.path:
        sys.path.insert(0, path_entry)

try:
    from app import app
except ImportError:
    from pid_line_tool.app import app
