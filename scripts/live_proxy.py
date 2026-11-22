"""Forward hunters' requests to one dev or UAT target the owner allowed: logged in, budgeted."""

import argparse
import base64
import binascii
import html
import http.client
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, quote, quote_plus, unquote, urlsplit

from drafts import drafts_dir
from stub_server import _redact_body, _redact_query

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
WRITES = {"POST", "PUT", "PATCH", "DELETE"}
ACCOUNT_HEADER = "x-bug-hunter-account"
# Marks the proxy's own refusals, so a replay can tell "not run" from the target's own error.
REFUSED_HEADER = "X-Bug-Hunter-Refused"
REFUSALS = "/.bug-hunter/refusals"  # the proxy's own path: how many requests it refused
# Hop-by-hop headers belong to one connection; Host and Content-Length are set for the target.
NOT_FORWARDED = {"connection", "keep-alive", "proxy-connection", "proxy-authorization", "te",
                 "trailer", "transfer-encoding", "upgrade", "host", "content-length",
                 ACCOUNT_HEADER, REFUSED_HEADER.lower()}
# Beside another target, only these cross (and the browser's own `Sec-` families below): a
# front end may route by any other header, and no list of routing headers is ever complete.
BESIDE_ANOTHER = {"accept", "accept-encoding", "accept-language", "authorization",
                  "cache-control", "content-type", "cookie", "dnt", "if-match",
                  "if-modified-since", "if-none-match", "if-range", "if-unmodified-since",
                  "origin", "pragma", "priority", "range", "referer", "upgrade-insecure-requests",
                  "sec-gpc", "user-agent", "x-csrf-token", "x-requested-with", "x-xsrf-token"}
BROWSER_FAMILIES = ("sec-fetch-", "sec-ch-", "sec-websocket-")
MAX_DECODES = 10
# A segment whose name, up to `;`, `?` or `#`, is only dots and whitespace.
DOT_SEGMENT = re.compile(r"(?:^|[/\\])\.[.\s]*(?:[;?#/\\]|$)")
UNICODE_ESCAPE = re.compile(r"%u[0-9a-f]{4}", re.I)  # IIS-style `%u002e`
MAX_BODY = 50 * 1024 * 1024
HEADER_NAME = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
# Drafts write an account as "$<NAME>_AUTH", so its name must be a shell variable name.
ACCOUNT_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
# Frameworks that honour these turn a GET into a write.
METHOD_OVERRIDES = {"x-http-method-override", "x-http-method", "x-method-override"}
# A hunter probing auth sends 401s on purpose; each must not mint a token.
REFRESH_GAP = 30.0
REFRESH_TIMEOUT = 60


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
        return {"url": target.rstrip("/"), "writes": True, "accounts": {}, "refresh": None}
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
    _check_accounts(target, accounts)
    refresh = entry.get("refresh")
    if "refresh" in entry and not (isinstance(refresh, list) and refresh
                                   and all(isinstance(arg, str) and arg for arg in refresh)):
        raise BadTarget(f"{target}: refresh must be a command as a list of text arguments, "
                        'like ["python3", "mint.py"]')
    return {"url": entry["url"].rstrip("/"), "writes": writes, "accounts": accounts,
            "refresh": refresh and {"argv": refresh, "dir": str(path.parent), "name": target,
                                    "repo": str(Path(repo).absolute())}}


class _InRepo(Exception):
    pass


def _check_accounts(target: str, accounts: object, minted: bool = False) -> None:
    """BadTarget unless `accounts` maps shell-safe names to objects of sendable headers."""
    if not isinstance(accounts, dict) or not all(
        isinstance(name, str) and isinstance(headers, dict)
        and all(isinstance(k, str) and isinstance(v, str) for k, v in headers.items())
        for name, headers in accounts.items()
    ):
        raise BadTarget(f"{target}: accounts must map names to objects of text headers")
    for i, (name, headers) in enumerate(accounts.items(), 1):
        # A command's output may hold a token in any field, so its items are named by position.
        account = f"account {i}" if minted else f"account {name}"
        if not ACCOUNT_NAME.fullmatch(name):
            raise BadTarget(f"{target}: " + (f"{account}'s name" if minted else
                                             f"account name {name!r}")
                            + " must be letters, digits and _, starting with a letter")
        for j, (header, value) in enumerate(headers.items(), 1):
            # Never echo the value: it is a login.
            if not HEADER_NAME.fullmatch(header):
                raise BadTarget(f"{target}: {account} has a header name that isn't valid")
            header = f"header {j}" if minted else header
            try:
                value.encode("latin-1")
            except UnicodeEncodeError:
                raise BadTarget(f"{target}: {account}'s {header} value has characters "
                                "HTTP headers can't carry") from None
            if any(c in value for c in "\r\n\0"):
                raise BadTarget(f"{target}: {account}'s {header} value has a line break")


def _program(name: str, folder: str, repo: str) -> str:
    """The refresh program's path: relative to targets.json's folder, else from PATH only."""
    if os.path.isabs(name):
        return name
    if "/" in name or os.sep in name:
        return str(Path(folder) / name)
    # Windows' lookup tries the current folder first unless this is set, and /hunt runs from
    # the hunted repo: a python3.exe it commits would run with the owner's logins.
    os.environ["NoDefaultCurrentDirectoryInExePath"] = "1"
    found = shutil.which(name)
    if found is None:
        raise FileNotFoundError(name)
    # PATH can lead into the repo too (an activated virtualenv); check the path as found and
    # with links resolved, against the repo and the folder the proxy runs in.
    places = {Path(found).absolute(), Path(found).resolve()}
    if any(p.is_relative_to(root) for p in places for root in {
            Path(repo), Path(repo).resolve()}) or Path(found).absolute().parent == Path.cwd():
        raise _InRepo(name)
    return found


def _kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe")
        try:
            subprocess.run([str(taskkill), "/T", "/F", "/PID", str(proc.pid)],
                           capture_output=True)
        except OSError:
            pass  # the direct child is still killed below
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    proc.kill()
    proc.wait()


def mint(target: dict) -> dict:
    """The accounts the target's refresh command prints; BadTarget, never its output, if not."""
    refresh = target["refresh"]
    what = f"{refresh['name']}: refresh command"
    # An argument list and no shell. Output goes to a file, not a pipe, so a child the command
    # leaves running can't hold the read open past the timeout; none of it is ever echoed.
    group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" \
        else {"start_new_session": True}
    try:
        with tempfile.TemporaryFile() as out:
            try:
                proc = subprocess.Popen(
                    [_program(refresh["argv"][0], refresh["dir"], refresh["repo"]),
                     *refresh["argv"][1:]], cwd=refresh["dir"], stdin=subprocess.DEVNULL,
                    stdout=out, stderr=subprocess.DEVNULL, **group)
            except _InRepo:
                raise BadTarget(f"{what}'s program was found inside the hunted repo or the "
                                "current folder; give its full path") from None
            except (OSError, ValueError) as exc:
                raise BadTarget(f"{what} can't start ({type(exc).__name__})") from None
            try:
                code = proc.wait(timeout=REFRESH_TIMEOUT)
            except subprocess.TimeoutExpired:
                _kill_tree(proc)
                raise BadTarget(f"{what} took longer than {REFRESH_TIMEOUT} s") from None
            out.seek(0)
            printed = out.read()
    except OSError as exc:
        raise BadTarget(f"{what} can't run ({type(exc).__name__})") from None
    if code != 0:
        raise BadTarget(f"{what} exited with {code}")
    try:
        accounts = json.loads(printed)
    except (ValueError, RecursionError):
        raise BadTarget(f"{what} didn't print a JSON object of accounts") from None
    _check_accounts(f"{what} printed bad accounts", accounts, minted=True)
    return accounts


def _apply(target: dict, minted: dict) -> None:
    """Put minted accounts over the current ones; every value they replace stays masked."""
    names = {name.lower() for name in minted}
    history = target.setdefault("history", [])
    for name, headers in target["accounts"].items():
        if name.lower() in names and headers not in history:
            history.append(headers)
    # Names match case-insensitively, as requests name them; an account a mint leaves out
    # keeps its last value and can still trigger the next mint.
    kept = {n: h for n, h in target["accounts"].items() if n.lower() not in names}
    target["accounts"] = {**kept, **minted}
    target["minted"] = target.get("minted", set()) | names
    target["minted_at"] = time.monotonic()
    target["mint_failed"] = False


def _place(target: dict) -> tuple:
    """The origin two targets must not share: scheme, host (loopback names as one) and port."""
    # Base paths don't count: two apps on one origin share an address key in the masking.
    url = urlsplit(target["url"])
    port = url.port or (443 if url.scheme == "https" else 80)
    host = (url.hostname or "").lower()
    return url.scheme, "loopback" if host in LOCAL_HOSTS else host, port


def _leaves_base(path: str) -> bool:
    """Whether a request path could climb out of the target's base path, however decoded."""
    # A target or front end may decode more than once (`%252e%252e` is `..`), end a segment's
    # name at `;`, `?` or `#` (`..;/`), or trim trailing dots and spaces (`.../`, `.. /`).
    if not path.startswith("/"):
        return True
    current = path.split("?", 1)[0]
    for _ in range(MAX_DECODES):
        if DOT_SEGMENT.search(current) or UNICODE_ESCAPE.search(current):
            return True
        decoded = unquote(current)
        if decoded == current:
            return False
        current = decoded
    return True  # still changing: encoded deeper than any real path


def _forms(value: str) -> set[str]:
    """The ways a response may echo a value: as is, JSON-escaped and percent-encoded."""
    escaped = json.dumps(value)[1:-1]
    encoded = {quote(value, safe=""), quote(value), quote_plus(value)}
    # Percent-encoding's hex may come back in either case; the value itself may not.
    encoded |= {re.sub(r"%[0-9A-F]{2}", lambda m: m.group().lower(), e) for e in encoded}
    # HTML templates escape &, <, >, quotes, and Go's also + and =, as named or numeric entities.
    entities = {html.escape(value)}
    for style in ("&#{:d};", "&#x{:X};", "&#x{:x};"):
        for chars in ("+=", "+=/"):
            entities.add("".join(style.format(ord(c)) if c in chars else c for c in value))
    return {value, escaped, escaped.replace("/", "\\/"), value.replace("/", "\\/")} \
        | encoded | entities


def _every_login(target: dict) -> list[dict]:
    """The headers of each account now and every value one replaced: all of them masked."""
    return [*target["accounts"].values(), *target.get("history", [])]


def _basic_passwords(logins: list[tuple[str, dict]]) -> list[tuple[str, str]]:
    """(account, decoded user:password) for each Basic login, as UTF-8 and as Latin-1."""
    found = []
    for name, headers in logins:
        for value in headers.values():
            scheme, _, credential = value.strip().partition(" ")
            if scheme.lower() != "basic":
                continue
            try:
                raw = base64.b64decode(credential.strip(), validate=True)
            except (binascii.Error, ValueError):
                continue
            for codec in ("utf-8", "latin-1"):
                try:
                    found.append((name, raw.decode(codec)))
                except UnicodeDecodeError:
                    continue  # not this encoding; a lossy decode would be a wrong pattern
    return found


def _pieces(target: dict) -> set[str]:
    """Every account value, and the parts a response might echo alone, stripped."""
    pieces = set()
    for headers in _every_login(target):
        for value in headers.values():
            pieces |= {value, value.strip().partition(" ")[2]}
            pieces |= {cookie.partition("=")[2] for cookie in value.split(";")}
    for _, decoded in _basic_passwords([("", h) for h in _every_login(target)]):
        pieces |= {decoded, decoded.partition(":")[2]}
    return {p.strip() for p in pieces}


def _secrets(target: dict) -> list[str]:
    """Every form of every account value, and of the parts a response might echo alone."""
    pieces = _pieces(target)
    found = set().union(*(_forms(p) for p in pieces)) if pieces else set()
    # Short pieces would mask ordinary words.
    return sorted((v for v in found if len(v) >= 6), key=len, reverse=True)


def _password_warnings(target: dict) -> list[str]:
    """What the owner should know about Basic passwords the masking handles poorly."""
    warnings = set()
    for name, decoded in _basic_passwords(list(target["accounts"].items())):
        password = decoded.partition(":")[2]
        if not password:
            continue  # a key sent as the user name, masked whole; nothing short to warn about
        if len(password) < 6:
            warnings.add(f"account {name}'s password is shorter than 6 characters, so the proxy "
                         "can't hide it if the target echoes it alone; use a longer one")
        elif re.fullmatch(r"[A-Za-z]+\d{0,3}", password):
            warnings.add(f"account {name}'s password is a plain word; responses that contain "
                         "it exactly will show <redacted> there")
    return sorted(warnings)


def _masker(target: dict, proxy_url: str, others: tuple = ()):
    """Hide account values and the addresses of this target and `others` (target, url)."""
    # One pass over all targets, longest first, so one target's patterns never cut another's.
    pairs = [(target, proxy_url), *others]
    secrets = sorted({s for t, _ in pairs for s in _secrets(t)}, key=len, reverse=True)
    # One pass per kind, built once per proxy; matched exactly, so "Password" in a form label
    # survives an account whose password is "password".
    # Each value as UTF-8 and, where it fits, as Latin-1 bytes: targets echo either.
    forms = {v.encode("utf-8") for v in secrets}
    for v in secrets:
        try:
            forms.add(v.encode("latin-1"))
        except UnicodeEncodeError:
            pass
    secret = re.compile(b"|".join(re.escape(f) for f in sorted(forms, key=len, reverse=True))
                        ) if forms else None
    # Each target's address goes to its own listener, so links an agent follows still work;
    # not where it continues as a longer host name (uat.acme.test.evil).
    urls: dict[bytes, bytes] = {}
    hosts: list[str] = []
    for chosen, url in pairs:
        base = urlsplit(chosen["url"])
        urls.setdefault(f"{base.scheme}://{base.netloc}".encode().lower(), url.encode())
        # A bare host is masked only where it stands alone, and a plain name ("uat") only with
        # its port: on its own it would mangle words like /actuator.
        if ":" in base.netloc or "." in base.netloc:
            hosts.append(base.netloc)
        if base.hostname not in LOCAL_HOSTS and ("." in base.hostname or ":" in base.hostname):
            hosts.append(base.hostname)
    address = re.compile(b"(?:" + b"|".join(re.escape(a) for a in sorted(
        urls, key=len, reverse=True)) + rb")(?![\w-]|\.\w)", re.I)
    # An IPv6 host must not match inside a longer address, so ":" before it also blocks it;
    # for other hosts ":" is ordinary punctuation ("Host:uat.acme.test").
    alternatives = [(rb"(?<![\w.:-])" if h.count(":") > 1 and not h.startswith("[")
                     else rb"(?<![\w.-])") + re.escape(h).encode() + rb"(?![\w-])"
                    for h in sorted(dict.fromkeys(hosts), key=len, reverse=True)]
    host = re.compile(b"|".join(alternatives), re.I) if hosts else None

    def mask(data: bytes) -> bytes:
        if secret:
            data = secret.sub(b"<redacted>", data)
        # bytes.lower() folds ASCII only, as re.I on bytes does, so every match has its key.
        data = address.sub(lambda m: urls[m.group().lower()], data)
        return host.sub(b"<target>", data) if host else data
    return mask


def _handler(target: dict, log: Path, budget: int, rate: float, seen: list, proxy_url: list,
             label: str | None = None, shared: dict | None = None, others: tuple = (),
             gap: float = REFRESH_GAP):
    """A handler for one listener; `others` are masked too, `shared` holds the joint budget."""
    base = urlsplit(target["url"])
    https = base.scheme == "https"
    connection = http.client.HTTPSConnection if https else http.client.HTTPConnection
    state = shared if shared is not None else {"lock": threading.Lock(), "sent": 0, "next": 0.0,
                                               "refused": 0}
    state.setdefault("logins", 0)  # bumped on every refresh, so each masker is rebuilt
    lock = state["lock"]
    refreshing = threading.Lock()
    def crosses(name: str) -> bool:
        name = name.lower()
        return name not in NOT_FORWARDED and (
            not others or name in BESIDE_ANOTHER or name.startswith(BROWSER_FAMILIES))

    masker: list = [None, -1]  # built on first use, once the proxies' own URLs are known

    def accounts() -> dict:
        with lock:
            return {name.lower(): headers for name, headers in target["accounts"].items()}

    def refresh(account: str, sent: dict) -> tuple[dict | None, str]:
        """New headers for `account` after its 401, or None and the note to log."""
        with refreshing:
            now = accounts().get(account.lower())
            if now is not None and now != sent:
                return now, ""  # another request's refresh already replaced them
            with lock:
                if account.lower() not in target.get("minted", set()):
                    return None, ""
                if time.monotonic() - target.get("minted_at", -math.inf) < gap:
                    return None, "token refresh failed" if target.get("mint_failed") else ""
                target["minted_at"] = time.monotonic()  # a failing command is throttled too
            try:
                minted = mint(target)
            except Exception:  # whatever went wrong, the hunter still gets the target's 401
                with lock:
                    target["mint_failed"] = True
                return None, "token refresh failed"
            with lock:
                _apply(target, minted)
                state["logins"] += 1
            now = accounts().get(account.lower())
            return (now, "") if now is not None and now != sent else (None, "")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass  # the JSON log is the record; stderr stays quiet

        def handle(self) -> None:
            try:
                super().handle()
            except (BrokenPipeError, ConnectionResetError):
                pass  # the hunter hung up; nothing is left to tell it

        def send_error(self, code: int, message: str | None = None,
                       explain: str | None = None) -> None:
            # http.server's own refusals (414, 431, 501) are the proxy's too, not the target's.
            self.close_connection = True
            entry = {"time": round(time.time(), 3), "method": self.command or "", "path": "",
                     "status": code, "note": "refused by http.server"}
            if label:
                entry["target"] = label
            with lock, log.open("a", encoding="utf-8") as out:
                out.write(json.dumps(entry) + "\n")
            self._reply(code, message or "the proxy refused this request")

        def _refusal_count(self) -> None:
            # The proxy's own answer, never forwarded or counted: browser.py reads it before
            # and after a test, so a refused request makes the run "not run", not a bug.
            with lock:
                data = json.dumps({"refused": state["refused"]}).encode()
            self.send_response_only(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Bug-Hunter-Proxy", "1")
            self.end_headers()
            self.wfile.write(data)

        def _reply(self, status: int, error: str) -> None:
            with lock:
                state["refused"] += 1
            data = json.dumps({"error": error}).encode()
            self.send_response_only(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header(REFUSED_HEADER, "1")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def _record(self, account: str, status: int, body: bytes, note: str = "",
                    forwarded: bool = False) -> None:
            url = urlsplit(self.path)
            entry = {
                "time": round(time.time(), 3), "method": self.command, "path": url.path,
                "query": _redact_query(url.query), "account": account, "status": status,
                "body": _redact_body(body, self.headers.get("Content-Type", ""), complete=True),
                "body_bytes": len(body),
            }
            held = sorted({k.lower() for k in self.headers if not crosses(k)} - NOT_FORWARDED)
            if forwarded and held:
                # Names only, for the run's Report: a header the app needed never arrived.
                note = "; ".join(filter(None, (note, "headers not forwarded beside the "
                                                     f"reference: {', '.join(held)}")))
            if note:
                entry["note"] = note
            if forwarded:
                entry["forwarded"] = True  # it took a budget slot; it may have reached the target
            if label:
                entry["target"] = label
            with lock, log.open("a", encoding="utf-8") as out:
                out.write(json.dumps(entry) + "\n")

        def _take_slot(self, counted: bool = True) -> bool:
            """Count this request against the budget and wait for its turn under the rate."""
            with lock:
                if counted and state["sent"] >= budget:
                    return False
                state["sent"] += counted
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
            if self.path == REFUSALS and self.command == "GET":
                return self._refusal_count()
            if not self.path.isascii():
                self.close_connection = True
                return self._refuse(400, "path isn't ASCII",
                                    "percent-encode non-ASCII characters in the path")
            if not self.path.startswith("/"):
                # A browser sends every request to its proxy in absolute form; only this
                # listener's own URL is served, so the browser can reach no other origin.
                try:
                    url = urlsplit(self.path)
                except ValueError:
                    url = None
                own = urlsplit(proxy_url[0])
                if url is None or (url.scheme, url.netloc.lower()) != (own.scheme, own.netloc):
                    self.close_connection = True
                    return self._refuse(400, "absolute URL to another origin",
                                        "only paths on the target, like /api/orders, are "
                                        "allowed")
                self.path = (url.path or "/") + (f"?{url.query}" if url.query else "")
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
            known = accounts()
            if account and account.lower() not in known:
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

            chosen = known[account.lower()] if account else {}
            try:
                response, data = self._send(body, chosen)
                note = ""
                if response.status == 401 and account and target["refresh"]:
                    fresh, note = refresh(account, chosen)
                    if fresh is not None:
                        self._take_slot(counted=False)  # the retry keeps to the rate
                        response, data = self._send(body, fresh)
                        note = "retried after token refresh"
            except (OSError, http.client.HTTPException, ValueError) as exc:
                self._record(account, 502, body, note=f"target unreachable: {type(exc).__name__}",
                             forwarded=True)
                return self._reply(502, f"target unreachable: {type(exc).__name__}")
            encoding = (response.getheader("Content-Encoding") or "identity").strip().lower()
            bodiless = self.command == "HEAD" or response.status in (204, 304)
            if encoding not in ("", "identity") and not bodiless:
                # Asked for identity; a compressed body can't be checked for logins. The
                # target's own value isn't echoed: it is text the agent shouldn't need.
                self._record(account, 502, body, note="target sent a compressed body",
                             forwarded=True)
                return self._reply(502, "the target sent a compressed body although asked "
                                        "not to, so it can't be checked for logins")
            self._record(account, response.status, body, note=note, forwarded=True)
            # Built under the lock that swaps accounts in, so it knows every value sent so far.
            with lock:
                if masker[1] != state["logins"]:
                    masker[:] = [_masker(target, proxy_url[0], tuple(
                        (other, url[0]) for other, url in others)), state["logins"]]
                mask = masker[0]
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

        def _send(self, body: bytes, chosen: dict) -> tuple:
            headers = {k: v for k, v in self.headers.items() if crosses(k)}
            if chosen:
                headers = {k: v for k, v in headers.items()
                           if k.lower() not in {name.lower() for name in chosen}}
                headers.update(chosen)
            headers["Host"] = base.netloc
            # Uncompressed, so account values and the target's address can be masked.
            headers = {k: v for k, v in headers.items() if k.lower() != "accept-encoding"}
            headers["Accept-Encoding"] = "identity"
            if body or self.command in WRITES:
                headers["Content-Length"] = str(len(body))
            upstream = connection(base.hostname, base.port, timeout=60)
            try:
                upstream.request(self.command, base.path + self.path, body=body or None,
                                 headers=headers)
                response = upstream.getresponse()
                return response, response.read(MAX_BODY + 1)[:MAX_BODY]
            finally:
                upstream.close()

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
    parser.add_argument("--reference",
                        help="a second target, the reference, served on its own listener")
    parser.add_argument("--refresh-gap", type=_positive(0, float), default=REFRESH_GAP,
                        help=argparse.SUPPRESS)
    parser.add_argument("--check", action="store_true",
                        help="only check the target is allowed and well formed, then exit")
    args = parser.parse_args(argv)
    try:
        target = load_target(args.repo, args.target)
        reference = load_target(args.repo, args.reference) if args.reference else None
    except BadTarget as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if reference and (args.reference == args.target or _place(reference) == _place(target)):
        print("error: --reference is on the same origin (scheme, host and port) as --target; "
              "the reference must be another server", file=sys.stderr)
        return 1
    try:
        for chosen in (target, reference):
            if chosen and chosen["refresh"]:
                _apply(chosen, mint(chosen))
    except BadTarget as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    listeners = [("target", args.target, target)]
    if reference:
        listeners.append(("reference", args.reference, reference))
    if args.check:
        for kind, name, chosen in listeners:
            accounts = ", ".join(chosen["accounts"]) or "none"
            print(f"{kind} ok: {name} (writes: {'yes' if chosen['writes'] else 'no'}; "
                  f"accounts: {accounts})")
        for _, _, chosen in listeners:
            for warning in _password_warnings(chosen):
                print(f"warning: {warning}")
        if reference:
            # Replays send one account name to both targets.
            names = [{n.lower() for n in t["accounts"]} for t in (target, reference)]
            for kind, mine, theirs in (("target", *names), ("reference", *names[::-1])):
                for name in sorted(mine - theirs):
                    print(f"warning: account {name} is on the {kind} only; its steps can't run "
                          "on both targets")
        return 0
    seen = [time.monotonic(), 0]  # last activity, requests in flight
    shared = {"lock": threading.Lock(), "sent": 0, "next": 0.0, "refused": 0}
    urls: list[list[str]] = [[""] for _ in listeners]
    servers = []
    for i, (kind, _, chosen) in enumerate(listeners):
        label = None if not reference else ("rebuild" if kind == "target" else "reference")
        others = tuple((o, urls[j]) for j, (_, _, o) in enumerate(listeners) if j != i)
        handler = _handler(chosen, Path(args.log), args.max_requests, args.rate, seen, urls[i],
                           label, shared, others, args.refresh_gap)
        try:
            # Loopback only: the hunters on this machine are the only clients.
            servers.append(ThreadingHTTPServer(("127.0.0.1", 0), handler))
        except OSError as exc:
            for server in servers:
                server.server_close()
            print(f"error: can't listen on 127.0.0.1: {exc.strerror}", file=sys.stderr)
            return 1
        urls[i][0] = f"http://127.0.0.1:{servers[-1].server_address[1]}"
    print(f"listening on {urls[0][0]}", flush=True)
    if reference:
        print(f"reference listening on {urls[1][0]}", flush=True)

    def watch() -> None:
        while seen[1] or time.monotonic() - seen[0] < args.idle_exit:
            time.sleep(min(1.0, args.idle_exit / 4))
        for server in servers:
            server.shutdown()

    for server in servers[1:]:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=watch, daemon=True).start()
    try:
        servers[0].serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # The reference listener's loop runs in a daemon thread and ends with the process;
        # closing its socket under that loop, or waiting on a loop not yet started, would not.
        servers[0].server_close()
    return 0


if __name__ == "__main__":
    sys.exit(_main())
