import json
import shutil
import subprocess

from conftest import run_script

FILES = {
    "src/cli.py": "",
    "src/my dir/naïve.py": "",
    "b10/x.py": "",
    "b2/y.py": "",
    "README.md": "",
    "uv.lock": "",
    "tests/test_cli.py": "",
    "src/test_foo.py": "",
    "pkg/a_test.go": "",
    "web/app.test.ts": "",
    **{f"big/f{i}.py": "" for i in range(1, 8)},
}


def scope(repo, *args):
    result = run_script("scope", repo, *args)
    return result, (json.loads(result.stdout) if result.returncode == 0 else None)


def test_splits_tracked_source_files_into_parts(make_repo):
    repo = make_repo(FILES)
    result, out = scope(repo)
    assert result.returncode == 0, result.stderr
    assert [(p["dir"], p["files"]) for p in out["parts"]] == [
        ("b2", ["b2/y.py"]),
        ("b10", ["b10/x.py"]),
        ("big", [f"big/f{i}.py" for i in range(1, 6)]),
        ("big", ["big/f6.py", "big/f7.py"]),
        ("src", ["src/cli.py"]),
        ("src/my dir", ["src/my dir/naïve.py"]),
    ]
    assert [p["id"] for p in out["parts"]] == [1, 2, 3, 4, 5, 6]
    assert out["hunters"] == 6
    assert out["est_tokens"] == 600_000
    assert out["skipped"] == []


def test_max_caps_hunters_and_cost(make_repo):
    repo = make_repo(FILES)
    result, out = scope(repo, "--max", "2")
    assert result.returncode == 0, result.stderr
    assert [p["dir"] for p in out["parts"]] == ["b2", "b10"]
    assert [p["dir"] for p in out["skipped"]] == ["big", "big", "src", "src/my dir"]
    assert out["hunters"] == 2
    assert out["est_tokens"] == 200_000

    for bad in ("0", "-1"):
        result = run_script("scope", repo, "--max", bad)
        assert result.returncode == 2
        assert "--max" in result.stderr
        assert "Traceback" not in result.stderr


def test_budget_caps_hunters_at_worst_case_cost(make_repo):
    repo = make_repo({**{f"api{i}/server.js": "app.get('/x', h)\n" for i in range(3)},
                      "lib/a.py": "", "lib2/b.py": ""})
    result, out = scope(repo, "--budget", "450000")
    assert result.returncode == 0, result.stderr
    assert [p["dir"] for p in out["parts"]] == ["api0", "api1"]
    assert [p["dir"] for p in out["skipped"]] == ["api2", "lib", "lib2"]
    assert (out["hunters"], out["est_tokens"]) == (2, 200_000)
    assert out["budget"] == {"tokens": 450000, "per_hunter": 200000, "left_out": 3}

    result, out = scope(repo, "--max", "1", "--budget", "450000")
    assert out["hunters"] == 1 and out["budget"]["left_out"] == 0

    result, out = scope(repo, "--live", "--budget", "400000")
    assert result.returncode == 0, result.stderr
    assert out["hunters"] == 2 and out["budget"]["left_out"] == 1

    low = run_script("scope", repo, "--budget", "199999")
    assert low.returncode == 1 and low.stderr.startswith("error:")
    assert "Traceback" not in low.stderr


def test_build_and_docs_tooling_parts_come_last(make_repo):
    # trentm/python-markdown2: --max 1 used to spend the only hunter on setup.py.
    repo = make_repo({
        "setup.py": "", "noxfile.py": "", "jest.config.ts": "", "vite.config.mjs": "",
        "docs/conf.py": "",
        "lib/markdown2.py": "", "src/app.ts": "", "src/setup.py": "",
    })
    _, out = scope(repo)
    assert [p["dir"] for p in out["parts"]] == ["lib", "src", ".", "docs"]
    _, capped = scope(repo, "--max", "1")
    assert capped["parts"][0]["files"] == ["lib/markdown2.py"]
    assert [p["dir"] for p in capped["skipped"]] == ["src", ".", "docs"]


def test_paths_restrict_and_errors_are_clean(make_repo, tmp_path):
    repo = make_repo(FILES)
    result, out = scope(repo, "src", "b2/y.py")
    assert result.returncode == 0, result.stderr
    files = [f for p in out["parts"] for f in p["files"]]
    assert files == ["b2/y.py", "src/cli.py", "src/my dir/naïve.py"]

    result = run_script("scope", repo, "nope")
    assert result.returncode == 1
    assert "nope" in result.stderr
    assert "Traceback" not in result.stderr
    assert len(result.stderr.strip().splitlines()) == 1

    not_git = tmp_path / "plain dir"
    not_git.mkdir()
    result = run_script("scope", not_git)
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert len(result.stderr.strip().splitlines()) == 1


def test_dot_and_absolute_paths_name_the_repo(make_repo):
    repo = make_repo(FILES)
    _, whole = scope(repo)
    for arg in (".", "./"):
        result, out = scope(repo, arg)
        assert result.returncode == 0, result.stderr
        assert out == whole
    result, out = scope(repo, repo / "src")
    assert result.returncode == 0, result.stderr
    assert [f for p in out["parts"] for f in p["files"]] == ["src/cli.py", "src/my dir/naïve.py"]

    result = run_script("scope", repo, repo.parent)
    assert result.returncode == 1 and "Traceback" not in result.stderr


def test_names_outside_the_windows_code_page_print_as_utf8(make_repo):
    repo = make_repo({"src/tệp.py": ""})
    result, out = scope(repo)
    assert result.returncode == 0, result.stderr
    assert [f for p in out["parts"] for f in p["files"]] == ["src/tệp.py"]


def test_skips_names_that_are_not_utf8(make_repo):
    repo = make_repo({"ok.py": ""})
    blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"], cwd=repo, input=b"", capture_output=True
    ).stdout.decode().strip()
    subprocess.run(
        [b"git", b"update-index", b"--add", b"--cacheinfo",
         f"100644,{blob},".encode() + b"bad\xff.py"],
        cwd=repo, check=True, capture_output=True,
    )
    result, out = scope(repo)
    assert result.returncode == 0, result.stderr
    assert [f for p in out["parts"] for f in p["files"]] == ["ok.py"]
    assert "UTF-8" in result.stderr and "Traceback" not in result.stderr


def test_live_keeps_only_parts_serving_http(make_repo):
    repo = make_repo({
        "api/server.js": "const app = express()\napp.get('/orders', list)\n",
        "web/views.py": "@app.route('/orders')\ndef orders():\n    return []\n",
        "svc/main.go": 'func main() {\n\thttp.HandleFunc("/x", h)\n}\n',
        "ctl/OrderController.java": '@GetMapping("/orders")\npublic List<O> all() {}\n',
        "lib/util.py": "def total(items):\n    return sum(items)\n",
    })
    live = run_script("scope", repo, "--live")
    assert live.returncode == 0, live.stderr
    parts = {p["dir"]: p["edge_inputs"] for p in json.loads(live.stdout)["parts"]}
    assert set(parts) == {"api", "web", "svc", "ctl"}
    assert all(inputs[-1] == "live-http" for inputs in parts.values())

    plain = json.loads(run_script("scope", repo).stdout)
    assert "lib" in {p["dir"] for p in plain["parts"]}
    assert all("live-http" not in p["edge_inputs"] for p in plain["parts"])

    shutil.rmtree(repo)
    none = make_repo({"lib/util.py": "def total(items):\n    return sum(items)\n"})
    result = run_script("scope", none, "--live")
    assert result.returncode == 1 and result.stderr.startswith("error:")
    assert "Traceback" not in result.stderr


def test_live_route_markers_across_frameworks(make_repo):
    serving = {
        "chi/main.go": 'r := chi.NewRouter()\nr.Get("/orders", list)\n',
        "fastify/app.js": "fastify.post('/orders', create)\n",
        "nest/orders.controller.ts": "@Controller('orders')\nexport class O {}\n",
        "fastapi/main.py": "@router.get('/orders')\ndef orders():\n    return []\n",
        "django/urls.py": "urlpatterns = [path('orders/', views.list)]\n",
        "laravel/web.php": "<?php\nRoute::get('/orders', [O::class, 'index']);\n",
        "rails/routes.rb": "Rails.application.routes.draw do\n  resources :orders\nend\n",
        "sinatra/app.rb": "get '/orders' do\n  'ok'\nend\n",
        "actix/main.rs": '#[get("/orders")]\nasync fn orders() {}\n',
        "axum/main.rs": 'let app = Router::new().route("/orders", get(list));\n',
        "echo/main.go": 'e := echo.New()\ne.GET("/orders", list)\n',
        "stdlib/server.py": "from http.server import BaseHTTPRequestHandler\n\n\n"
                            "class Handler(BaseHTTPRequestHandler):\n"
                            "    def log_message(self, *a):\n        pass\n\n"
                            "    def do_GET(self):\n        self.send_response(200)\n",
    }
    clients = {
        # A do_ method alone is not a server: the BaseHTTPRequestHandler subclass is the signal.
        "jobs/steps.py": "class Step:\n    def do_GET(self):\n        return 1\n",
        "front/api.js": "const api = axios.create()\n"
                        "export const list = () => api.get('/orders')\n",
        "lib/util.py": "def total(items):\n    return sum(items)\n",
    }
    repo = make_repo({**serving, **clients})
    live = run_script("scope", repo, "--live")
    assert live.returncode == 0, live.stderr
    kept = {p["dir"] for p in json.loads(live.stdout)["parts"]}
    assert kept == {path.split("/")[0] for path in serving}, kept
