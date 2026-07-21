import sys
import os

# Add inner folder to python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pid-line-tool'))

from app import app
