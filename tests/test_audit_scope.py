import json

from conftest import run_script


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
        {"dir": ".", "command": "npm audit --omit=dev --json",
         "step": "npm audit --omit=dev --json"},
        {"dir": "php app", "command": "composer audit --no-plugins --no-scripts --format=json",
         "step": "(cd 'php app' && composer audit --no-plugins --no-scripts --format=json)"},
    ]
    assert "unsafe folder name" in result.stderr
