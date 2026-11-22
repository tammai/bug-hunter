import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _target(url: str, headers: dict | None = None) -> dict:
    return {"url": url, "accounts": {"member": headers or {"Authorization": "Bearer member"}}}


def _bare(url: str) -> dict:
    return {"url": url, "accounts": {}}


def test_browser_script_runs_alone_on_the_standard_library(tmp_path):
    shutil.copy(SCRIPTS / "browser.py", tmp_path / "browser.py")
    result = subprocess.run([sys.executable, "-I", "browser.py", "--help"], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_ipv6_target_with_its_port_unbracketed_is_found():
    from drafts import leaks

    target = _target("http://[2001:db8::1]:8080")
    for text in ("host 2001:db8:0:0:0:0:0:1:8080 up", "host 2001:db8::1:08080 up"):
        assert leaks(text, target), text
    assert leaks("host 2001:db8::1:8081 up", target) == []


def test_ipv6_followed_by_a_letter_of_another_script_is_found():
    from drafts import leaks

    assert leaks("fd00::1失败", _target("http://[fd00::1]:8080"))


def test_masker_and_scan_agree_on_folded_letters_and_zones():
    from drafts import leaks
    from live_proxy import _masker

    for url, text in (("https://uat.acme.test", "see uat.acme.teſt end"),
                      ("https://kube.acme.test", "see Kube.acme.test end"),
                      ("http://localhost:5000", "see [::1%25lö]:5000 end")):
        assert leaks(text, _bare(url)), text
        out = _masker(_bare(url), "http://127.0.0.1:9")(text.encode())
        assert leaks(out.decode("utf-8"), _bare(url)) == [], (text, out)


def test_random_value_of_a_non_session_cookie_counts_anywhere():
    from drafts import leaks

    for cookie, token in (("theme=qwxzkvbnmt", "qwxzkvbnmt"),
                          ("theme=qwxzkvbnmtplkjhgfdsa", "qwxzkvbnmtplkjhgfdsa")):
        target = _target("http://127.0.0.1:5000", {"Cookie": cookie})
        assert leaks(f"got {token} back", target), cookie


def test_value_first_login_behind_other_attributes():
    from drafts import leaks

    target = _target("http://127.0.0.1:5000")
    for text in ('<input value="member" type="text" name="password">',
                 '{"value":"member","type":"x","name":"token"}'):
        assert leaks(text, target), text
    assert leaks('<input value="member" type="text" name="role">', target) == []


def test_browser_failure_message_keeps_a_digest_and_infra_failures_stay_not_run():
    from browser import _failed, _message

    assert _message("Z" * 600) != _message("Z" * 599 + "Y")
    infra = "Error: " + "x " * 300 + "net::ERR_CONNECTION_REFUSED at http://x"
    assert _failed(infra)["result"].startswith("not run: ")
    assert _failed("expect(received).toBe(expected)")["result"] == "fail"


def test_default_port_url_behind_any_scheme_characters_is_found():
    from drafts import leaks

    for url, scheme in (("http://localhost", "http"), ("https://localhost", "https")):
        for before in ("...", "endpoint.", "-", "1.", "\\057", "git+"):
            text = f"see {before}{scheme}://localhost/x"
            assert leaks(text, _target(url)), (url, text)
    assert leaks("see https://localhost/x", _target("http://localhost:80")) == []


def test_value_key_takes_one_bracket_and_one_quote():
    from drafts import leaks

    target = _target("http://127.0.0.1:5000")
    for text in ('name="password" value="" member', '<input name="password" value="" member>'):
        assert leaks(text, target) == [], text
    for text in ('{"name":"token","value":"member"}', '{"password": {"value":["member"]}}',
                 "<password><value>member</value></password>"):
        assert leaks(text, target), text


def test_is_takes_markdown_and_typographic_wrappers():
    from drafts import leaks

    target = _target("http://127.0.0.1:5000")
    for text in ("the password is **member**", "the password is *member*",
                 "the password is - member", "the password is – member",
                 "the password is “member”", "the password is ‘member’",
                 "the password is (member)", "the password is <member>",
                 "the password is member"):
        assert leaks(text, target), text
    assert leaks("It works whatever the password is. Member and admin pass.", target) == []


def test_a_link_followed_by_userinfo_is_not_routed():
    from live_proxy import _masker

    for url, link in (("https://uat.acme.test", b"https://uat.acme.test@evil.test/x"),
                      ("http://localhost:5000", b"http://localhost:5000@evil.test/x")):
        out = _masker(_bare(url), "http://127.0.0.1:9")(link)
        assert b"127.0.0.1:9" not in out, (url, out)


def test_bare_host_with_its_port_masks_the_host_only():
    from live_proxy import _masker

    mask = _masker(_bare("https://uat.acme.test:8443"), "http://127.0.0.1:9")
    assert mask(b"peer uat.acme.test:8443 up") == b"peer <target>:8443 up"
