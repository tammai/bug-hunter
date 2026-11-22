def _bare(url: str) -> dict:
    return {"url": url, "accounts": {}}


def _found_and_masked(url: str, text: str) -> None:
    from drafts import leaks
    from live_proxy import _masker

    assert leaks(text, _bare(url)), (url, text)
    out = _masker(_bare(url), "http://127.0.0.1:9")(text.encode()).decode("utf-8")
    assert leaks(out, _bare(url)) == [], (url, text, out)


def test_ipv6_spellings_carry_the_targets_port_even_the_default():
    from drafts import leaks

    for url, text in (("https://[2001:db8::1]", "connect ECONNREFUSED 2001:db8::1:443"),
                      ("https://[2001:db8::1]", "connect ECONNREFUSED 2001:db8::1:0443"),
                      ("http://10.0.0.1:5000", "connect ECONNREFUSED ::ffff:a00:1:5000")):
        _found_and_masked(url, text)
    assert leaks("connect ECONNREFUSED 2001:db8::1:444", _bare("https://[2001:db8::1]")) == []
    assert leaks("peer ::ffff:a00:1:5001 up", _bare("http://10.0.0.1:5000")) == []


def test_a_letter_of_another_script_after_a_host_never_hides_it():
    for url, text in (("http://devbox", "see http://devbox失败"),
                      ("http://localhost", "see http://localhost失败"),
                      ("http://localhost:5000", "see localhost:5000失"),
                      ("http://10.0.0.1", "see 10.0.0.1失")):
        _found_and_masked(url, text)


def test_a_link_with_an_unrelated_address_later_still_routes():
    from live_proxy import _masker

    mask = _masker(_bare("http://localhost:5000"), "http://127.0.0.1:9")
    out = mask(b'{"base":"http://localhost:5000","contact":"admin@acme.test"}')
    assert out == b'{"base":"http://127.0.0.1:9","contact":"admin@acme.test"}'
    mask = _masker(_bare("https://uat.acme.test"), "http://127.0.0.1:9")
    out = mask(b'<a href="https://uat.acme.test">admin@acme.test</a>')
    assert out == b'<a href="http://127.0.0.1:9">admin@acme.test</a>'


def test_browser_message_never_empty_and_infra_read_from_kept_lines():
    from browser import _failed, _message

    assert _message("") == "(no error message)"
    stack_only = "expect(received).toBe(expected)\n    at net::ERR_FAKE (helper.ts:3)"
    assert _failed(stack_only)["result"] == "fail"
