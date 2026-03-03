#!/usr/bin/env python3
"""Minimal HTTP server to trigger import_recipe.py from the local network."""

import json
import logging
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

HOST = "0.0.0.0"
PORT = 5050
SCRIPT_DIR = "/mnt/usb/dagelijksekost-paprika"
COMMAND = ["/home/tomklaasen/.local/bin/uv", "run", "import_recipe.py"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/run":
            self.send_json(404, {"error": "Not found"})
            return

        log.info("Running import_recipe.py ...")
        try:
            result = subprocess.run(
                COMMAND,
                cwd=SCRIPT_DIR,
                capture_output=True,
                text=True,
                timeout=120,
            )
            body = {
                "ok": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
            status = 200 if result.returncode == 0 else 500
            log.info("Finished with exit code %d", result.returncode)
        except subprocess.TimeoutExpired:
            body = {"ok": False, "error": "Script timed out after 120 seconds"}
            status = 504
            log.error("Script timed out")
        except Exception as e:
            body = {"ok": False, "error": str(e)}
            status = 500
            log.exception("Unexpected error")

        self.send_json(status, body)

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status": "ok"})
            return
        self.send_json(405, {"error": "Use POST /run"})

    def send_json(self, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        log.info(format, *args)


def main():
    server = HTTPServer((HOST, PORT), Handler)
    log.info("Listening on %s:%d", HOST, PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down")
        server.server_close()


if __name__ == "__main__":
    main()
