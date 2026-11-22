import os
import shlex
import subprocess
import sys

import pytest
from test_isolate import BASH, SCRIPTS

RAW = (
    "import ctypes, json, nt\n"
    "k = ctypes.windll.kernel32\n"
    "k.GetEnvironmentStringsW.restype = ctypes.c_void_p\n"
    "p = k.GetEnvironmentStringsW(); names = []; off = 0\n"
    "while True:\n"
    "    s = ctypes.wstring_at(p + off * 2)\n"
    "    if not s: break\n"
    "    names.append(s); off += len(s) + 1\n"
    "print(json.dumps({'raw': [n for n in names if n[:1] in '=!' or 'proj' in n],\n"
    "  'nt': {a: b for a, b in nt.environ.items() if a[:1] in '=!' or a == '' or 'proj' in b}}))\n"
)


@pytest.mark.skipif(os.name != "nt", reason="diagnostic")
def test_diag_bang_drive_names(tmp_path):
    real = tmp_path / "real"
    env = {"PATH": os.environ["PATH"], "HOME": str(real), "SYSTEMROOT": os.environ["SYSTEMROOT"],
           "!C:": str(real / "proj")}
    iso = shlex.join([sys.executable, "-I", str(SCRIPTS / "isolate.py"), str(tmp_path / "s")])
    child = shlex.join([sys.executable, "-I", "-c", RAW])
    out = []
    for script in (f"compgen -e | grep -n '[!=]' ; {child}",
                   f'ISO="$({iso})"; echo "rc=$?"; printf "%s\\n" "$ISO" | grep -n "C:" ; '
                   f'eval "$ISO"; compgen -e | grep -n "[!=]"; {child}'):
        r = subprocess.run([BASH, "-c", script], env=env, capture_output=True, text=True)
        out.append(f"--- rc={r.returncode}\nOUT:{r.stdout}\nERR:{r.stderr}")
    pytest.fail("\n".join(out))
