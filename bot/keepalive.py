"""
یک سرور HTTP خیلی ساده فقط برای اینکه Render به‌عنوان Web Service سرویس بات را زنده نگه دارد.
"""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import os


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"BEHI PLAY bot is running")

    def log_message(self, format, *args):
        pass  # لاگ‌های اضافی رو خاموش می‌کنیم


def start_keepalive_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
