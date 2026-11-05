import json

import pytest
from conftest import run_script


def scope(repo):
    result = run_script("scope", repo)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_vue_and_svelte_files_are_hunted_as_node(make_repo):
    repo = make_repo({"web/src/App.vue": "", "web/src/Nav.svelte": "", "web/src/main.ts": ""})
    [part] = scope(repo)["parts"]
    assert part["files"] == ["web/src/App.vue", "web/src/main.ts", "web/src/Nav.svelte"]
    assert part["stacks"] == ["node"]
    assert part["edge_inputs"] == ["generic", "node"]


@pytest.mark.parametrize(
    ("files", "stacks", "edge_inputs"),
    [
        (["app/cli.py"], ["python"], ["generic", "python-cli"]),
        (["server/index.js", "server/db.mjs"], ["node"], ["generic", "node"]),
        (["cmd/main.go"], ["go"], ["generic", "go"]),
        (["src/lib.rs"], ["rust"], ["generic", "rust"]),
        (["src/App.java"], ["jvm"], ["generic", "jvm"]),
        (["src/Util.kt"], ["jvm"], ["generic", "jvm"]),
        (["lib/parser.rb"], ["ruby"], ["generic", "ruby"]),
        (["src/Cart.php"], ["php"], ["generic", "php"]),
        (["native/buf.c"], [], ["generic"]),
        (["bin/run.sh"], [], ["generic"]),
        (["mix/a.py", "mix/b.ts"], ["python", "node"], ["generic", "python-cli", "node"]),
    ],
)
def test_each_stack_gets_its_edge_inputs(make_repo, files, stacks, edge_inputs):
    repo = make_repo(dict.fromkeys(files, ""))
    [part] = scope(repo)["parts"]
    assert part["stacks"] == stacks
    assert part["edge_inputs"] == edge_inputs


def test_each_stacks_test_files_are_left_out(make_repo):
    tests = [
        "spec/a_spec.rb", "lib/b_test.rb", "src/UserTest.java", "src/UserTests.java",
        "src/UserTest.kt", "src/UserTest.php", "src/__tests__/x.ts", "pkg/x_test.go",
        "web/Nav.spec.ts", "app/test_cli.py",
    ]
    real = ["lib/real.rb", "src/Contest.php", "src/Latest.java"]
    repo = make_repo(dict.fromkeys(tests + real, ""))
    files = [f for p in scope(repo)["parts"] for f in p["files"]]
    assert sorted(files) == sorted(real)


def test_lockfiles_give_exact_locked_installs(make_repo):
    lockfiles = {
        "package-lock.json": ".",
        "web app/pnpm-lock.yaml": "web app",
        "y1/yarn.lock": "y1",
        "y2/yarn.lock": "y2",
        "y2/.yarnrc.yml": None,
        "b/bun.lockb": "b",
        "b2/bun.lock": "b2",
        "py/uv.lock": "py",
        "po/poetry.lock": "po",
        "go/go.sum": "go",
        "rs/Cargo.lock": "rs",
        "rb/Gemfile.lock": "rb",
        "ph/composer.lock": "ph",
        "jv/gradlew": "jv",
        "mv/pom.xml": "mv",
    }
    repo = make_repo({**dict.fromkeys(lockfiles, ""), "src/a.js": ""})
    got = sorted((i["dir"], i["command"]) for i in scope(repo)["installs"])
    assert got == sorted([
        (".", "npm ci --ignore-scripts"),
        ("web app", "pnpm install --frozen-lockfile --ignore-scripts"),
        ("y1", "yarn install --frozen-lockfile --ignore-scripts"),
        ("y2", "YARN_ENABLE_SCRIPTS=0 yarn install --immutable"),
        ("b", "bun install --frozen-lockfile --ignore-scripts"),
        ("b2", "bun install --frozen-lockfile --ignore-scripts"),
        ("py", "uv sync --frozen"),
        ("po", "poetry install --no-root"),
        ("go", "go mod download"),
        ("rs", "cargo fetch --locked"),
        ("rb", "BUNDLE_FROZEN=true BUNDLE_PATH=vendor/bundle bundle install"),
        ("ph", "composer install --no-scripts --no-plugins"),
        ("jv", "./gradlew --no-daemon dependencies"),
        ("mv", "mvn -B -q dependency:go-offline"),
    ])


def test_no_lockfile_means_no_installs(make_repo):
    repo = make_repo({"src/a.js": "", "package.json": "{}"})
    assert scope(repo)["installs"] == []


def test_install_steps_are_exact_and_unsafe_folders_get_none(make_repo):
    repo = make_repo({
        "src/a.js": "",
        "web app/package-lock.json": "",
        "café/go.sum": "",
        "a$(touch pwned)/package-lock.json": "",
        'b"q/yarn.lock': "",
        "c`id`/Cargo.lock": "",
        "d\\e/uv.lock": "",
        "e'f/poetry.lock": "",
        "-x/go.sum": "",
        "tests/fixtures/app/package-lock.json": "",
        "pkg/testdata/go.sum": "",
        "dup/bun.lock": "",
        "dup/bun.lockb": "",
        "mw/mvnw": "",
        "mw/pom.xml": "",
    })
    result = run_script("scope", repo)
    assert result.returncode == 0, result.stderr
    installs = json.loads(result.stdout)["installs"]
    assert [(i["dir"], i["step"]) for i in installs] == [
        ("café", "(cd 'café' && go mod download)"),
        ("dup", "(cd 'dup' && bun install --frozen-lockfile --ignore-scripts)"),
        ("mw", "(cd 'mw' && ./mvnw -B -q dependency:go-offline)"),
        ("web app", "(cd 'web app' && npm ci --ignore-scripts)"),
    ]
    assert result.stderr.count("unsafe folder name") == 6
    assert not (repo / "pwned").exists()


def test_root_install_step_is_the_bare_command(make_repo):
    repo = make_repo({"src/a.js": "", "package-lock.json": ""})
    assert scope(repo)["installs"] == [
        {"dir": ".", "command": "npm ci --ignore-scripts", "step": "npm ci --ignore-scripts"}
    ]
