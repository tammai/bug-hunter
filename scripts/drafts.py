"""Where a repo's drafts live, the next draft number, and the fixed draft format check."""

import argparse
import html
import ipaddress
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

JSON_LETTERS = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r",
                "t": "\t"}
# Either case of `u` and `x`: an escape upper-cased after escaping (`\U002F`, `\X2F`) still decodes.
JSON_ESCAPE = re.compile(r'\\([uU][0-9a-fA-F]{4}|["\\/bfnrt])')
HEX_ESCAPE = re.compile(r"\\[xX]([0-9a-fA-F]{2})")
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")  # terminal colour and cursor codes
MAX_DECODE_ROUNDS = 8
MAX_SPELLINGS = 256

SECTIONS = ["What happens", "Steps to reproduce", "Expected", "Root cause"]
DRAFT_NAME = re.compile(r"^(\d+)\.md$")
# Userinfo runs to the last @ before the path: a password may hold an un-escaped @.
URL_ORIGIN = re.compile(r"^[a-z][a-z0-9+.-]*://(?:[^/]*@)?([^/:@]+)(?::\d+)?/(.+)$", re.I)
SCP_ORIGIN = re.compile(r"^(?:[^@/]*@)?([^/:]+):(?!/)(.+)$")


# Never the URL itself: it can carry a user name and token.
NO_FOLDER = ("origin URL can't name a drafts folder: a path part is empty, '.' or '..', or "
             "it holds an @ that can't be placed")


def _origin_parts(url: str) -> list[str] | None:
    match = URL_ORIGIN.match(url) or SCP_ORIGIN.match(url)
    if not match:
        return None
    # Any @ left after the user info the pattern took may be more of it (a password or token
    # holding `@`, `/`, `?` or `#`), and a real path's @ can't be told apart: refused before
    # anything is cut, since the folder name is printed.
    if "@" in match[1] + match[2]:
        raise ValueError(NO_FOLDER)
    path = match[2]
    if url.lower().startswith(("http://", "https://")):
        # A query or fragment can carry a token and never names the repo; in SCP and ssh
        # paths `?` and `#` are ordinary file-name characters.
        path = re.split(r"[?#]", path, maxsplit=1)[0]
    path = path.rstrip("/").removesuffix(".git")
    return [match[1], *path.split("/")]


def drafts_dir(repo: str) -> Path:
    """The repo's drafts folder, outside the repo so hunting leaves nothing in it."""
    result = subprocess.run(
        ["git", "-C", repo, "remote", "get-url", "origin"],
        capture_output=True, text=True, encoding="utf-8",
    )
    parts = _origin_parts(result.stdout.strip()) if result.returncode == 0 else None
    # A repo with no origin names its folder from its own name, @ and all.
    if parts is None:
        parts = ["local", Path(repo).resolve().name]
    # One folder level per URL part, so acme-web/api and acme/web-api never share a folder;
    # a "." or ".." part would climb out of ~/.bug-hunter.
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError(NO_FOLDER)
    return Path.home().joinpath(".bug-hunter", *parts, "drafts")


def numbered(directory: Path) -> list[tuple[int, Path]]:
    """The `NN.md` drafts in a folder, in numeric order; other files are ignored."""
    if not directory.is_dir():
        return []
    found = [(int(m[1]), p) for p in directory.iterdir() if (m := DRAFT_NAME.match(p.name))]
    return sorted(found)


def title(path: Path) -> str | None:
    """A draft's `# ` title, or None when it has none."""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            return (line[2:].strip() or None) if line.startswith("# ") else None
    return None


FENCE = re.compile(r" {0,3}(`{3,}|~{3,})(.*)")


def fenced(lines: list[str]):
    """Each line with whether it is part of a code block (its fence lines included)."""
    # CommonMark's rules: a Python traceback's indented `~~~~^^^^` caret line is plain text.
    opener = None
    for line in lines:
        match = FENCE.match(line)
        if opener is None:
            if match and not (match[1][0] == "`" and "`" in match[2]):
                opener = match[1]
            yield line, opener is not None
        else:
            if (match and match[1][0] == opener[0] and len(match[1]) >= len(opener)
                    and not match[2].strip()):
                opener = None
            yield line, True


def problems(text: str) -> list[str]:
    """Every way a draft breaks the fixed format; empty when it's good."""
    lines = text.splitlines()
    found = []
    first = next((line for line in lines if line.strip()), "")
    if not first.startswith("# "):
        found.append("missing a '# ' title line")
    elif not first[2:].strip():
        found.append("empty title after '# '")

    bodies: dict[str, list[str]] = {}
    current = None
    for line, in_fence in fenced(lines):
        if line.startswith("## ") and not in_fence:
            current = line[3:].strip().rstrip(":").casefold()
            bodies.setdefault(current, [])
        elif current is not None:
            bodies[current].append(line)

    order = [s for s in bodies if s in {r.casefold() for r in SECTIONS}]
    for section in SECTIONS:
        key = section.casefold()
        if key not in bodies:
            found.append(f"missing section: ## {section}")
        elif not any(line.strip() for line in bodies[key]):
            found.append(f"empty section: ## {section}")
    if order != [s.casefold() for s in SECTIONS if s.casefold() in bodies]:
        found.append("sections out of order: want " + " · ".join(SECTIONS))

    steps = bodies.get("steps to reproduce", [])
    if steps and not any(in_fence for _, in_fence in fenced(steps)):
        found.append("## Steps to reproduce has no code block with the actual output")
    # A browser draft writes its test with a heredoc the verifier's shell runs: a second end
    # line inside the test would end it early and run the rest as commands.
    if any("<<'BH_TEST_END'" in line for line in steps) and \
            sum(line.strip() == "BH_TEST_END" for line in steps) != 1:
        found.append("## Steps to reproduce: the test's heredoc needs exactly one BH_TEST_END "
                     "line, its last")
    return found


def _home_problems(text: str) -> list[str]:
    """The owner's home folder in a draft: it names their account in a public issue."""
    home = Path.home().as_posix().rstrip("/").lower()
    forms = {home, home.replace("/", "\\"), home.replace("/", "\\\\")}
    if home[1:2] == ":":
        forms.add("/" + home[0] + home[2:])  # Git Bash: C:/Users/x -> /c/Users/x
    lowered = text.lower()
    if len(home) > 3 and any(form in lowered for form in forms):
        return ["contains your home folder's path, which names your account"]
    return []


def _live_problems(text: str, target: dict, variable: str = "BASE",
                   replay: bool = False) -> list[str]:
    """Ways a live draft would leak the target's host or a login into a public issue."""
    found = leaks(text, target, variable, replay)
    setup = next((line for line in text.splitlines()
                  if line.strip().lower().startswith("set before running:")), None)
    if setup is None or not re.search(rf"\b{variable}\b", setup):
        found.append(f"missing a 'Set before running:' line naming {variable}")
    return found


def leaks(text: str, target: dict, variable: str = "BASE", replay: bool = False) -> list[str]:
    """The target's host, the proxy's account header or a login in `text`, never echoed."""
    # An HTTP-replay draft (a reference run) logs in through ACCEPT_ACCOUNT_<NAME>, not curl.
    def login(name: str) -> str:
        return f"ACCEPT_ACCOUNT_{name}" if replay else f'-H "${name}_AUTH"'
    from live_proxy import LOCAL_HOSTS  # live_proxy imports this module

    found = []
    # Every check runs on every decoded spelling, so no encoding layer hides a value.
    spellings = _spellings(text)
    patterns = _host_patterns(urlsplit(target["url"]), LOCAL_HOSTS)
    if any(re.search(p, t, re.I) for p in patterns for t in spellings):
        whose = "target's" if variable == "BASE" else "reference's"
        found.append(f"names the {whose} host: write \"${variable}\" instead")
    if any("x-bug-hunter-account" in t.lower() for t in spellings):
        found.append(f"writes the proxy's account header: write {login('<ACCOUNT>')} instead")
    for name, headers in target["accounts"].items():
        if any(_holds_login(t, name, headers, target["url"]) for t in spellings):
            found.append(f"holds a login value of account {name}: "
                         f"write {login(name.upper())} instead")
    return found


# A login piece shaped like a word ("member", "admin1"): prose is full of these, so one only
# counts next to what makes it a credential. Long letter runs are random tokens, not words.
WORDLIKE = re.compile(r"[A-Z]?[a-z]+\d{0,3}")  # lower or Capitalized: mixed case is random
WORDLIKE_MAX = 15
# Letter pairs that are rare in English words (under 1 in 10,000 pairs of /usr/share/dict/words):
# a lowercase run holding one (qwxzkvbnmt) is a random token, not a word, so it counts anywhere.
RARE_PAIRS = frozenset("""
aa aj aq bf bg bh bj bk bm bn bp bq bv bw bx bz cb cd cf cg cj cm cn cp cq cv cw cx cz db
dc dj dk dp dq dt dx dz fb fc fd fg fh fj fk fm fn fp fq fs fv fw fx fz gb gc gd gf gj gk
gp gq gt gv gw gx gz hb hc hd hg hh hj hk hp hq hs hv hx hz ii ij iw iy jb jc jd jf jg jh
ji jj jk jl jm jn jp jq jr js jt jv jw jx jy jz kb kc kd kf kg kj kk km kp kq kr kt kv kx
kz lh lj lq lr lx lz mc md mf mg mh mj mk mq mr mt mv mw mx mz nx oj pb pc pd pf pg pj pk
pm pq pv pw px pz qa qb qc qd qe qf qg qh qi qj qk ql qm qn qo qp qq qr qs qt qv qw qx qy
qz rj rq rx rz sd sg sj sr sv sx sz td tg tj tk tq tv tx tz uh uj uq uu uw uy uz vb vc vd
vf vg vh vj vk vl vm vn vp vq vr vs vt vv vw vx vy vz wb wc wd wf wg wj wk wm wp wq wt wu
wv ww wx wy wz xb xd xf xg xh xj xk xl xm xn xq xr xs xu xv xw xx xz yf yh yj yk yq yu yv
yx yy yz zb zc zd zf zg zh zj zk zl zm zn zp zq zr zs zt zu zv zw zx
""".split())
CREDENTIAL_FIELDS = r"password|passwd|pwd|pass|token|secret|api[_-]?key|key|auth"
# In prose ("the password is …") only names that mean a credential: "key is" and "auth is" are
# ordinary sentences.
PROSE_FIELDS = r"password|passwd|pwd|token|secret|api[_-]?key"
SESSION_LIKE = re.compile(r"sess|sid|auth|tok|jwt|csrf|xsrf|login|remember|key|secret|pass"
                          r"|cred|bearer|access|refresh|user|account|identity|id\s*$", re.I)
PROSE_TWO_WORDS = r"(?<![\w-])(?i:api|secret|access)\s++(?i:key|token)(?![\w-])"
# Where a name starts or ends inside an identifier: its edge, `_`/`-`, or a camelCase hump.
SEGMENT_START = r"(?:(?<![\w-])|(?<=[_-])|(?<=[a-z0-9])(?=[A-Z]))"
SEGMENT_END = r"(?=[_-]|(?<=[a-z0-9])[A-Z]|[^\w-]|\Z)"


def _holds_login(text: str, account: str, headers: dict, url: str) -> bool:
    """Whether `text` holds one of these login headers' values, or a part one could echo."""
    from live_proxy import _forms, _pieces  # live_proxy imports this module

    # Every form the proxy masks: as sent, JSON-escaped, percent-encoded, HTML entities and a
    # Basic login decoded; forms under 6 characters would match ordinary words.
    pieces = _pieces({"url": url, "accounts": {"_": headers}})
    # A word-shaped value of a cookie that isn't a session or auth cookie (device=desktop)
    # holds no secret on its own: it counts only as a credential, like a word login.
    cookies = [(c.partition("=")[0], c.partition("=")[2].strip())
               for h, v in headers.items() if h.lower() == "cookie" for c in v.split(";")
               if "=" in c]
    # Word-shaped: up to one rare pair (desktop's "kt"), where a random value has several.
    plain = {v for n, v in cookies if not SESSION_LIKE.search(n) and WORDLIKE.fullmatch(v)
             and len(v) <= WORDLIKE_MAX and _rare_pairs(v) <= 1}
    plain = {p for p in plain - _whole_values(headers) - {v for n, v in cookies
                                                          if SESSION_LIKE.search(n)}
             if len(p) >= 6}
    letters = {p for p in pieces - plain if WORDLIKE.fullmatch(p) and len(p) >= 6}
    words = {p for p in letters if len(p) <= WORDLIKE_MAX and _reads_as_word(p)} | plain
    # A random letters-only token counts anywhere and in any case, as a credential word does.
    # The placeholders this check tells drafts to write (MEMBER_AUTH) are not credentials.
    own = "|".join(re.escape(p) for p in (f"{account}_AUTH", f"ACCEPT_ACCOUNT_{account}"))
    lowered = re.sub(rf"(?i)(?<![\w-])(?:{own})(?![\w-])", " ", text).lower()
    if any(p.lower() in lowered for p in letters - words):
        return True
    if any(len(form) >= 6 and form in text for p in pieces - words for form in _forms(p)):
        return True
    if not words:
        return False
    # A word counts only as a credential: after this account's auth scheme, or after any field
    # or flag with one of these headers' or cookies' names or a credential word as a whole
    # segment of its name (access_token, --password, X-Auth-Token, <newPassword>), so prose
    # ("Author: a member", "Bypass: member") stays clean.
    names = {h for h in headers} | {c.partition("=")[0].strip()
                                     for v in headers.values() for c in v.split(";") if "=" in c}
    context = "|".join([*(re.escape(n) for n in names if n), CREDENTIAL_FIELDS])
    schemes = {v.split()[0] for v in headers.values() if len(v.split()) > 1}
    scheme = rf"(?i:{'|'.join(map(re.escape, schemes))})\s++" if schemes else None
    # One start per identifier and possessive runs: drafts and echoed responses are untrusted,
    # and a backtracking field match is cubic on a long run like "authauth…".
    # Then punctuation before the value (`: "`, `>`, `=`, `": ["`), or only spaces after a flag.
    def named(fields: str) -> str:
        return (rf"(?<![\w-])(?!(?i:{own})(?![\w-]))"
                rf"(?=[\w-]*?{SEGMENT_START}(?i:{fields}){SEGMENT_END})[\w-]++")
    name = named(context)
    prose = named("|".join([*(re.escape(n) for n in names if n), PROSE_FIELDS]))
    # After the punctuation, one `value` key or element may stand between (name="password"
    # value="…", "name":"token","value":"…", <password><value>…), then at most one `[` and
    # one quote, so an empty value ("") is never crossed; in prose, "is" or "was" (the
    # password is: …, the token value was **…**), then anything but a sentence or line end.
    # Up to three other quoted attributes or keys may stand beside that `value` (name="password"
    # type="text" value="…"); bounded, so a hostile run of them stays linear.
    punct = r"[^\w\s]\W*+"
    attr = (r"[\w-]++[\"']?\s*+[:=]\s*+(?:\"[^\"\n]{0,256}+\"|'[^'\n]{0,256}+')"
            r"[\s,]*+[\"']?")
    field = (rf"(?:{name}\s*+{punct}(?:(?:{attr}){{0,3}}(?i:value)[\"']?\s*+[:=>]"
             rf"\s*+(?:\[\s*+)?[\"']?)?|(?=-){name}\s++"
             rf"|(?:{prose}|{PROSE_TWO_WORDS})\s++(?:(?i:value)\s++)?(?i:is|was)(?![\w-])"
             rf"[^\w\n.!?;]*+)"
             rf"{f'(?:{scheme})?' if scheme else ''}")
    before = f"(?:{field}|\\b{scheme})" if scheme else field
    word = "|".join(map(re.escape, words))
    if re.search(rf"{before}(?i:{word})(?![\w-])", text):
        return True
    # The `value` key first: value="…" name="password", {"value":"…","name":"token"}.
    return re.search(rf"(?<![\w-])(?i:value)[\"']?\s*+[:=]\s*+[\"']?(?i:{word})(?![\w-])"
                     rf"[\"']?[\s,]*+[\"']?(?:{attr}){{0,3}}(?i:name)[\"']?\s*+[:=]\s*+[\"']?"
                     rf"{name}", text) is not None


def _whole_values(headers: dict) -> set[str]:
    """Each header's value and its credential after the scheme, and Basic logins decoded."""
    from live_proxy import _basic_passwords  # live_proxy imports this module

    found = {p.strip() for v in headers.values() for p in (v, v.strip().partition(" ")[2])}
    for _, decoded in _basic_passwords([("", headers)]):
        found |= {decoded.strip(), decoded.partition(":")[2].strip()}
    return found


CUT_AT = re.compile(r"[\s\"'`<>]")


def cut_whole(text: str, limit: int) -> str:
    """`text` cut to at most `limit` characters before a space, quote or angle bracket."""
    # Hosts, URLs and tokens hold none of those, so one is kept whole or dropped, never left
    # as a prefix; a run with none of them before the limit is dropped whole.
    if len(text) <= limit:
        return text
    return text[:max((m.start() for m in CUT_AT.finditer(text, 0, limit + 1)), default=0)]


def _reads_as_word(piece: str) -> bool:
    return _rare_pairs(piece) == 0


def _rare_pairs(piece: str) -> int:
    letters = piece.rstrip("0123456789").lower()
    return sum(letters[i:i + 2] in RARE_PAIRS for i in range(len(letters) - 1))


def _spellings(text: str) -> set[str]:
    """`text` and what it decodes to (JSON escapes, HTML entities, %xx), to any depth."""
    found = frontier = {text}
    # Each decoding is applied again to what it gave until nothing new comes out; bounded,
    # since every round can triple the set.
    for _ in range(MAX_DECODE_ROUNDS):
        frontier = {d for t in frontier
                    for d in (unquote(t), html.unescape(t), _json_unescaped(t),
                              HEX_ESCAPE.sub(lambda m: chr(int(m[1], 16)), t),
                              ANSI.sub("", t))} - found
        if not frontier or len(found) > MAX_SPELLINGS:
            break
        found = found | frontier
    return found


def _json_unescaped(text: str) -> str:
    # One left-to-right pass, as a JSON parser reads a string: `\\n` is a backslash then n.
    return JSON_ESCAPE.sub(lambda m: chr(int(m[1][1:], 16)) if m[1][0] in "uU"
                           else JSON_LETTERS[m[1]], text)


DEFAULT_PORTS = {"http": 80, "ws": 80, "https": 443, "wss": 443}
# An IPv6 spelling ends where no longer address goes on: not before a letter, digit or `_`,
# nor before `:` and another group (2001:db8::1:5, std::vector); "2001:db8::1: timeout" counts.
# Right boundaries are ASCII and case-sensitive, so a letter of another script after a host
# (fd00::1失败), or one re.I folds into ASCII (K, ſ), never hides it.
WORD = "(?-i:[0-9A-Za-z_])"
V6_END = rf"(?!{WORD}|:(?:{WORD}|:))"
# Anything up to the bracket, bounded so a hostile run of "[::1%" stays linear.
ZONE = r"(?:%[^\]\s]{0,64}+)?"
# Where a host name ends with no port after it: not in a longer name or before a port.
HOST_END = r"(?!(?-i:[0-9A-Za-z_.-])|:[0-9])"
# An `@` written as an HTML reference (with or without `;`) or a JSON escape.
AT = r"(?:&(?:#0*64(?![0-9])|#x0*40(?![0-9a-f])|commat;)|\\u0040)"
# The addresses a loopback target is reached at besides "localhost": 0.0.0.0 reaches the same
# server.
LOOPBACK = tuple(map(ipaddress.ip_address, ("127.0.0.1", "0.0.0.0", "::1")))


def _host(url) -> str:
    # DNS reads uat.acme.test. as uat.acme.test.
    return (url.hostname or "").lower().rstrip(".")


def _address(host: str):
    try:  # a zone (fe80::1%25eth0) names an interface, not another address
        return ipaddress.ip_address(host.partition("%")[0])
    except ValueError:
        return None


def _octets(address) -> str:
    # Zero-padded octets too (10.0.0.01).
    return r"\.".join(f"0*{octet}" for octet in address.packed)


def _ip_spellings(address) -> list[tuple[str, str]]:
    """Every way to write an IP address, each with where it ends when no port follows: IPv4
    zero-padded and as an IPv4-mapped IPv6 address; IPv6 in any spelling, bracketed (with a
    zone) or not."""
    if address.version == 4:
        # A leading 0* starts only at a run's first zero, so a long run of zeros stays linear.
        # 0.0.0.0 and 127.0.0.1's short forms (127.1, 127.0.1) need a left boundary, or they
        # match inside 10.0.0.0.0 or 192.168.127.1.
        guard = "(?<![0-9.])" if address.packed == bytes(4) else "(?<!0)"
        found = [(guard + _octets(address), "(?![0-9])")]
        if str(address) == "127.0.0.1":
            found.append((r"(?<![0-9.])0*127(?:\.0*0)?\.0*1", "(?![0-9])"))
        return found + _ip_spellings(ipaddress.IPv6Address(f"::ffff:{address}"))
    tree = _ipv6_pattern(address)
    return [(rf"\[{tree}{ZONE}\]", ""), (tree, V6_END)]


def _loopback() -> str:
    """Every spelling of a loopback host: localhost and each loopback address's IP spellings."""
    spellings = [s for a in LOOPBACK for s, _ in _ip_spellings(a)]
    # The lookahead fails at once where no spelling can start.
    return rf"(?=[l0-9\[:])(?:localhost\.?|{'|'.join(spellings)})"


def _port(port: int) -> str:
    # A URL parser reads :05000 as 5000.
    return rf":0*+{port}(?![0-9])"


def _ip(address, port: int | None) -> list[str]:
    """Every spelling of an IP target alone, and each with `port` after it (2001:db8::1:443)."""
    return [s + end for s, end in _ip_spellings(address)] + \
        ([s + _port(port) for s, _ in _ip_spellings(address)] if port else [])


def _host_patterns(url, local_hosts: set[str]) -> list[str]:
    """Where `url`'s host names the target: one source for the leak scan and the masker."""
    # No left boundary anywhere: whatever stands before a host (an undecoded escape, `_`, a
    # letter of another script) must never hide it; over-refusing and over-masking are the
    # safe side. A right boundary only after a digit, so a longer port or address (the
    # proxy's own listener at 127.0.0.1:50003, 10.0.0.12) isn't the target.
    host, port = _host(url), url.port
    effective = port or DEFAULT_PORTS.get(url.scheme)
    # A URL's host position, with any user@. The scheme run is matched whole from its start
    # and its end checked, so a long run stays linear and scheme characters glued before it
    # (git+http://, ...http://, -http://, an undecoded \057) never hide the URL.
    def at(ends: str = "") -> str:
        return rf"(?<![a-z0-9+.-])[a-z0-9+.-]++{ends}://(?:[^\s/@]*@)?"
    scheme = at()
    if host in local_hosts:
        # Any loopback spelling with exactly the target's port, the scheme's default when the
        # URL names none; a bare "localhost" gives nothing away.
        alias = _loopback()
        if effective is None:
            return [rf"{scheme}{alias}{HOST_END}"]
        # A URL leaves out its own scheme's default port, whatever the target's scheme is.
        found = [rf"{alias}{_port(effective)}"]
        prefix = {80: at("(?:(?<=http)|(?<=ws))"),
                  443: at("(?:(?<=https)|(?<=wss))")}.get(effective)
        if prefix:
            found.append(rf"{prefix}{alias}{HOST_END}")
        return found
    address = _address(host)
    if address:
        found = _ip(address, effective)
        if address.version == 6 and address.ipv4_mapped:
            port = f":{url.port}" if url.port else ""
            found += _host_patterns(urlsplit(f"{url.scheme}://{address.ipv4_mapped}{port}"),
                                    local_hosts)
        return found
    if "." in host or ":" in host:  # a domain: anywhere, subdomains included
        tail = r"(?![0-9a-f])" if ":" in host else r"(?![0-9])" if host[-1].isdigit() else ""
        return [re.escape(host) + tail]
    # A plain name ("ref") only after a scheme (and any user@) or with its port: elsewhere
    # every draft's own words ($REF_BASE, "reference", a /ref or //ref path, an @ref
    # decorator, qa@ref.com) would match. Known limit: a protocol-relative //ref is missed.
    name = re.escape(host) + r"\.?"
    found = [rf"{scheme}{name}(?!(?-i:[0-9A-Za-z_-])|\.{WORD})"]
    if port:
        found.append(rf"{name}{_port(port)}")
    return found


def _link_pattern(url, local_hosts: set[str]) -> str:
    """A link to `url`'s origin: its scheme, any spelling of its host, then its port (or none
    for the scheme's default), never where the host name goes on (uat.acme.test.evil)."""
    host = _host(url)
    address = _address(host)
    if host in local_hosts:
        spelled = _loopback()
    elif address:
        spelled = f"(?:{'|'.join(s for s, _ in _ip_spellings(address))})"
    else:
        spelled = re.escape(host) + r"\.?"
    default = DEFAULT_PORTS.get(url.scheme)
    port = url.port if url.port != default else None
    if port:
        tail = _port(port)
    else:
        tail = (rf"(?:{_port(default)})?" if default else "") + HOST_END
    # Not before a non-ASCII character (http://localhost失), case-sensitively so re.I can't
    # fold K or ſ into ASCII: that is no link the listener serves, so the host is masked
    # instead. Not where userinfo follows, plain, as an entity or a JSON escape: in
    # http://uat.acme.test;@evil.test/ the host is evil.test. Other entities (&amp;) are
    # stepped over whole; the look stops only where a URL's authority ends (space, /, ?, #,
    # a double quote, <, >, a backtick, a backslash), so a later address in the text
    # (admin@acme.test) doesn't count; possessive, so linear.
    return (rf"(?<![a-z0-9+.-]){re.escape(url.scheme)}://{spelled}{tail}"
            r"(?!(?-i:[^\x00-\x7f]))"
            rf"(?!(?:[^\s/?#@\"<>`\\&]|(?!{AT})&#?[0-9a-z]*+;?)*+(?:@|{AT}))")


def _ipv6_pattern(address: ipaddress.IPv6Address) -> str:
    """Every way to write `address`: groups zero-padded or not, any run of zeros as `::`, and
    the last 32 bits as a dotted IPv4 tail."""
    groups = [int(address) >> (112 - 16 * i) & 0xFFFF for i in range(8)]

    def group(value: int) -> str:
        return "0{1,4}" if value == 0 else f"0{{0,{4 - len(f'{value:x}')}}}{value:x}"

    def atoms(part: list[int]) -> list[str]:
        return [a for i, v in enumerate(part) for a in ([":"] if i else []) + [group(v)]]

    def compressed(part: list[int]) -> list[list[str]]:
        found = [atoms(part)]
        for start in range(len(part)):
            for end in range(start + 1, len(part) + 1):
                if not any(part[start:end]):
                    found.append(atoms(part[:start]) + ["::"] + atoms(part[end:]))
        return found

    quad = r"\.".join(f"0*{octet}" for octet in address.packed[12:])
    spellings = compressed(groups) + [head + ([] if head[-1] == "::" else [":"]) + [quad]
                                      for head in compressed(groups[:6])]
    # The spellings share their prefixes in one tree, so a hostile run of zeros and colons
    # walks one branch per position instead of trying each of about 100 spellings.
    tree: dict = {}
    for spelling in spellings:
        node = tree
        for atom in spelling:
            node = node.setdefault(atom, {})
        node[""] = {}

    def render(node: dict) -> str:
        branches = [atom + render(child) for atom, child in node.items() if atom]
        if "" in node:
            branches.append("")
        return branches[0] if len(branches) == 1 else "(?:" + "|".join(branches) + ")"

    # Every spelling starts with a zero, a `::` or the first group's first digit.
    return f"(?=[0:{groups[0]:x}])" + render(tree)


def expected_body(text: str) -> str:
    """The text of a draft's `## Expected` section."""
    expected, current = [], None
    for line, in_fence in fenced(text.splitlines()):
        if line.startswith("## ") and not in_fence:
            current = line[3:].strip().rstrip(":").casefold()
        elif current == "expected":
            expected.append(line)
    return "\n".join(expected)


def oracle_problems(text: str, spec: Path) -> list[str]:
    """Ways a draft's Expected fails to rest on the spec: an unknown criterion or rule, or none."""
    from oracle import (  # oracle imports scope
        CRITERION,
        domain_headings,
        is_spec_gap,
        load_lock,
        rule_citations,
    )

    known = {c["id"] for c in load_lock(spec)}
    body = expected_body(text)
    found = []
    ids = CRITERION.findall(body)
    if set(ids) - known:
        found.append("Expected cites a criterion that isn't in criteria.lock.json: "
                     + ", ".join(sorted(set(ids) - known)))
    rules, unknown = rule_citations(body, domain_headings(spec))
    if unknown:
        found.append("Expected cites a domain.md § that isn't a section of domain.md")
    if not is_spec_gap(text) and not (set(ids) & known or rules):
        found.append("Expected cites no criterion or domain.md rule (if none covers it, put "
                     "'Oracle: spec-gap' under the title)")
    return found


def _main(argv: list[str] | None = None) -> int:
    # Windows Python before 3.15 writes in the ANSI code page; the commands read UTF-8.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors=stream.errors)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("dir", help="print the repo's drafts folder").add_argument("repo")
    sub.add_parser("next", help="print the next free draft number").add_argument("dir")
    check = sub.add_parser("check", help="check a draft's format")
    check.add_argument("file")
    check.add_argument("--repo", help="with --target: the repo whose targets.json to read")
    check.add_argument("--target", help="a live draft: hide this target's host and logins")
    check.add_argument("--reference", help="also hide this reference's host and logins")
    check.add_argument("--oracle", type=Path, help="the spec folder Expected must cite")
    args = parser.parse_args(argv)
    if getattr(args, "reference", None) and not args.target:
        print("error: --reference needs --target", file=sys.stderr)
        return 1

    if args.command == "dir":
        try:
            print(drafts_dir(args.repo))
        except FileNotFoundError:
            print("error: git is not installed", file=sys.stderr)
            return 1
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        return 0
    if args.command == "next":
        drafts = numbered(Path(args.dir))
        print(f"{(drafts[-1][0] if drafts else 0) + 1:02d}")
        return 0
    try:
        text = Path(args.file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: cannot read {args.file}: {exc}", file=sys.stderr)
        return 1
    found = problems(text) + _home_problems(text)
    if args.oracle:
        from oracle import BadOracle

        try:
            found += oracle_problems(text, args.oracle)
        except BadOracle as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    if args.target:
        from live_proxy import BadTarget, load_target  # live_proxy imports this module

        try:
            replay = bool(args.reference)
            found += _live_problems(text, load_target(args.repo or ".", args.target),
                                    replay=replay)
            if args.reference:
                found += _live_problems(text, load_target(args.repo or ".", args.reference),
                                        "REF_BASE", replay)
        except BadTarget as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    for problem in dict.fromkeys(found):
        print(problem)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(_main())
