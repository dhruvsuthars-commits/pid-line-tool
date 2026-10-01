import sys
import os
import json
import importlib.util

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "pid-line-tool"))

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

app_module_path = os.path.join(PROJECT_DIR, "app.py")
spec = importlib.util.spec_from_file_location("app", app_module_path)
app_module = importlib.util.module_from_spec(spec)
sys.modules["app"] = app_module
spec.loader.exec_module(app_module)

app = app_module.app

class VercelPathFixMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        if environ.get("HTTP_X_DEBUG") == "1":
            start_response("200 OK", [("Content-Type", "application/json")])
            debug_info = {k: str(v) for k, v in environ.items() if isinstance(v, (str, int))}
            return [json.dumps(debug_info, indent=2).encode("utf-8")]
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)
