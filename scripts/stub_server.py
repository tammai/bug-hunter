"""A local stand-in for a third-party HTTP service: scripted responses, every request logged."""

import argparse
import json
import math
import re
import socket
import struct
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
        if "method" in rule and not isinstance(rule["method"], str):
            raise _BadScenario(f"rule {n}: method must be text")
        for m, response in enumerate(responses, 1):
            if not isinstance(response, dict):
                raise _BadScenario(f"rule {n}: each response must be an object")
            _check_response(response, f"rule {n} response {m}")
    return rules


def _check_response(r: dict, where: str) -> None:
    status = r.get("status", 200)
    if not isinstance(status, int) or isinstance(status, bool) or not 100 <= status <= 599:
        raise _BadScenario(f"{where}: status must be a number from 100 to 599")
    headers = r.get("headers", {})
    if not isinstance(headers, dict) or not all(
        isinstance(k, str) and isinstance(v, (str, int)) for k, v in headers.items()
    ):
        raise _BadScenario(f"{where}: headers must be an object of text values")
    delay = r.get("delay", 0)
    if (not isinstance(delay, (int, float)) or isinstance(delay, bool)
            or not math.isfinite(delay) or delay < 0):
        raise _BadScenario(f"{where}: delay must be a finite number of seconds")
    truncate = r.get("truncate")
    if truncate is not None and (not isinstance(truncate, int) or isinstance(truncate, bool)
                                 or truncate < 0):
        raise _BadScenario(f"{where}: truncate must be a byte count")
    for flag in ("close", "reset"):
        if not isinstance(r.get(flag, False), bool):
            raise _BadScenario(f"{where}: {flag} must be true or false")


SECRET_NAME = r"[\w.-]*(?:token|secret|api[-_]?key|password|passwd|authorization|cookie)[\w.-]*"
# Secret-named fields in any body shape, matched as text so a body cut at 64 KB, sent with
# the wrong content type, or split into multipart parts is still redacted.
JSON_STRING = re.compile(rf'("{SECRET_NAME}"\s*:\s*)"(?:[^"\\]|\\.)*"?', re.I)
JSON_BARE = re.compile(rf'("{SECRET_NAME}"\s*:\s*)(?!["{{\[\s])[^,}}\s]+', re.I)
FORM_FIELD = re.compile(rf"((?:^|[&\s;]){SECRET_NAME}=)[^&\s;]*", re.I)
MULTIPART = re.compile(
    rf'(name="{SECRET_NAME}"[^\r\n]*\r?\n(?:[^\r\n]+\r?\n)*\r?\n)[^\r\n]*', re.I
)


def _redact_text(text: str) -> str:
    text = JSON_STRING.sub(lambda m: m.group(1) + '"<redacted>"', text)
    text = JSON_BARE.sub(lambda m: m.group(1) + '"<redacted>"', text)
    text = FORM_FIELD.sub(lambda m: m.group(1) + "<redacted>", text)
    return MULTIPART.sub(lambda m: m.group(1) + "<redacted>", text)


def _redact_query(query: str) -> str:
    """Secret-named query values redacted, everything else exactly as the client sent it."""
    parts = []
    for item in query.split("&") if query else []:
        name, eq, _ = item.partition("=")
        secret = re.fullmatch(SECRET_NAME, name, re.I)
        parts.append(f"{name}=<redacted>" if eq and secret else item)
    return "&".join(parts)


def _handler(rules: list[dict], log: Path) -> type[BaseHTTPRequestHandler]:
    calls: dict[int, int] = {}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass  # the JSON log is the record; stderr stays quiet

        def _read_body(self) -> tuple[bytes, int]:
            """The whole request body (chunked or sized), so the socket is left clean."""
            kept, total = bytearray(), 0
            if "chunked" in self.headers.get("Transfer-Encoding", "").lower():
                while True:
                    size = int(self.rfile.readline().split(b";")[0].strip() or b"0", 16)
                    if size == 0:
                        while self.rfile.readline().strip():
                            pass  # trailers
                        break
                    chunk = self.rfile.read(size)
                    self.rfile.readline()
                    total += len(chunk)
                    kept += chunk[: max(0, MAX_BODY - len(kept))]
                return bytes(kept), total
            remaining = int(self.headers.get("Content-Length") or 0)
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 65536))
                if not chunk:
                    break
                remaining -= len(chunk)
                total += len(chunk)
                kept += chunk[: max(0, MAX_BODY - len(kept))]
            return bytes(kept), total

        def _record(self, body: bytes, total: int, note: str = "") -> None:
            url = urlsplit(self.path)
            text = body.decode("utf-8", errors="replace")
            entry = {
                "time": round(time.time(), 3), "method": self.command, "path": url.path,
                "query": _redact_query(url.query),
                "headers": {k: "<redacted>" if SECRET_HEADER.search(k) else v
                            for k, v in self.headers.items()},
                "body": _redact_text(text),
                "body_bytes": total,
            }
            if note:
                entry["note"] = note
            with lock, log.open("a", encoding="utf-8") as out:
                out.write(json.dumps(entry) + "\n")

        def _respond(self) -> None:
            try:
                body, total = self._read_body()
            except ValueError:
                # The client under test sent a broken body: that's evidence, so log it and
                # answer instead of dropping the connection.
                self._record(b"", 0, note="malformed chunk size or Content-Length")
                self.close_connection = True
                return self._send({"status": 400, "body": {"error": "malformed request body"}})
            self._record(body, total)
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
            if response.get("reset"):
                # Linger 0 makes close() send RST: a reset, not a clean close.
                self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                                           struct.pack("ii", 1, 0))
                self.close_connection = True
                self.connection.close()
                return
            if response.get("close"):
                self.close_connection = True
                self.connection.close()
                return
            body = response.get("body", "")
            data = (json.dumps(body) if not isinstance(body, str) else body).encode("utf-8")
            status = int(response.get("status", 200))
            bodiless = status < 200 or status in (204, 304)
            if bodiless:
                data = b""  # these statuses carry no body; one would corrupt the next response
            headers = {"content-type": ("Content-Type", "application/json"
                                        if not isinstance(body, str)
                                        else "text/plain; charset=utf-8"),
                       "content-length": ("Content-Length", str(len(data)))}
            for name, value in response.get("headers", {}).items():
                headers[name.lower()] = (name, str(value))  # scripted values replace defaults
            self.send_response(status)
            for name, value in headers.values():
                self.send_header(name, value)
            self.end_headers()
            if self.command == "HEAD" or bodiless:
                return
            truncate = response.get("truncate")
            self.wfile.write(data if truncate is None else data[:truncate])
            if truncate is not None:
                self.wfile.flush()
                self.close_connection = True
                self.connection.close()

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
