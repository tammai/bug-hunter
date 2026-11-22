import json

from conftest import commit, run_script


def scope(repo, *args):
    result = run_script("scope", repo, *args)
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
    result = run_script("scope", repo)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["audits"] == [
        {"dir": ".", "lockfile": "package-lock.json", "command": "npm audit --omit=dev --json",
         "step": "npm audit --omit=dev --json"},
        {"dir": "php app", "lockfile": "php app/composer.lock",
         "command": "composer audit --no-plugins --no-scripts --format=json",
         "step": "(cd 'php app' && composer audit --no-plugins --no-scripts --format=json)"},
    ]
    assert "unsafe folder name" in result.stderr


def test_scope_reports_coverage_gaps(make_repo):
    repo = make_repo({
        "src/app.py": "",
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
    assert by_dir["src"]["no_checklist"] == ["python"]
    assert by_dir["web/src"]["no_checklist"] == ["react"]
    assert "react" not in by_dir["web/src"]["checklists"]
    assert by_dir["api"]["no_checklist"] == []
    assert by_dir["tool"]["no_checklist"] == ["go"]
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
