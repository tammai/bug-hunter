import time


def _mask(url: str):
    from live_proxy import _masker

    return _masker({"url": url, "accounts": {}}, "http://127.0.0.1:9")


def test_userinfo_behind_any_entity_or_escape_is_not_routed():
    mask = _mask("http://uat.acme.test")
    for tail in ("&x@evil.test/", "&amp;x@evil.test/", "&AMP;x@evil.test/",
                 "&#x26;x@evil.test/", "&#59;@evil.test/", "&lt;x@evil.test/",
                 "&#64evil.test/", "\\u0040evil.test/", "\\U0040evil.test/"):
        out = mask(f"http://uat.acme.test{tail}".encode())
        assert b"127.0.0.1:9" not in out and b"<target>" in out, (tail, out)


def test_ordinary_links_with_ampersands_still_route():
    mask = _mask("http://uat.acme.test")
    for tail in ("/x?a=1&b=2", "&b=2/", "#top", " a@b", "&#x40e/", "&#640/"):
        out = mask(f"http://uat.acme.test{tail}".encode())
        assert out.startswith(b"http://127.0.0.1:9"), (tail, out)


def test_a_link_before_a_letter_case_folding_turns_ascii_is_not_routed():
    for url, link in (("http://uat.acme.test", "http://uat.acme.test\u212a/x"),
                      ("http://devbox", "http://devbox\u017f/")):
        out = _mask(url)(link.encode())
        assert b"127.0.0.1:9" not in out, (link, out)


def test_userinfo_look_stays_linear_on_ampersand_runs():
    mask = _mask("http://uat.acme.test")
    for run in ("&" * 200_000, "&#" * 100_000, "&#6" * 66_000):
        data = ("http://uat.acme.test" + run).encode() * 2
        start = time.monotonic()
        mask(data)
        assert time.monotonic() - start < 2, run[:3]
