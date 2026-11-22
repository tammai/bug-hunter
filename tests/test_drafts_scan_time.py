import time


def test_long_hostile_runs_are_scanned_in_linear_time():
    from drafts import leaks

    # Drafts quote hostile responses. At 50,000 characters a linear scan takes well under a
    # second; a pattern that restarts a run at every position would take minutes.
    runs = ("0" * 50_000, "0:" * 25_000, "0." * 25_000, ":" * 50_000, "a" * 50_000,
            "authauth" * 6_250, "password is " * 4_000, '"token","value":' * 3_000)
    for url in ("http://127.0.0.1:5000", "http://localhost", "http://localhost:80",
                "http://10.0.0.1", "http://[2001:db8::1]:8080", "http://ref"):
        target = {"url": url, "accounts": {"m": {"Authorization": "Bearer member"}}}
        for text in runs:
            start = time.monotonic()
            leaks(text, target)
            assert time.monotonic() - start < 5, (url, text[:8])
