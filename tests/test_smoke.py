from bug_hunter_version import version


def test_version_matches_manifest():
    assert version() == "0.1.0"
