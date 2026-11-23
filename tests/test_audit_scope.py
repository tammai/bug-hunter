import json
import os
import shutil
import sys
from pathlib import Path

from conftest import commit, run_script


def scope(repo, *args, osv=False):
    """scope.py's JSON; OSV-Scanner on PATH only when osv is True, so results don't depend on
    what this machine has installed."""
    env = None
    if not osv:
        # Only python's and git's own folders (resolved, so a shared bin of links can't bring
        # the tools back in).
        keep = [str(Path(os.path.realpath(t)).parent) for t in (sys.executable,
                                                               shutil.which("git")) if t]
        env = dict(os.environ, PATH=os.pathsep.join(dict.fromkeys(keep)))
    result = run_script("scope", repo, *args, env=env)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


FILES = {
    "lib/format.js": "",
    "src/routes/users.js": "",
    "src/utils/math.js": "",
    "src/middleware/authGuard.ts": "",
    "src/db/schema.prisma": "",
    "src/db/migrations/001_init.sql": "",
    "config/app.yaml": "",
    ".env": "SECRET=x",
    ".env.example": "",
    "Dockerfile": "",
    "docs/security.md": "",
    "web/src/App.vue": "",
    "web/src/store/session.js": "",
    "web/package.json": json.dumps({"dependencies": {"vue": "^3.4.0"}}),
    "api/package.json": json.dumps({"dependencies": {"express": "^4"}}),
    "api/server.js": "",
    "package-lock.json": "",
    "web/pnpm-lock.yaml": "",
    "tests/fixtures/app.yaml": "",
    "src/routes/users.test.js": "",
}


def test_focus_security_orders_widens_and_picks_checklists(make_repo):
    repo = make_repo(FILES)

    plain = scope(repo)
    assert "checklists" not in plain["parts"][0]
    plain_files = [f for p in plain["parts"] for f in p["files"]]
    assert "config/app.yaml" not in plain_files

    out = scope(repo, "--focus", "security")
    parts = out["parts"]
    files = [f for p in parts for f in p["files"]]
    for wanted in ("src/db/schema.prisma", "src/db/migrations/001_init.sql", "config/app.yaml",
                   ".env", "Dockerfile"):
        assert wanted in files, wanted
    for unwanted in (".env.example", "docs/security.md", "package-lock.json", "web/pnpm-lock.yaml",
                     "tests/fixtures/app.yaml", "src/routes/users.test.js",
                     "web/package.json"):
        assert unwanted not in files, unwanted

    dirs = [p["dir"] for p in parts]
    security_dirs = {"src/routes", "src/middleware", "src/db", "src/db/migrations", "config",
                     "web/src/store", ".", "api"}
    security = [d for d in dirs if d in security_dirs]
    assert dirs[: len(security)] == security
    assert dirs.index("src/utils") > dirs.index("src/routes")
    assert dirs.index("lib") > dirs.index("src/middleware")
    assert [p["id"] for p in parts] == list(range(1, len(parts) + 1))

    by_dir = {p["dir"]: p["checklists"] for p in parts}
    assert by_dir["src/db/migrations"] == ["generic", "pii"]
    assert by_dir["src/routes"] == ["generic", "pii", "node"]
    assert by_dir["web/src"] == ["generic", "pii", "node", "vue"]
    assert by_dir["web/src/store"] == ["generic", "pii", "node", "vue"]
    assert by_dir["api"] == ["generic", "pii", "node"]

    capped = scope(repo, "--focus", "security", "--max", "2")
    assert [p["dir"] for p in capped["parts"]] == dirs[:2]


def test_focus_ranks_identity_then_entry_points_then_data(make_repo):
    # The shape of gothinkster/node-express-realworld-example-app, where --max 2 used to keep
    # only jest config: nearly every part matched some keyword, so the sort did nothing.
    repo = make_repo({
        "Dockerfile": "",
        "jest.config.ts": "",
        "e2e/jest.config.ts": "",
        "src/app/models/http-exception.model.ts": "",
        "src/app/routes/routes.ts": "",
        "src/app/routes/auth/auth.service.ts": "",
        "src/app/routes/profile/profile.controller.ts": "",
        "src/lib/strings.ts": "",
    })
    dirs = [p["dir"] for p in scope(repo, "--focus", "security")["parts"]]
    assert dirs == ["src/app/routes/auth",                       # identity
                    "src/app/routes", "src/app/routes/profile",  # entry points
                    ".", "e2e", "src/app/models",                # data and config
                    "src/lib"]                                   # the rest
    capped = scope(repo, "--focus", "security", "--max", "2")["parts"]
    assert [p["dir"] for p in capped] == ["src/app/routes/auth", "src/app/routes"]
    # Plain /hunt ignores the tiers: folder order, with jest config (tooling) last.
    assert [p["dir"] for p in scope(repo)["parts"]][0] == "src/app/models"


def test_author_is_not_auth(make_repo):
    # node-express-realworld-example-app: article/author.mapper.ts outranked auth/token.utils.ts.
    repo = make_repo({
        "src/article/author.mapper.ts": "",
        "src/policy/authorization.ts": "",
        "src/routes/index.ts": "",
    })
    dirs = [p["dir"] for p in scope(repo, "--focus", "security")["parts"]]
    assert dirs == ["src/policy", "src/routes", "src/article"]


def test_lockfiles_give_dependency_audit_steps(make_repo):
    repo = make_repo({
        "src/a.js": "",
        "package-lock.json": "",
        "php app/composer.lock": "",
        "y/yarn.lock": "",
        "tests/fixtures/x/package-lock.json": "",
        "a$(id)/package-lock.json": "",
    })
    # Without OSV-Scanner, npm and composer audit where they apply (the OSV steps are tested in
    # test_audit_stack_coverage.py).
    assert scope(repo)["audits"] == [
        {"dir": ".", "lockfile": "package-lock.json", "command": "npm audit --omit=dev --json",
         "step": "npm audit --omit=dev --json", "tool": "npm"},
        {"dir": "php app", "lockfile": "php app/composer.lock",
         "command": "composer audit --no-plugins --no-scripts --format=json",
         "step": "(cd 'php app' && composer audit --no-plugins --no-scripts --format=json)",
         "tool": "composer"},
    ]
    assert "unsafe folder name" in run_script("scope", repo).stderr


def test_scope_reports_coverage_gaps(make_repo):
    repo = make_repo({
        "src/app.py": "",
        "jvm/App.java": "",
        "web/src/App.jsx": "",
        "web/package.json": json.dumps({"dependencies": {"react": "^18"}}),
        "web/package-lock.json": "",
        "packages/ui/index.js": "",
        "packages/ui/package.json": "{}",
        "package.json": "{}",
        "pnpm-lock.yaml": "",
        "api/server.js": "",
        "api/package.json": "{}",
        "deploy/run.sh": "",
        "deploy/build.sh": "",
        "tool/main.go": "",
        "tool/go.mod": "module tool",
        "svc/main.go": "",
        "svc/go.mod": "module svc",
        "svc/go.sum": "",
        "tests/fixtures/x/package.json": "{}",
    })
    commit(repo)
    out = scope(repo, "--focus", "security")
    by_dir = {p["dir"]: p for p in out["parts"]}
    assert by_dir["src"]["no_checklist"] == [] and "python" in by_dir["src"]["checklists"]
    assert by_dir["jvm"]["no_checklist"] == ["jvm"]
    assert by_dir["web/src"]["no_checklist"] == []
    assert "react" in by_dir["web/src"]["checklists"]
    assert by_dir["api"]["no_checklist"] == []
    assert by_dir["tool"]["no_checklist"] == [] and "go" in by_dir["tool"]["checklists"]
    coverage = out["coverage"]
    assert coverage["other_files"] == {".sh": 2}
    assert coverage["manifests_without_lockfile"] == ["tool/go.mod"]
    assert coverage["unaudited_lockfiles"] == ["pnpm-lock.yaml", "svc/go.sum"]
    assert coverage["dirty"] is False and len(coverage["commit"]) == 40
    assert coverage["paths"] == [] and coverage["unsafe_folders"] == []

    (repo / "src/new.py").write_text("x = 1\n", encoding="utf-8")
    assert scope(repo, "--focus", "security")["coverage"]["dirty"] is True
    narrowed = scope(repo, "src", "--focus", "security")["coverage"]
    assert narrowed["paths"] == ["src"]


def test_git_calls_and_inventory_cells_cant_be_steered(make_repo, tmp_path):
    import os
    import subprocess
    stripe = "sk_" + "live_" + "a1" * 12
    repo = make_repo({"src/app.js": "x\n", "config.js": f'const k = "{stripe}";\n'})
    commit(repo)
    other = tmp_path / "other"
    other.mkdir()
    subprocess.run(["git", "init", "-q", str(other)], check=True)
    env = {**os.environ, "GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other),
           "GIT_INDEX_FILE": str(other / ".git" / "index")}
    result = run_script("scope", repo, "--focus", "security", env=env)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert any("src/app.js" in part["files"] for part in data["parts"])
    assert data["coverage"]["commit"] and data["coverage"]["dirty"] is False
    result = run_script("secrets_scan", repo, env=env)
    assert result.returncode == 0, result.stderr
    assert any(f["path"] == "config.js" for f in json.loads(result.stdout))

    audit = tmp_path / "audit"
    audit.mkdir()
    blocks = tmp_path / "blocks.txt"
    blocks.write_text("=== PII INVENTORY ===\n"
                      "| field | defined | logged | returned | sent to | stored | deletion |\n"
                      "| email\x1b[2J | src/a.js:1 | no\x07 | yes\x9b | - | db\u200bx | - |\n"
                      "=== END ===\n", encoding="utf-8")
    assert run_script("findings", "inventory", blocks, audit).returncode == 0
    report_run = run_script("findings", "report", audit)
    assert report_run.returncode == 0, report_run.stderr
    for name in ("inventory.md", "REPORT.md"):
        text = (audit / name).read_text(encoding="utf-8")
        assert "email" in text
        assert not any(not c.isprintable() and c not in "\n" for c in text), name


def test_the_dirty_check_runs_no_program_from_the_target_config(make_repo, tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    import pytest
    if os.name == "nt":
        pytest.skip("filter commands here are POSIX shell")
    marker = tmp_path / "ran"
    gitconfig = tmp_path / "global.gitconfig"
    gitconfig.write_text('[filter "g"]\n\tclean = tr a b\n', encoding="utf-8")
    env = {**os.environ, "GIT_CONFIG_GLOBAL": str(gitconfig)}

    def git(repo, *args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                       env=env)

    def run(repo):
        result = subprocess.run([sys.executable, str(Path(__file__).parent.parent / "scripts"
                                                     / "scope.py"), str(repo), "--focus",
                                 "security"], capture_output=True, text=True, env=env)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)["coverage"]["dirty"]

    def make(name, attributes, config):
        repo = tmp_path / name
        repo.mkdir()
        git(repo, "init", "-q")
        (repo / ".gitattributes").write_text(attributes, encoding="utf-8")
        (repo / "app.js").write_text("x\n", encoding="utf-8")
        for file in ("a.txt", "b.dat", "c.g"):
            (repo / file).write_text("a\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "i")
        for key, value in config:
            git(repo, "config", key, value)
        later = os.stat(repo / "a.txt").st_mtime + 5
        for file in ("a.txt", "b.dat", "c.g"):
            os.utime(repo / file, (later, later))
        return repo

    hostile = make("hostile", "*.txt filter=a=b.c\n*.dat filter=p.q\n*.g filter=g\n",
                   [("filter.a=b.c.clean", f"touch {marker}; cat"),
                    ("filter.p.q.process", f"touch {marker}")])
    # Blanked, its filters change nothing here, so the files read as they were committed.
    assert run(hostile) is False
    assert not marker.exists()

    required = make("required", "*.txt filter=r\n",
                    [("filter.r.clean", f"touch {marker}; cat"), ("filter.r.required", "true")])
    assert run(required) is None
    assert not marker.exists()

    owners = make("owners", "*.g filter=g\n", [])
    assert run(owners) is False

    # A treeless partial clone fetches missing trees on demand, through the target's config.
    src = tmp_path / "src"
    src.mkdir()
    git(src, "init", "-q")
    (src / "d").mkdir()
    (src / "d" / ".env").write_text("x\n", encoding="utf-8")
    git(src, "add", "-A")
    git(src, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "i")
    git(src, "config", "uploadpack.allowFilter", "true")
    git(src, "config", "uploadpack.allowAnySHA1InWant", "true")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "--no-checkout", "--filter=tree:0",
                    src.as_uri(), str(clone)], check=True, capture_output=True, env=env)
    upload = tmp_path / "upload.sh"
    upload.write_text(f'#!/bin/sh\ntouch "{marker}"\nexec git-upload-pack "$@"\n',
                      encoding="utf-8")
    upload.chmod(0o755)
    git(clone, "config", "remote.origin.uploadpack", str(upload))
    import secrets_scan
    # Without the trees git can't answer, which reads as "maybe in history", never as "not".
    assert secrets_scan.in_history(str(clone), "d/.env") is not False
    assert not marker.exists()


def test_an_old_git_fails_closed_and_no_transport_runs(make_repo, tmp_path, monkeypatch):
    import os
    import subprocess

    import pytest
    import scope as scope_module
    import secrets_scan
    if os.name == "nt":
        pytest.skip("the upload-pack stand-in is a POSIX shell script")

    def git(repo, *args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    repo = make_repo({"app.js": "x\n"})
    commit(repo)
    assert scope_module._blank_filters(str(repo)) == {}
    git(repo, "config", "filter.x.clean", "cat")
    assert scope_module._blank_filters(str(repo)) == {
        "filter.x.clean": "", "filter.x.smudge": "", "filter.x.process": ""}

    # Before 2.31 git ignores GIT_CONFIG_COUNT, so a blanked driver would still run.
    for module in (scope_module, secrets_scan):
        monkeypatch.setattr(module, "git_version", lambda: (2, 30, 9), raising=False)
    assert scope_module._blank_filters(str(repo)) is None
    git(repo, "config", "--unset", "filter.x.clean")
    assert scope_module._blank_filters(str(repo)) == {}

    marker = tmp_path / "ran"
    src = tmp_path / "src"
    src.mkdir()
    git(src, "init", "-q")
    (src / ".env").write_text("x\n", encoding="utf-8")
    git(src, "add", "-A")
    git(src, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "i")
    git(src, "config", "uploadpack.allowFilter", "true")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "--no-checkout", "--filter=tree:0", src.as_uri(),
                    str(clone)], check=True, capture_output=True)
    upload = tmp_path / "upload.sh"
    upload.write_text(f'#!/bin/sh\ntouch "{marker}"\nexec git-upload-pack "$@"\n',
                      encoding="utf-8")
    upload.chmod(0o755)
    git(clone, "config", "remote.origin.uploadpack", str(upload))
    # Before 2.45.1 GIT_NO_LAZY_FETCH is ignored: a partial clone can't be asked at all.
    monkeypatch.setattr(secrets_scan, "git_version", lambda: (2, 45, 0))
    assert secrets_scan.in_history(str(clone), ".env") is None
    assert secrets_scan.in_history(str(repo), "app.js") is True
    # On any git, no transport runs: a fetch is refused before it starts the remote's program.
    monkeypatch.setattr(secrets_scan, "git_version", lambda: (2, 50, 1))
    assert secrets_scan.run_git(str(clone), "fetch", "-q", "origin").returncode != 0
    assert not marker.exists()
    # Even when the target's own config allows the transport by name.
    for name in ("file", "ext"):
        git(clone, "config", f"protocol.{name}.allow", "always")
    assert secrets_scan.run_git(str(clone), "fetch", "-q", "origin").returncode != 0
    assert not marker.exists()

    # browser.py stays standalone, but its one git call is hardened the same way.
    import browser
    other = tmp_path / "other"
    other.mkdir()
    git(other, "init", "-q")
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    assert browser._tracked(str(repo)) == ["app.js"]


def test_submodules_are_a_gap_and_their_filters_never_run(make_repo, tmp_path):
    import os
    import subprocess

    import pytest
    if os.name == "nt":
        pytest.skip("filter commands here are POSIX shell")

    def git(repo, *args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    sub = tmp_path / "sub"
    sub.mkdir()
    git(sub, "init", "-q")
    (sub / ".gitattributes").write_text("* filter=evil\n", encoding="utf-8")
    (sub / "lib.js").write_text("x\n", encoding="utf-8")
    git(sub, "add", "-A")
    git(sub, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "i")
    repo = make_repo({"app.js": "x\n"})
    git(repo, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub), "sub")
    commit(repo)
    marker = tmp_path / "ran"
    git(repo / "sub", "config", "filter.evil.clean", f"touch {marker}; cat")
    later = os.stat(repo / "sub" / "lib.js").st_mtime + 5
    os.utime(repo / "sub" / "lib.js", (later, later))
    cover = scope(repo, "--focus", "security")["coverage"]
    assert not marker.exists()
    assert cover["submodules"] == ["sub"]

    audit = tmp_path / "audit"
    audit.mkdir()
    facts = tmp_path / "scope.json"
    facts.write_text(json.dumps({"parts": [], "skipped": [], "audits": [],
                                 "coverage": cover}), encoding="utf-8")
    assert run_script("findings", "report", audit, "--scope", facts).returncode == 0
    report = (audit / "REPORT.md").read_text(encoding="utf-8")
    assert "submodule not checked for uncommitted changes: sub" in report


def test_an_unknown_history_for_a_local_secret_is_a_gap(tmp_path, monkeypatch, capsys):
    import subprocess

    import secrets_scan

    def git(repo, *args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    stripe = "sk_" + "live_" + "a1" * 12
    src = tmp_path / "src"
    src.mkdir()
    git(src, "init", "-q")
    (src / ".env").write_text(f"STRIPE={stripe}\n", encoding="utf-8")
    (src / "app.js").write_text("x\n", encoding="utf-8")
    git(src, "add", "-A")
    git(src, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "i")
    git(src, "rm", "-q", "--cached", ".env")
    (src / ".gitignore").write_text(".env\n", encoding="utf-8")
    git(src, "add", ".gitignore")
    git(src, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "untrack")
    git(src, "config", "uploadpack.allowFilter", "true")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "--filter=blob:none", src.as_uri(), str(clone)],
                   check=True, capture_output=True)
    (clone / ".env").write_text(f"STRIPE={stripe}\n", encoding="utf-8")
    monkeypatch.setattr(secrets_scan, "git_version", lambda: (2, 45, 0))
    assert secrets_scan._main([str(clone)]) == 0
    [item] = [f for f in json.loads(capsys.readouterr().out) if f["path"] == ".env"]
    assert item["committed"] is False and item["history_unknown"] is True

    audit = tmp_path / "audit"
    audit.mkdir()
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"secrets_scanned": True, "history_unknown": [".env"]}),
                    encoding="utf-8")
    assert run_script("findings", "report", audit, "--meta", meta).returncode == 0
    report = (audit / "REPORT.md").read_text(encoding="utf-8")
    assert "couldn't tell whether git history holds .env" in report


def test_a_shallow_clone_cant_say_a_path_was_never_committed(tmp_path, capsys):
    import subprocess

    import secrets_scan

    def git(repo, *args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    stripe = "sk_" + "live_" + "a1" * 12
    src = tmp_path / "src"
    src.mkdir()
    git(src, "init", "-q")
    (src / ".env").write_text(f"STRIPE={stripe}\n", encoding="utf-8")
    (src / "app.js").write_text("x\n", encoding="utf-8")
    git(src, "add", "-A")
    git(src, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "i")
    git(src, "rm", "-q", "--cached", ".env")
    (src / ".gitignore").write_text(".env\n", encoding="utf-8")
    git(src, "add", ".gitignore")
    git(src, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "untrack")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "--depth", "1", src.as_uri(), str(clone)],
                   check=True, capture_output=True)
    (clone / ".env").write_text(f"STRIPE={stripe}\n", encoding="utf-8")
    assert secrets_scan.in_history(str(clone), ".env") is None
    assert secrets_scan._main([str(clone)]) == 0
    [item] = [f for f in json.loads(capsys.readouterr().out) if f["path"] == ".env"]
    assert item["committed"] is False and item["history_unknown"] is True
    data = tmp_path / "s.json"
    data.write_text(json.dumps([item]), encoding="utf-8")
    out = tmp_path / "out"
    assert run_script("findings", "from-secrets-scan", data, out).returncode == 0
    [text] = [p.read_text(encoding="utf-8") for p in out.glob("*.md")]
    assert "not committed" not in text.splitlines()[0]
    impact = text.split("## Impact\n")[1].split("\n")[0]
    assert impact.startswith("Maybe in git history already (git couldn't say)")
    assert ".env:1 pattern=stripe-live-key" in text and "committed=false" in text


def test_replaced_history_cant_say_a_path_was_never_committed(make_repo):
    import subprocess

    import secrets_scan

    def git(*args):
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
                        *args], check=True, capture_output=True)

    repo = make_repo({".env": "x\n", "app.js": "x\n"})
    commit(repo)
    git("rm", "-q", "--cached", ".env")
    git("commit", "-qm", "untrack")
    assert secrets_scan.in_history(str(repo), ".env") is True
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True,
                          text=True).stdout.strip()
    # A graft that makes HEAD a root hides the commit that held .env from a plain rev-list.
    git("replace", "--graft", head)
    assert secrets_scan.in_history(str(repo), ".env") is not False
    git("replace", "-d", head)
    (repo / ".git" / "info").mkdir(exist_ok=True)
    (repo / ".git" / "info" / "grafts").write_text(head + "\n", encoding="utf-8")
    assert secrets_scan.in_history(str(repo), ".env") is None


def test_a_git_timeout_is_cant_say_never_clean(make_repo, monkeypatch, capsys):
    import subprocess

    import browser
    import scope as scope_module
    import secrets_scan
    import throwaway
    assert browser._REPO_VARS == frozenset(throwaway._REPO_VARS)

    repo = make_repo({"app.js": "x\n"})
    commit(repo)

    def slow(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs.get("timeout") or 1)

    monkeypatch.setattr(secrets_scan, "git_version", lambda: (2, 50, 1))
    monkeypatch.setattr(subprocess, "run", slow)
    assert secrets_scan.run_git(str(repo), "status").returncode == 124
    assert secrets_scan.in_history(str(repo), "app.js") is None
    assert browser._tracked(str(repo)) is None
    for main in (secrets_scan._main, scope_module._main):
        assert main([str(repo)]) == 1
        err = capsys.readouterr().err
        assert err.startswith(f"error: git timed out on {repo}"), err


def test_only_submodules_inside_the_runs_paths_are_a_gap(make_repo, tmp_path):
    import subprocess

    def run(repo, *args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    sub = tmp_path / "sub"
    sub.mkdir()
    run(sub, "init", "-q")
    (sub / "lib.js").write_text("x\n", encoding="utf-8")
    run(sub, "add", "-A")
    run(sub, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "i")
    repo = make_repo({"api/app.js": "x\n", "web/app.js": "x\n"})
    for where in ("api/vendor/lib", "web/vendor/lib"):
        run(repo, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub), where)
    commit(repo)
    assert scope(repo, "--focus", "security")["coverage"]["submodules"] == [
        "api/vendor/lib", "web/vendor/lib"]
    assert scope(repo, "api", "--focus", "security")["coverage"]["submodules"] == [
        "api/vendor/lib"]
