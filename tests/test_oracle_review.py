import json

import pytest
from conftest import git
from test_oracle import SPEC, TEXTS, commit, hunted_repo, scope, sha, story


def part(out, feature):
    return next(p for p in out["parts"] if p["feature"] == feature)


@pytest.mark.parametrize("bad", ["deleted", 123, None])
def test_a_lock_hash_that_is_missing_or_not_text_gives_level_0(make_repo, bad):
    repo = hunted_repo(make_repo)
    lock = json.loads(SPEC["spec/criteria.lock.json"])
    for c in lock["criteria"]:
        if c["id"] == "F-TSK-03.AC1":
            if bad == "deleted":
                del c["text_sha256"]
            else:
                c["text_sha256"] = bad
    (repo / "spec" / "criteria.lock.json").write_text(json.dumps(lock), encoding="utf-8")
    result, out = scope(repo)
    assert result.returncode == 0, result.stderr
    stats = part(out, "F-TSK-03")
    assert stats["criteria"][0]["level"] == 0 and stats["below_level_2"] is True


def test_a_crlf_story_with_matching_hashes_keeps_its_level(make_repo):
    repo = hunted_repo(make_repo)
    text = story("F-TSK-03", [("F-TSK-03.AC1", TEXTS["F-TSK-03.AC1"])]).replace("\n", "\r\n")
    (repo / "spec" / "features" / "F-TSK-03.md").write_bytes(text.encode())
    _, out = scope(repo)
    assert part(out, "F-TSK-03")["criteria"][0]["level"] == 2


def test_a_git_log_that_fails_is_one_error_line(make_repo):
    repo = hunted_repo(make_repo)
    git(repo, "symbolic-ref", "HEAD", "refs/heads/unborn")  # the index stays, history doesn't
    result, _ = scope(repo)
    assert result.returncode == 1 and result.stderr.startswith("error:"), result.stdout
    assert result.stderr.count("\n") == 1 and "Traceback" not in result.stderr


def test_numstat_starts_a_commit_only_on_a_hash(monkeypatch):
    import oracle

    good = "a" * 40
    monkeypatch.setattr(oracle, "_git", lambda *a, **k: (
        f"\x01not a hash\0\n1\t0\tsrc/a.py\0\x01{good}\0\n2\t0\tsrc/b.py\0"))
    assert oracle._numstat("repo") == {good: {"src/b.py": 2}}


def test_git_pins_signature_and_follow_config(make_repo, monkeypatch):
    import oracle

    repo = hunted_repo(make_repo)
    git(repo, "config", "log.showSignature", "true")
    git(repo, "config", "log.follow", "true")
    seen = []
    real = oracle.subprocess.run
    monkeypatch.setattr(oracle.subprocess, "run",
                        lambda argv, **k: seen.append(argv) or real(argv, **k))
    oracle.build(str(repo), repo / "spec")
    logs = [argv for argv in seen if "log" in argv]
    assert logs and all("log.showSignature=false" in argv and "log.follow=false" in argv
                        for argv in logs), logs


def test_an_os_error_running_git_is_one_error_line(make_repo, monkeypatch, capsys):
    import oracle

    repo = hunted_repo(make_repo)

    def refuse(*args, **kwargs):
        raise OSError(7, "Argument list too long")

    monkeypatch.setattr(oracle, "_git", refuse)
    assert oracle._main(["scope", str(repo), "--oracle", str(repo / "spec")]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error:") and err.count("\n") == 1


def test_each_criterion_is_read_from_its_own_story(make_repo):
    repo = hunted_repo(make_repo)
    lock = json.loads(SPEC["spec/criteria.lock.json"])
    for c in lock["criteria"]:
        if c["id"] == "F-TSK-01.AC2":
            c["file"] = "features/F-TSK-01-b.md"
    commit(repo, {"spec/criteria.lock.json": json.dumps(lock),
                  "spec/features/F-TSK-01.md": story(
                      "F-TSK-01", [("F-TSK-01.AC1", TEXTS["F-TSK-01.AC1"])]),
                  "spec/features/F-TSK-01-b.md": story(
                      "F-TSK-01", [("F-TSK-01.AC2", TEXTS["F-TSK-01.AC2"])])}, "split")
    _, out = scope(repo)
    second = part(out, "F-TSK-01")["criteria"][1]
    assert second == {"id": "F-TSK-01.AC2", "level": 2, "text": TEXTS["F-TSK-01.AC2"]}


def test_story_criteria_are_read_as_the_lock_producer_reads_them(make_repo):
    repo = hunted_repo(make_repo)
    odd = "Given a b, then 2."  # a line separator to splitlines, not to the producer
    lock = json.loads(SPEC["spec/criteria.lock.json"])
    for c in lock["criteria"]:
        if c["id"] == "F-TSK-03.AC1":
            c["text_sha256"] = sha(odd)
    text = story("F-TSK-03", [("F-TSK-03.AC1", odd), ("F-TSK-03.AC1", "Given a copy, then 9.")])
    text += "\n## Notes\n- **F-TSK-03.AC1** Not a criterion here.\n"
    commit(repo, {"spec/criteria.lock.json": json.dumps(lock),
                  "spec/features/F-TSK-03.md": text}, "odd")
    _, out = scope(repo)
    assert part(out, "F-TSK-03")["criteria"][0] == {"id": "F-TSK-03.AC1", "level": 2,
                                                    "text": odd}


@pytest.mark.parametrize("text", [
    "Per `domain.md` §Roles.", "Per domain.md, §Roles.", "Per **domain.md** §Roles.",
    "Per domain.md: §Roles.", "Per domain.md (§Roles).", "Per domain.md - §Roles.",
    "Per domain.md — §Roles.", "Per domain.md – §Roles.", "Per _domain.md_ §Roles.",
    "Per **domain.md**, §Roles.",
])
def test_markup_and_punctuation_between_the_file_and_section_sign(text):
    from oracle import rule_citations

    assert rule_citations(text, ["Roles"]) == (["Roles"], 0), text
    assert rule_citations(text.replace("§", "and §"), ["Roles"]) == ([], 0), text
