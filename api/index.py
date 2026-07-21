import sys
import os

# Absolute path resolution for Vercel serverless environment
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INNER_DIR = os.path.join(ROOT_DIR, "pid-line-tool")

if INNER_DIR not in sys.path:
    sys.path.insert(0, INNER_DIR)

from app import app
