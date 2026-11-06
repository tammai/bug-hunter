"""Forward hunters' requests to one dev or UAT target the owner allowed: logged in, budgeted."""

import argparse
import http.client
import json
import math
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from drafts import drafts_dir
from stub_server import _redact_body, _redact_query

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
WRITES = {"POST", "PUT", "PATCH", "DELETE"}
ACCOUNT_HEADER = "x-bug-hunter-account"
# Hop-by-hop headers belong to one connection; Host and Content-Length are set for the target.
NOT_FORWARDED = {"connection", "keep-alive", "proxy-connection", "proxy-authorization", "te",
                 "trailer", "transfer-encoding", "upgrade", "host", "content-length",
                 ACCOUNT_HEADER}
MAX_BODY = 50 * 1024 * 1024
HEADER_NAME = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
# Drafts write an account as "$<NAME>_AUTH", so its name must be a shell variable name.
ACCOUNT_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
# Frameworks that honour these turn a GET into a write.
METHOD_OVERRIDES = {"x-http-method-override", "x-http-method", "x-method-override"}


class BadTarget(Exception):
    pass


def _http_url(text: str) -> bool:
    try:
        url = urlsplit(text)
        port = url.port
    except ValueError:
        return False
    return url.scheme in ("http", "https") and bool(url.hostname) and port != 0 \
        and url.username is None and url.password is None


def _local_url(text: str) -> bool:
    try:
        url = urlsplit(text)
        return url.scheme in ("http", "https") and url.hostname in LOCAL_HOSTS \
            and url.port is not None
    except ValueError:
        return False


def _targets_file(repo: str) -> Path:
    """The owner's allow-list for this repo, next to its drafts folder and outside the repo."""
    return drafts_dir(repo).parent / "targets.json"


def load_target(repo: str, target: str) -> dict:
    """The target's url, writes flag and accounts; BadTarget unless the owner allowed it."""
    if "://" in target:
        # Only localhost may be typed: any other host must be named from the owner's list,
        # so a mistyped URL can never reach production.
        if not _local_url(target):
            raise BadTarget(f"{target} isn't a localhost URL with a port; "
                            "name a target from targets.json instead")
        return {"url": target.rstrip("/"), "writes": True, "accounts": {}}
    if not target:
        raise BadTarget("no target named")
    try:
        path = _targets_file(repo)
    except FileNotFoundError:
        raise BadTarget("git is not installed") from None
    except ValueError as exc:
        raise BadTarget(str(exc)) from None
    try:
        targets = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise BadTarget(f"no {path}: list your dev and UAT targets there") from None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BadTarget(f"can't read {path} as JSON: {exc}") from None
    if not isinstance(targets, dict) or target not in targets:
        raise BadTarget(f"{target} isn't listed in {path}")
    entry = targets[target]
    if not isinstance(entry, dict) or not isinstance(entry.get("url"), str) \
            or not _http_url(entry["url"]):
        raise BadTarget(f"{target}: url must be an http or https URL with no user:password@")
    writes = entry.get("writes", False)
    if not isinstance(writes, bool):
        raise BadTarget(f"{target}: writes must be true or false")
    accounts = entry.get("accounts", {})
    if not isinstance(accounts, dict) or not all(
        isinstance(name, str) and isinstance(headers, dict)
        and all(isinstance(k, str) and isinstance(v, str) for k, v in headers.items())
        for name, headers in accounts.items()
    ):
        raise BadTarget(f"{target}: accounts must map names to objects of text headers")
    for name, headers in accounts.items():
        if not ACCOUNT_NAME.fullmatch(name):
            raise BadTarget(f"{target}: account name {name!r} must be letters, digits and _, "
                            "starting with a letter")
        for header, value in headers.items():
            # Never echo the value: it is a login.
            if not HEADER_NAME.fullmatch(header):
                raise BadTarget(f"{target}: account {name} has a header name that isn't valid")
            try:
                value.encode("latin-1")
            except UnicodeEncodeError:
                raise BadTarget(f"{target}: account {name}'s {header} value has characters "
                                "HTTP headers can't carry") from None
            if any(c in value for c in "\r\n\0"):
                raise BadTarget(f"{target}: account {name}'s {header} value has a line break")
    return {"url": entry["url"].rstrip("/"), "writes": writes, "accounts": accounts}


def _leaves_base(path: str) -> bool:
    """Whether a request path could climb out of the target's base path once decoded."""
    decoded = unquote(path.split("?", 1)[0])
    return not path.startswith("/") or any(
        segment in (".", "..") for segment in decoded.replace("\\", "/").split("/")
    )


def _secrets(target: dict) -> list[str]:
    """Every account value, and the parts a response might echo on their own."""
    found = set()
    for headers in target["accounts"].values():
        for value in headers.values():
            found |= {value, value.partition(" ")[2]}
            found |= {cookie.partition("=")[2] for cookie in value.split(";")}
    # Short pieces would mask ordinary words.
    return sorted((v.strip() for v in found if len(v.strip()) >= 6), key=len, reverse=True)


def _masker(target: dict, proxy_url: str):
    """Hide account values and the target's address in what goes back to an agent."""
    base = urlsplit(target["url"])
    swaps = [(re.compile(re.escape(v).encode()), b"<redacted>") for v in _secrets(target)]
    swaps.append((re.compile(re.escape(f"{base.scheme}://{base.netloc}").encode(), re.I),
                  proxy_url.encode()))
    hosts = [base.netloc] + ([] if base.hostname in LOCAL_HOSTS else [base.hostname])
    swaps += [(re.compile(re.escape(h).encode(), re.I), b"<target>") for h in hosts]

    def mask(data: bytes) -> bytes:
        for pattern, replacement in swaps:
            data = pattern.sub(replacement, data)
        return data
    return mask


def _handler(target: dict, log: Path, budget: int, rate: float, seen: list, proxy_url: list):
    base = urlsplit(target["url"])
    https = base.scheme == "https"
    connection = http.client.HTTPSConnection if https else http.client.HTTPConnection
    accounts = {name.lower(): headers for name, headers in target["accounts"].items()}
    lock = threading.Lock()
    state = {"sent": 0, "next": 0.0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass  # the JSON log is the record; stderr stays quiet

        def handle(self) -> None:
            try:
                super().handle()
            except (BrokenPipeError, ConnectionResetError):
                pass  # the hunter hung up; nothing is left to tell it

        def _reply(self, status: int, error: str) -> None:
            data = json.dumps({"error": error}).encode()
            self.send_response_only(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def _record(self, account: str, status: int, body: bytes, note: str = "") -> None:
            url = urlsplit(self.path)
            entry = {
                "time": round(time.time(), 3), "method": self.command, "path": url.path,
                "query": _redact_query(url.query), "account": account, "status": status,
                "body": _redact_body(body, self.headers.get("Content-Type", ""), complete=True),
                "body_bytes": len(body),
            }
            if note:
                entry["note"] = note
            with lock, log.open("a", encoding="utf-8") as out:
                out.write(json.dumps(entry) + "\n")

        def _take_slot(self) -> bool:
            """Count this request against the budget and wait for its turn under the rate."""
            with lock:
                if state["sent"] >= budget:
                    return False
                state["sent"] += 1
                now = time.monotonic()
                slot = max(now, state["next"])
                state["next"] = slot + 1 / rate
            time.sleep(max(0.0, slot - now))
            return True

        def _respond(self) -> None:
            with lock:
                seen[1] += 1
            try:
                self._forward()
            finally:
                with lock:
                    seen[1] -= 1
                    seen[0] = time.monotonic()

        def _refuse(self, status: int, note: str, error: str, body: bytes = b"") -> None:
            self._record(self.headers.get(ACCOUNT_HEADER, "").strip(), status, body, note=note)
            self._reply(status, error)

        def _forward(self) -> None:
            if not self.path.isascii():
                self.close_connection = True
                return self._refuse(400, "path isn't ASCII",
                                    "percent-encode non-ASCII characters in the path")
            if _leaves_base(self.path):
                self.close_connection = True
                return self._reply(400, "only paths on the target, like /api/orders, are allowed")
            if "chunked" in self.headers.get("Transfer-Encoding", "").lower():
                self.close_connection = True
                return self._reply(411, "send a Content-Length body, not chunked")
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if not 0 <= length <= MAX_BODY:
                self.close_connection = True
                return self._reply(400, "bad Content-Length")
            body = self.rfile.read(length) if length else b""
            account = self.headers.get(ACCOUNT_HEADER, "").strip()
            if account and account.lower() not in accounts:
                self._record(account, 400, body, note="unknown account")
                return self._reply(400, f"no account named {account} for this target")
            if self.command in WRITES and not target["writes"]:
                self._record(account, 403, body, note="writes not allowed")
                return self._reply(403, "this target doesn't allow writes")
            overridden = METHOD_OVERRIDES & {k.lower() for k in self.headers} or any(
                k.lower() == "_method" for k, _ in parse_qsl(urlsplit(self.path).query))
            if overridden and not target["writes"]:
                self._record(account, 403, body, note="method override on a read-only target")
                return self._reply(403, "this target doesn't allow writes")
            if not self._take_slot():
                self._record(account, 429, body, note="request budget used up")
                return self._reply(429, "the run's request budget is used up")

            headers = {k: v for k, v in self.headers.items() if k.lower() not in NOT_FORWARDED}
            if account:
                chosen = accounts[account.lower()]
                headers = {k: v for k, v in headers.items()
                           if k.lower() not in {name.lower() for name in chosen}}
                headers.update(chosen)
            headers["Host"] = base.netloc
            # Uncompressed, so account values and the target's address can be masked.
            headers = {k: v for k, v in headers.items() if k.lower() != "accept-encoding"}
            headers["Accept-Encoding"] = "identity"
            if body or self.command in WRITES:
                headers["Content-Length"] = str(len(body))
            try:
                upstream = connection(base.hostname, base.port, timeout=60)
                upstream.request(self.command, base.path + self.path, body=body or None,
                                 headers=headers)
                response = upstream.getresponse()
                data = response.read(MAX_BODY + 1)[:MAX_BODY]
                upstream.close()
            except (OSError, http.client.HTTPException, ValueError) as exc:
                self._record(account, 502, body, note=f"target unreachable: {type(exc).__name__}")
                return self._reply(502, f"target unreachable: {type(exc).__name__}")
            self._record(account, response.status, body)
            mask = _masker(target, proxy_url[0])
            data = mask(data)
            # send_response_only: no Server or Date of the proxy's own beside the target's.
            self.send_response_only(response.status, response.reason)
            for name, value in response.getheaders():
                if name.lower() not in NOT_FORWARDED:
                    self.send_header(name, mask(value.encode("latin-1")).decode("latin-1"))
            if self.command == "HEAD":
                length = response.getheader("Content-Length")
                if length is not None:
                    self.send_header("Content-Length", length)
            else:
                self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _respond

    return Handler


def _positive(minimum: float, kind: type):
    def parse(text: str):
        try:
            value = kind(text)
        except ValueError:
            value = math.nan
        if not (math.isfinite(value) and value >= minimum):
            raise argparse.ArgumentTypeError(f"must be a number of at least {minimum}")
        return value
    return parse


def _main(argv: list[str] | None = None) -> int:
    # Windows Python before 3.15 writes in the ANSI code page; the commands read UTF-8.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors=stream.errors)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--target", required=True,
                        help="a name from targets.json, or http://localhost:<port>")
    parser.add_argument("--log", required=True)
    parser.add_argument("--max-requests", type=_positive(1, int), default=200)
    parser.add_argument("--rate", type=_positive(0.01, float), default=5.0,
                        help="requests a second, at most")
    parser.add_argument("--idle-exit", type=_positive(1, float), default=600,
                        help="exit after this many seconds without a request")
    parser.add_argument("--check", action="store_true",
                        help="only check the target is allowed and well formed, then exit")
    args = parser.parse_args(argv)
    try:
        target = load_target(args.repo, args.target)
    except BadTarget as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.check:
        accounts = ", ".join(target["accounts"]) or "none"
        print(f"target ok: {args.target} (writes: {'yes' if target['writes'] else 'no'}; "
              f"accounts: {accounts})")
        return 0
    seen = [time.monotonic(), 0]  # last activity, requests in flight
    proxy_url: list[str] = [""]
    handler = _handler(target, Path(args.log), args.max_requests, args.rate, seen, proxy_url)
    try:
        # Loopback only: the hunters on this machine are the only clients.
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    except OSError as exc:
        print(f"error: can't listen on 127.0.0.1: {exc.strerror}", file=sys.stderr)
        return 1
    proxy_url[0] = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"listening on {proxy_url[0]}", flush=True)

    def watch() -> None:
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
