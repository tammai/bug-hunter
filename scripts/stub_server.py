"""A local stand-in for a third-party HTTP service: scripted responses, every request logged."""

import argparse
import email.parser
import email.policy
import html
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
from urllib.parse import unquote_plus, urlsplit

# A name or a value with one of these words may carry a credential.
SECRET_WORD = re.compile(
    r"token|secret|api[-_ ]?key|password|passwd|authorization|cookie|credential"
    r"|private[-_ ]?key|session", re.I,
)
MAX_BODY = 65536  # logged
PARSE_LIMIT = 10 * 1024 * 1024  # read and parsed for redaction
MAX_CHUNK = 64 * 1024 * 1024
MAX_DELAY = 3600
REDACTED = "<redacted>"


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
    if not isinstance(status, int) or isinstance(status, bool) or not 200 <= status <= 599:
        raise _BadScenario(f"{where}: status must be a number from 200 to 599")
    headers = r.get("headers", {})
    if not isinstance(headers, dict) or not all(
        isinstance(k, str) and isinstance(v, (str, int)) for k, v in headers.items()
    ):
        raise _BadScenario(f"{where}: headers must be an object of text values")
    delay = r.get("delay", 0)
    if (not isinstance(delay, (int, float)) or isinstance(delay, bool) or delay < 0
            or delay > MAX_DELAY or (isinstance(delay, float) and not math.isfinite(delay))):
        raise _BadScenario(f"{where}: delay must be 0 to {MAX_DELAY} seconds")
    truncate = r.get("truncate")
    if truncate is not None and (not isinstance(truncate, int) or isinstance(truncate, bool)
                                 or truncate < 0):
        raise _BadScenario(f"{where}: truncate must be a byte count")
    for flag in ("close", "reset"):
        if not isinstance(r.get(flag, False), bool):
            raise _BadScenario(f"{where}: {flag} must be true or false")


class _Withhold(Exception):
    """The body may hold a secret that structured redaction couldn't isolate."""


class _Unparsed(Exception):
    """The body isn't in the shape it claimed; fine to log only if it plainly has no secret."""


def _has_secret(text: str) -> bool:
    """A secret word in the text, or in what its %xx, \\u, \\x or &# escapes spell."""
    for _ in range(8):  # escapes can be nested (%2574 is %74 is t)
        if SECRET_WORD.search(text):
            return True
        decoded = html.unescape(unquote_plus(re.sub(
            r"\\(?:u([0-9a-fA-F]{4})|x([0-9a-fA-F]{2}))",
            lambda m: chr(int(m.group(1) or m.group(2), 16)), text)))
        if decoded == text:
            return False
        text = decoded
    return True  # still decoding after that many layers: treat as hiding something


def _redact_json(value: object) -> object:
    if isinstance(value, dict):
        return {k: REDACTED if _has_secret(str(k)) else _redact_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_json(v) for v in value]
    if isinstance(value, str) and _has_secret(value):
        raise _Withhold  # e.g. JSON escaped inside a string, or prose naming a password
    return value


def _redact_json_text(text: str) -> str:
    try:
        return json.dumps(_redact_json(json.loads(text)))
    except json.JSONDecodeError:
        lines = [line for line in text.splitlines() if line.strip()]
        try:  # newline-delimited JSON
            return "\n".join(json.dumps(_redact_json(json.loads(line))) for line in lines)
        except json.JSONDecodeError:
            raise _Unparsed from None


def _redact_pairs(text: str) -> str:
    """name=value pairs (forms, queries) with secret-named values replaced, raw text kept."""
    parts = []
    for item in text.split("&"):
        name, eq, value = item.partition("=")
        if eq and _has_secret(name):
            parts.append(f"{name}={REDACTED}")
        elif _has_secret(item):  # also an encoded = (%3D) hiding a name=value pair
            raise _Withhold
        else:
            parts.append(item)
    return "&".join(parts)


def _redact_multipart(raw: bytes, content_type: str) -> str:
    message = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
        f"Content-Type: {content_type}\r\n\r\n".encode() + raw
    )
    if not message.is_multipart():
        raise _Unparsed
    fields = []
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition") or ""
        value = part.get_payload(decode=True) or b""
        text = value.decode("utf-8", errors="replace")
        if _has_secret(name):
            text = REDACTED
        elif _has_secret(text):
            raise _Withhold
        fields.append(f"{name}={text}")
    return "\n".join(fields)


def _redact_body(raw: bytes, content_type: str, complete: bool) -> str:
    """The body for the log: parsed and redacted, or withheld if it can't be made safe."""
    text = raw.decode("utf-8", errors="replace")
    if not text.strip():
        return text
    withheld = f"<body withheld: {len(raw)} bytes; it may hold a secret>"
    try:
        if not complete:
            return withheld  # cut short, so no parser sees the whole thing
        kind = content_type.lower()
        if "multipart/" in kind:
            return _redact_multipart(raw, content_type)
        if "json" in kind or text.lstrip()[:1] in ("{", "["):
            return _redact_json_text(text)
        if "x-www-form-urlencoded" in kind or re.fullmatch(r"[^\s=&]+=[^\s]*", text.strip()):
            return _redact_pairs(text.strip())
        raise _Unparsed
    except _Withhold:
        # Redaction found a secret it couldn't isolate: never fall back to the raw text.
        return withheld
    except (_Unparsed, ValueError, TypeError, LookupError):
        if _has_secret(text):
            return withheld
        return text


def _redact_query(query: str) -> str:
    """Secret-named query values redacted, everything else exactly as the client sent it."""
    if not query:
        return ""
    try:
        return _redact_pairs(query)
    except _Withhold:
        return "<query withheld: it may hold a secret>"


def _handler(rules: list[dict], log: Path, seen: list) -> type[BaseHTTPRequestHandler]:
    calls: dict[int, int] = {}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass  # the JSON log is the record; stderr stays quiet

        def _read_body(self) -> tuple[bytes, int]:
            """The whole request body (chunked or sized), so the socket is left clean."""
            self._kept, self._total = bytearray(), 0

            def keep(chunk: bytes) -> None:
                self._total += len(chunk)
                self._kept += chunk[: max(0, PARSE_LIMIT - len(self._kept))]

            if "chunked" in self.headers.get("Transfer-Encoding", "").lower():
                while True:
                    line = self.rfile.readline()
                    if not line:
                        raise ConnectionError("client closed mid-body")
                    size_text = line.split(b";")[0].strip()
                    if not re.fullmatch(rb"[0-9a-fA-F]+", size_text):
                        raise ValueError("chunk size isn't hex")
                    size = int(size_text, 16)
                    if size > MAX_CHUNK:
                        raise ValueError("chunk too large")
                    if size == 0:
                        while self.rfile.readline().strip():
                            pass  # trailers
                        break
                    keep(self.rfile.read(size))
                    self.rfile.readline()
                return bytes(self._kept), self._total
            remaining = int(self.headers.get("Content-Length") or 0)
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 65536))
                if not chunk:
                    raise ConnectionError("client closed mid-body")
                remaining -= len(chunk)
                keep(chunk)
            return bytes(self._kept), self._total

        def _record(self, body: bytes, total: int, note: str = "") -> None:
            url = urlsplit(self.path)
            if note:
                logged = body.decode("utf-8", errors="replace")  # already screened
            else:
                logged = _redact_body(body, self.headers.get("Content-Type", ""),
                                      complete=total == len(body))
            entry = {
                "time": round(time.time(), 3), "method": self.command, "path": url.path,
                "query": _redact_query(url.query),
                "headers": {k: "<redacted>" if _has_secret(k) else v
                            for k, v in self.headers.items()},
                "body": logged[:MAX_BODY],
                "body_bytes": total,
            }
            if note:
                entry["note"] = note
            with lock, log.open("a", encoding="utf-8") as out:
                out.write(json.dumps(entry) + "\n")

        def _respond(self) -> None:
            with lock:
                seen[1] += 1  # in flight: a slow scripted answer isn't idleness
            try:
                self._answer()
            finally:
                with lock:
                    seen[1] -= 1
                    seen[0] = time.monotonic()

        def _answer(self) -> None:
            try:
                body, total = self._read_body()
            except (ValueError, MemoryError, ConnectionError) as exc:
                # A broken or abandoned body is evidence: log what arrived. Answer only a
                # client still listening; writing to a closed socket prints a traceback.
                partial = bytes(getattr(self, "_kept", b""))
                if _has_secret(partial.decode("utf-8", errors="replace")):
                    partial = b""
                closed = isinstance(exc, ConnectionError)
                self._record(partial, getattr(self, "_total", 0),
                             note="client closed mid-body" if closed
                             else "malformed chunk size or Content-Length")
                self.close_connection = True
                if not closed:
                    self._send({"status": 400, "body": {"error": "malformed request body"}})
                return
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
            bodiless = status in (204, 304)
            if bodiless:
                data = b""  # these statuses carry no body; one would corrupt the next response
            headers = {} if bodiless else {
                "content-type": ("Content-Type", "application/json" if not isinstance(body, str)
                                 else "text/plain; charset=utf-8"),
                "content-length": ("Content-Length", str(len(data))),
            }
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


def _idle_seconds(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        value = math.nan
    if not (math.isfinite(value) and value >= 1):
        raise argparse.ArgumentTypeError("must be at least 1 second")
    return value


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--idle-exit", type=_idle_seconds, default=600,
                        help="exit after this many seconds without a request")
    args = parser.parse_args(argv)
    seen = [time.monotonic(), 0]  # last activity, requests in flight
    try:
        rules = _load(Path(args.scenario))
        # Loopback only: the stub must never be reachable from outside this machine.
        server = ThreadingHTTPServer(("127.0.0.1", args.port),
                                     _handler(rules, Path(args.log), seen))
    except _BadScenario as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: can't listen on 127.0.0.1:{args.port}: {exc.strerror}", file=sys.stderr)
        return 1
    print(f"listening on http://127.0.0.1:{server.server_address[1]}", flush=True)

    def watch() -> None:
        # A stub nobody stopped stops itself, so a forgotten one can't linger.
        while seen[1] or time.monotonic() - seen[0] < args.idle_exit:
            time.sleep(min(1.0, args.idle_exit / 4))
        server.shutdown()

    threading.Thread(target=watch, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(_main())
