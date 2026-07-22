import sys
import os
import importlib.util

# Add inner project directory to system path for Vercel & IDE static analysis
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "pid-line-tool"))

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Dynamically import app module to prevent static linter unresolved module warnings
app_module_path = os.path.join(PROJECT_DIR, "app.py")
spec = importlib.util.spec_from_file_location("app", app_module_path)
app_module = importlib.util.module_from_spec(spec)
sys.modules["app"] = app_module
spec.loader.exec_module(app_module)

app = app_module.app
