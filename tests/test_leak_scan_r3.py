def _bare(url: str) -> dict:
    return {"url": url, "accounts": {}}


def _found_and_masked(url: str, text: str) -> None:
    from drafts import leaks
    from live_proxy import _masker

    assert leaks(text, _bare(url)), (url, text)
    out = _masker(_bare(url), "http://127.0.0.1:9")(text.encode()).decode("utf-8")
    assert leaks(out, _bare(url)) == [], (url, text, out)


def test_loopback_reaches_every_ip_spelling_with_its_port():
    from drafts import leaks

    for url, text in (("http://127.0.0.1:5000", "connect ECONNREFUSED ::ffff:7f00:1:5000"),
                      ("http://localhost:5000", "connect ECONNREFUSED ::ffff:7f00:1:5000"),
                      ("http://localhost:5000", "connect ECONNREFUSED ::1:5000"),
                      ("http://localhost:5000", "connect ECONNREFUSED ::ffff:127.0.0.1:5000"),
                      ("http://localhost", "connect ECONNREFUSED ::ffff:7f00:1:80")):
        _found_and_masked(url, text)
    assert leaks("connect ECONNREFUSED ::ffff:7f00:1:5001", _bare("http://localhost:5000")) == []


def test_right_boundaries_do_not_fold_case():
    for url, text in (("http://[fd00::1]:8080", "see fd00::1K"),
                      ("http://[2001:db8::1]:8080", "see 2001:db8::1ſ"),
                      ("http://localhost", "see http://[::1]K/x"),
                      ("http://devbox", "see http://devboxK")):
        _found_and_masked(url, text)


def test_a_link_with_userinfo_after_punctuation_or_an_entity_is_not_routed():
    from live_proxy import _masker

    mask = _masker(_bare("http://uat.acme.test"), "http://127.0.0.1:9")
    for link in (b"http://uat.acme.test;@evil.test/", b"http://uat.acme.test,x@evil.test/",
                 b"http://uat.acme.test(x)@evil.test/", b"http://uat.acme.test'x@evil.test/",
                 b"http://uat.acme.test&#64;evil.test/", b"http://uat.acme.test&#x40;evil.test/",
                 b"http://uat.acme.test&commat;evil.test/"):
        out = mask(link)
        assert b"127.0.0.1:9" not in out and b"<target>" in out, (link, out)


def test_a_link_followed_by_a_non_ascii_letter_is_masked_not_routed():
    from live_proxy import _masker

    out = _masker(_bare("http://localhost"), "http://127.0.0.1:9")("see http://localhost失".encode())
    assert b"127.0.0.1:9" not in out and b"localhost" not in out


def test_infra_failure_past_the_sixth_kept_line_stays_not_run():
    from browser import _failed

    raw = "\n".join(f"line {i}" for i in range(10)) + "\nnet::ERR_CONNECTION_REFUSED"
    assert _failed(raw)["result"].startswith("not run: ")
