import sys
import os

# Add inner project directory to system path for Vercel & IDE static analysis
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "pid-line-tool"))

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Import Flask app entrypoint
import app
app = app.app
