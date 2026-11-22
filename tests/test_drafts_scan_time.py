import time

URLS = ("http://127.0.0.1:5000", "http://localhost", "http://localhost:80", "http://10.0.0.1",
        "http://[2001:db8::1]:8080", "http://ref", "http://uat.acme.test.")
RUNS = ("0" * 50_000, "0:" * 25_000, "0." * 25_000, ":" * 50_000, "a" * 50_000,
        "authauth" * 6_250, "password is " * 4_000, '"token","value":' * 3_000,
        'value="member" name="' * 2_500, 'name="password" type="text" ' * 2_000,
        'password="' + 'a="' * 16_000, "[::1%25" * 7_000, ":0" * 25_000, "localhost:0" * 4_500,
        "a+" * 25_000, "git+" * 12_500, 'value="m" a="b" ' * 3_000, "http://localhost" * 3_000,
        "é" * 50_000, "失" * 50_000)


def test_long_hostile_runs_are_scanned_in_linear_time():
    from drafts import leaks

    # Drafts quote hostile responses. At 50,000 characters a linear scan takes well under a
    # second; a pattern that restarts a run at every position would take minutes.
    for url in URLS:
        target = {"url": url, "accounts": {"m": {"Authorization": "Bearer member",
                                                 "Cookie": "device=desktop; sid=qwxzkvbnmt"}}}
        for text in RUNS:
            start = time.monotonic()
            leaks(text, target)
            assert time.monotonic() - start < 5, (url, text[:8])


def test_masker_masks_long_hostile_runs_in_linear_time():
    from live_proxy import _masker

    # The masker runs the scan's patterns on every response the target sends.
    for url in URLS:
        mask = _masker({"url": url, "accounts": {}}, "http://127.0.0.1:9")
        for data in (*(text.encode() for text in RUNS), b"\xe9" * 50_000):
            start = time.monotonic()
            mask(data)
            assert time.monotonic() - start < 2, (url, data[:8])
