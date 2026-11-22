def _target(url: str, value: str = "Bearer 9fK2xQ7vL0pR3sT8") -> dict:
    return {"url": url, "accounts": {"member": {"Authorization": value}}}


def test_mapped_and_zoned_ipv6_targets_are_checked_not_crashed():
    from drafts import leaks

    mapped = _target("http://[::ffff:10.0.0.1]:8080")
    assert leaks("ok", mapped) == []
    for text in ("curl http://[::ffff:10.0.0.1]:8080/x", "host 10.0.0.1", "[::ffff:a00:1]"):
        assert leaks(text, mapped), text
    zoned = _target("http://[fe80::1%25eth0]:8080")
    assert leaks("ok", zoned) == []
    assert leaks("curl http://[fe80::1%25eth0]:8080/x", zoned)


def test_ipv6_spellings_with_a_dotted_ipv4_tail_are_found():
    from drafts import leaks

    assert leaks("host 2001:db8::0.0.0.1", _target("http://[2001:db8::1]:8080"))
    loopback = _target("http://127.0.0.1:5000")
    for text in ("curl http://[::0.0.0.1]:5000/x", "curl http://[::ffff:127.0.0.1]:5000/x"):
        assert leaks(text, loopback), text


def test_random_token_login_is_found_in_any_case():
    from drafts import leaks

    target = _target("http://127.0.0.1:5000", "Bearer qwxzkvbnmt")
    for text in ("password: QWXZKVBNMT", "got Qwxzkvbnmt back"):
        assert leaks(text, target), text


def test_word_login_after_is_with_punctuation_or_a_value_word():
    from drafts import leaks

    target = _target("http://127.0.0.1:5000", "Bearer member")
    for text in ("the password is: member", "The password was: member",
                 "the token value is member"):
        assert leaks(text, target), text
    # `value` counts only as a key, not as another field's value; prose "key is" is not a login.
    for text in ('{"key": "value", "member": 1}', "token: value, member",
                 "the key is member access", "Auth is member", "the pass is member"):
        assert leaks(text, target) == [], text


def test_short_loopback_forms_do_not_match_inside_other_addresses():
    from drafts import leaks

    target = _target("http://127.0.0.1:5000")
    for text in ("192.168.127.1:5000", "10.127.0.1:5000", "10.0.0.0:5000"):
        assert leaks(text, target) == [], text
    assert leaks(r"\057127.0.0.1:5000", target)


def test_default_port_without_a_port_follows_the_scheme():
    from drafts import leaks

    assert leaks("curl https://localhost/x", _target("https://localhost:443"))
    assert leaks("curl http://localhost/x", _target("http://localhost:443")) == []


def test_mapped_loopback_target_keeps_its_port():
    from drafts import leaks

    target = _target("http://[::ffff:127.0.0.1]:5000")
    assert leaks("curl http://127.0.0.1:5000/x", target)
    assert leaks("curl http://127.0.0.1:5001/x", target) == []


def test_a_url_without_a_port_follows_the_drafts_scheme():
    from drafts import leaks

    assert leaks("curl https://localhost/x", _target("http://localhost:443"))
    assert leaks("curl http://localhost/x", _target("https://localhost:80"))
    assert leaks("curl wss://localhost/x", _target("https://localhost"))
    assert leaks("curl https://localhost/x", _target("http://localhost:80")) == []


def test_word_login_after_two_word_fields_and_a_value_element():
    from drafts import leaks

    target = _target("http://127.0.0.1:5000", "Bearer member")
    for text in ("the API key is member", "the secret key is member",
                 "<password><value>member</value></password>"):
        assert leaks(text, target), text


def test_long_random_token_login_is_found_in_any_case():
    from drafts import leaks

    assert leaks("PASSWORD: QWXZKVBNMTQWXZKVB",
                 _target("http://127.0.0.1:5000", "Bearer qwxzkvbnmtqwxzkvb"))


def test_placeholder_named_after_a_random_looking_login_is_clean():
    from drafts import leaks

    target = {"url": "http://127.0.0.1:5000",
              "accounts": {"dbadmin": {"Authorization": "Bearer dbadmin"}}}
    assert leaks('curl -H "$DBADMIN_AUTH" "$BASE/x"', target) == []
    assert leaks("Set ACCEPT_ACCOUNT_DBADMIN first.", target, replay=True) == []
    assert leaks("the server answered dbadmin", target)


def test_a_compound_scheme_without_a_port_is_found():
    from drafts import leaks

    assert leaks("pip install git+http://localhost/x", _target("http://localhost"))
    assert leaks("svn co svn+https://localhost/x", _target("https://localhost:443"))


def test_is_and_an_empty_value_do_not_reach_the_next_words():
    from drafts import leaks

    target = _target("http://127.0.0.1:5000", "Bearer member")
    for text in ("It works whatever the password is. Member and admin both pass.",
                 '<input type="password" value=""> member'):
        assert leaks(text, target) == [], text


def test_a_websocket_loopback_target_has_a_default_port():
    from drafts import leaks

    assert leaks("curl http://localhost:80/x", _target("ws://localhost"))


def test_a_token_shaped_value_of_any_cookie_counts_anywhere():
    from drafts import leaks

    for cookie, token in ((".AspNetCore.Cookies=CfDJ8Kq9xZ7vL0pR", "CfDJ8Kq9xZ7vL0pR"),
                          ("theme=qwxzkvbnmt; sid=qwxzkvbnmt", "qwxzkvbnmt")):
        target = {"url": "http://127.0.0.1:5000", "accounts": {"member": {"Cookie": cookie}}}
        assert leaks(f"got {token} back", target), cookie


def test_a_cut_message_keeps_its_not_run_prefix_and_never_reads_empty():
    from browser import _message
    from finding_v1 import _bounded

    assert _bounded("not run: " + "Z" * 600).startswith("not run: ")
    assert _message("Z" * 600)
