"""A local stand-in for a third-party HTTP service: scripted responses, every request logged."""

import argparse
import json
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

SECRET_HEADER = re.compile(r"authorization|cookie|token|secret|api[-_]?key|password", re.I)
MAX_BODY = 65536


class _BadScenario(Exception):
    pass


def _load(path: Path) -> list[dict]:
    try:
        rules = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _BadScenario(f"can't read {path} as JSON: {exc}") from exc
    if not isinstance(rules, list):
        raise _BadScenario("the scenario must be a list of rules")
    for n, rule in enumerate(rules, 1):
        if not isinstance(rule, dict) or not isinstance(rule.get("path"), str):
            raise _BadScenario(f"rule {n} needs a path")
        responses = rule.get("responses")
        if not isinstance(responses, list) or not responses:
            raise _BadScenario(f"rule {n} needs a non-empty responses list")
        if not all(isinstance(r, dict) for r in responses):
            raise _BadScenario(f"rule {n}: each response must be an object")
    return rules


def _handler(rules: list[dict], log: Path) -> type[BaseHTTPRequestHandler]:
    calls: dict[int, int] = {}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass  # the JSON log is the record; stderr stays quiet

        def _record(self, body: bytes) -> None:
            url = urlsplit(self.path)
            entry = {
                "time": round(time.time(), 3), "method": self.command, "path": url.path,
                "query": url.query,
                "headers": {k: "<redacted>" if SECRET_HEADER.search(k) else v
                            for k, v in self.headers.items()},
                "body": body[:MAX_BODY].decode("utf-8", errors="replace"),
            }
            with lock, log.open("a", encoding="utf-8") as out:
                out.write(json.dumps(entry) + "\n")

        def _respond(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(min(length, MAX_BODY)) if length else b""
            self._record(body)
            path = urlsplit(self.path).path
            match = next((n for n, r in enumerate(rules)
                          if r["path"] == path
                          and r.get("method", self.command).upper() == self.command), None)
            if match is None:
                return self._send({"status": 404,
                                   "body": {"error": f"no scenario for {self.command} {path}"}})
            with lock:
                count = calls.get(match, 0)
                calls[match] = count + 1
            responses = rules[match]["responses"]
            # Responses play in order; the last one repeats for every later call.
            self._send(responses[min(count, len(responses) - 1)])

        def _send(self, response: dict) -> None:
            time.sleep(float(response.get("delay", 0)))
            if response.get("close"):
                self.close_connection = True
                self.connection.close()
                return
            body = response.get("body", "")
            data = (json.dumps(body) if not isinstance(body, str) else body).encode("utf-8")
            self.send_response(int(response.get("status", 200)))
            headers = {"Content-Type": "application/json" if not isinstance(body, str)
                       else "text/plain; charset=utf-8", **response.get("headers", {})}
            for name, value in headers.items():
                self.send_header(name, str(value))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = _respond

    return Handler


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        rules = _load(Path(args.scenario))
        # Loopback only: the stub must never be reachable from outside this machine.
        server = ThreadingHTTPServer(("127.0.0.1", args.port), _handler(rules, Path(args.log)))
    except _BadScenario as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: can't listen on 127.0.0.1:{args.port}: {exc.strerror}", file=sys.stderr)
        return 1
    print(f"listening on http://127.0.0.1:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(_main())
