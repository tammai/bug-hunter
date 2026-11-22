import os
import re
import shutil

import pytest


def _target(url: str, headers: dict | None = None) -> dict:
    return {"url": url, "accounts": {"member": headers or {"Authorization": "Bearer member"}}}


def _bare(url: str) -> dict:
    return {"url": url, "accounts": {}}


def test_masker_hides_every_spelling_the_scan_finds():
    from drafts import leaks
    from live_proxy import _masker

    cases = {
        "http://localhost:5000": ["127.1:5000", "0.0.0.0:5000", "[::1%25lo]:5000",
                                  "localhost:05000"],
        "http://10.0.0.1:8080": ["10.0.0.01", "::ffff:a00:1"],
        "http://[2001:db8::1]:8080": ["2001:0db8:0:0:0:0:0:1"],
        "https://uat.acme.test": ["xuat.acme.test", "uat.acme.test."],
    }
    for url, spellings in cases.items():
        mask = _masker(_bare(url), "http://127.0.0.1:9")
        for spelling in spellings:
            text = f"see {spelling} end"
            assert leaks(text, _bare(url)), (url, spelling)
            out = mask(text.encode()).decode("latin-1")
            assert leaks(out, _bare(url)) == [], (url, spelling, out)


def test_links_under_any_host_spelling_go_to_the_listener():
    from live_proxy import _masker

    mask = _masker(_bare("http://localhost:5000"), "http://127.0.0.1:9")
    for link in ("http://127.1:5000/x", "http://[::1]:5000/x", "http://localhost:05000/x",
                 "HTTP://LOCALHOST:5000/x"):
        assert mask(f"go {link} now".encode()) == b"go http://127.0.0.1:9/x now", link
    dotted = _masker(_bare("https://uat.acme.test"), "http://127.0.0.1:9")
    for link in ("https://uat.acme.test/x", "https://uat.acme.test:443/x",
                 "https://uat.acme.test./x"):
        assert dotted(f"go {link}".encode()) == b"go http://127.0.0.1:9/x", link
    for other in ("https://uat.acme.test.evil/x", "http://uat.acme.test/x"):
        out = dotted(other.encode())
        assert b"127.0.0.1:9" not in out and b"uat.acme.test" not in out, other


def test_two_targets_are_masked_in_one_pass_longest_first():
    from live_proxy import _masker

    one, two = "http://127.0.0.1:30001", "http://127.0.0.1:30011"
    mask = _masker(_bare("http://localhost:3000"), one, ((_bare("http://localhost:3001"), two),))
    text = b"a http://127.1:3000/x b http://localhost:3001/y c 127.1:3001 d 127.0.0.1:3000"
    assert mask(text) == (b"a " + one.encode() + b"/x b " + two.encode()
                          + b"/y c <target> d <target>")
    mask = _masker(_bare("https://acme.test"), one, ((_bare("https://uat.acme.test"), two),))
    text = b"https://uat.acme.test/x https://acme.test/y xuat.acme.test \xe9acme.test\xe9"
    assert mask(text) == (two.encode() + b"/x " + one.encode()
                          + b"/y x<target> \xe9<target>\xe9")


def test_message_cut_never_leaves_a_host_or_login_prefix():
    from browser import _message
    from finding_v1 import _bounded

    token = "uat.acme.test/Tok9fK2xQ7vL0pR3sT8"
    for cut in (_bounded, _message):
        for offset in range(440, 500):
            filler = "x " * (offset // 2) + "x" * (offset % 2)
            out = cut(f"{filler} {token} tail")
            assert token in out or token[:2] not in out, (cut.__name__, offset, out)
        out = cut("step 1: " + "Z" * 600)
        assert "Z" not in out, cut.__name__
    assert _bounded("x " * 300 + "one") != _bounded("x " * 300 + "two")


def test_trailing_dot_host_is_the_same_host():
    from drafts import leaks

    cases = {"http://localhost.:5000": ["localhost:5000", "127.0.0.1:5000"],
             "http://ref.:3000": ["ref:3000"],
             "http://uat.acme.test.": ["uat.acme.test"]}
    for url, texts in cases.items():
        for text in texts:
            assert leaks(f"curl {text}/x", _target(url)), (url, text)
    assert leaks("curl uat.acme.test./x", _target("http://uat.acme.test"))


@pytest.mark.skipif(os.name == "nt", reason="needs symlinks")
def test_linked_spec_folder_is_refused_under_another_repo_spelling(make_repo, tmp_path):
    import oracle
    from test_oracle import hunted_repo

    repo = hunted_repo(make_repo)
    outside = tmp_path / "outside-spec"
    shutil.move(repo / "spec", outside)
    (repo / "spec").symlink_to(outside, target_is_directory=True)
    alias = tmp_path / "alias"
    alias.symlink_to(repo.parent, target_is_directory=True)
    # A link above the repo spells its path differently, as an 8.3 short name does on Windows.
    for repo_arg, spec_arg in ((repo, alias / repo.name / "spec"),
                               (alias / repo.name, repo / "spec")):
        with pytest.raises(oracle.BadOracle):
            oracle.build(str(repo_arg), spec_arg)


@pytest.mark.skipif(os.name == "nt", reason="needs symlinks")
def test_files_under_a_linked_folder_are_not_read(tmp_path):
    import scope

    root, outside = tmp_path / "repo", tmp_path / "outside"
    (root / "plain").mkdir(parents=True)
    outside.mkdir()
    (outside / "a.py").write_text("MARK\n", encoding="utf-8")
    (root / "plain" / "a.py").write_text("MARK\n", encoding="utf-8")
    (root / "src").symlink_to(outside, target_is_directory=True)
    marker = re.compile("MARK")
    assert scope._any_matches(root, ["plain/a.py"], marker, marker)
    assert not scope._any_matches(root, ["src/a.py"], marker, marker)


def test_padded_ports_zones_and_ipv6_boundaries():
    from drafts import leaks

    found = [("http://localhost", "localhost:080"), ("http://localhost", "http://localhost:080/"),
             ("http://127.0.0.1:5000", "127.0.0.1:05000"),
             ("http://127.0.0.1:5000", "curl http://[::1%25lo]:5000/x"),
             ("http://127.0.0.1:5000", "curl http://[::1%lo]:5000/x"),
             ("http://ref:3000", "ref:03000"),
             ("http://10.0.0.1", "peer ::ffff:a00:1 up"),
             ("http://10.0.0.1", "peer [::ffff:a00:1] up"),
             ("http://[2001:db8::1]:8080", "reached 2001:db8::1: timeout"),
             ("http://[2001:db8::1]:8080", "curl http://[2001:db8::1]:8080/x")]
    for url, text in found:
        assert leaks(text, _target(url)), (url, text)
    clean = [("http://127.0.0.1:5000", "listener 127.0.0.1:50003"),
             ("http://[2001:db8::1]:8080", "peer 2001:db8::1:5 up"),
             ("http://[::]:8080", "std::vector<int> v;"),
             ("http://10.0.0.1", "peer ::ffff:a00:2 up")]
    for url, text in clean:
        assert leaks(text, _target(url)) == [], (url, text)


def test_word_login_reversed_or_behind_other_attributes():
    from drafts import leaks

    target = _target("http://127.0.0.1:5000")
    for text in ('<input value="member" name="password">', '{"value":"member","name":"token"}',
                 '<input name="password" type="text" value="member">',
                 '{"name":"token","type":"x","value":"member"}'):
        assert leaks(text, target), text
    for text in ('<input value="member" name="role">',
                 '<input name="role" type="text" value="member">'):
        assert leaks(text, target) == [], text


def test_only_session_like_cookie_values_count_anywhere():
    from drafts import leaks

    target = _target("http://127.0.0.1:5000", {"Cookie": "device=desktop; sid=qwxzkvbnmt"})
    assert leaks("Open the desktop layout.", target) == []
    assert leaks("Cookie: device=desktop", target)
    assert leaks("got qwxzkvbnmt back", target)
