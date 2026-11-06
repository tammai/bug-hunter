"""A local stand-in for a third-party HTTP service: scripted responses, every request logged."""

import argparse
import json
import re
import socket
import struct
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

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
    if not isinstance(delay, (int, float)) or isinstance(delay, bool) or delay < 0:
        raise _BadScenario(f"{where}: delay must be a number of seconds")
    truncate = r.get("truncate")
    if truncate is not None and (not isinstance(truncate, int) or truncate < 0):
        raise _BadScenario(f"{where}: truncate must be a byte count")
    for flag in ("close", "reset"):
        if not isinstance(r.get(flag, False), bool):
            raise _BadScenario(f"{where}: {flag} must be true or false")


def _redact_pairs(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(k, "<redacted>" if SECRET_HEADER.search(k) else v) for k, v in pairs]


def _redact_json(value: object) -> object:
    if isinstance(value, dict):
        return {k: "<redacted>" if SECRET_HEADER.search(str(k)) else _redact_json(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_json(v) for v in value]
    return value


def _redact_body(body: str, content_type: str) -> str:
    """Secret-named fields in a form or JSON body; the log is pasted into drafts."""
    if "json" in content_type:
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return body
        redacted = _redact_json(parsed)
        return body if redacted == parsed else json.dumps(redacted)
    if "x-www-form-urlencoded" in content_type:
        pairs = parse_qsl(body, keep_blank_values=True)
        redacted_pairs = _redact_pairs(pairs)
        # Rewrite only when something was redacted, so the logged body stays what was sent.
        return body if redacted_pairs == pairs else urlencode(redacted_pairs, safe="<>")
    return body


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

        def _record(self, body: bytes, total: int) -> None:
            url = urlsplit(self.path)
            text = body.decode("utf-8", errors="replace")
            entry = {
                "time": round(time.time(), 3), "method": self.command, "path": url.path,
                "query": urlencode(_redact_pairs(parse_qsl(url.query, keep_blank_values=True)),
                                   safe="<>"),
                "headers": {k: "<redacted>" if SECRET_HEADER.search(k) else v
                            for k, v in self.headers.items()},
                "body": _redact_body(text, self.headers.get("Content-Type", "")),
                "body_bytes": total,
            }
            with lock, log.open("a", encoding="utf-8") as out:
                out.write(json.dumps(entry) + "\n")

        def _respond(self) -> None:
            body, total = self._read_body()
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
            headers = {"content-type": ("Content-Type", "application/json"
                                        if not isinstance(body, str)
                                        else "text/plain; charset=utf-8"),
                       "content-length": ("Content-Length", str(len(data)))}
            for name, value in response.get("headers", {}).items():
                headers[name.lower()] = (name, str(value))  # scripted values replace defaults
            self.send_response(int(response.get("status", 200)))
            for name, value in headers.values():
                self.send_header(name, value)
            self.end_headers()
            if self.command == "HEAD":
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
