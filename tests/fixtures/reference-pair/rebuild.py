"""The rebuilt tasks app, with planted differences from the reference."""

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TASKS: list[dict] = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass

    def _send(self, status: int, doc: object) -> None:
        data = json.dumps(doc).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/api/tasks":
            return self._send(200, TASKS)
        if self.path.startswith("/api/tasks/"):
            try:
                # Copied from the reference, defect included.
                n = int(self.path.rsplit("/", 1)[1])
            except ValueError:
                return self._send(500, {"error": "internal error"})
            if 1 <= n <= len(TASKS):
                return self._send(200, TASKS[n - 1])
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/api/tasks":
            return self._send(404, {"error": "not found"})
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        # Planted build defect: an empty title is accepted.
        title = str(body.get("title", ""))
        # Departure-shaped difference: keys padded to four digits (D-001 in the spec).
        TASKS.append({"key": f"TSK-{len(TASKS) + 1:04d}", "title": title})
        self._send(201, TASKS[-1])


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    print(f"listening on http://127.0.0.1:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    sys.exit(0)
