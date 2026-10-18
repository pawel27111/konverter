"""Standalone Linux setup script, sent to WSL's python3 over stdin.

No imports from the Windows frontend: this file must run before that package exists in WSL.
"""
from __future__ import annotations

import fcntl
import hashlib
import io
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

COMMIT = "873560b6f9c9865d0aee0cc7ddc0b034045cd051"
URL = "https://github.com/acmeup/coreai-diffusion-converter.git"
UV_URL = "https://files.pythonhosted.org/packages/e5/83/85a6c63c24905af4924fddb11a499b934913f59a134248367a1ef1a4716f/uv-0.12.23-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
UV_SHA256 = "565c6e2874dbeae86c02f3dea97255e878fec672659a73d4930c6b93fcab2fff"
MARKER = "__KONVERTER_RUNTIME__"


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    # arguments: setup|check, optional developer-owned engine checkout
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    override = sys.argv[2] if len(sys.argv) > 2 else ""
    if mode not in ("setup", "check"):
        raise ValueError("Invalid setup mode")
    if platform.system() != "Linux" or platform.machine().lower() not in ("x86_64", "amd64"):
        raise RuntimeError("Backend requires x86-64 Linux (on Windows: WSL2).")
    libc, version = platform.libc_ver()
    if libc != "glibc" or tuple(map(int, version.split(".")[:2])) < (2, 34):
        raise RuntimeError("glibc >=2.34 required; use Ubuntu 22.04 or 24.04.")
    root = Path.home() / ".local" / "share" / "konverter"
    engine = Path(override).expanduser().resolve() if override else root / ("engine-" + COMMIT[:12])
    python = engine / ".venv" / "bin" / "python"
    if not shutil.which("git"):
        raise RuntimeError("git is missing in WSL. Run Setup-Windows.ps1 to install Linux prerequisites.")
    if not python.is_file() and (mode == "check" or override):
        raise RuntimeError("Engine is not installed. Run konverter setup / Einrichten first.")
    root.mkdir(parents=True, exist_ok=True)
    with (root / "setup.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another Konverter setup is already running.") from None
        if mode == "setup" and not override:
            if not python.is_file() and shutil.disk_usage(root).free < 14 * 1024**3:
                raise RuntimeError("At least 14 GiB free space is needed for the engine installation.")
            tools = root / "tools"
            tools.mkdir(exist_ok=True)
            uv = tools / "uv-0.12.23"
            if not uv.is_file():
                print("Lade geprüftes uv-Werkzeug …", flush=True)
                with urllib.request.urlopen(UV_URL, timeout=120) as response:
                    data = response.read(32 * 1024**2 + 1)
                if hashlib.sha256(data).hexdigest() != UV_SHA256:
                    raise RuntimeError("uv download checksum mismatch.")
                with zipfile.ZipFile(io.BytesIO(data)) as wheel:
                    matches = [n for n in wheel.namelist() if n.endswith(".data/scripts/uv")]
                    if len(matches) != 1:
                        raise RuntimeError("Unexpected uv wheel layout.")
                    binary = wheel.read(matches[0])
                temporary = tools / "uv.partial"
                temporary.write_bytes(binary)
                temporary.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
                temporary.replace(uv)
            if not engine.exists():
                print("Installiere festgelegten Converter-Stand …", flush=True)
                staging = root / ("engine-" + COMMIT[:12] + ".partial")
                if staging.exists():
                    shutil.rmtree(staging)
                try:
                    run(["git", "clone", "--no-checkout", URL, str(staging)])
                    run(["git", "-C", str(staging), "checkout", "--detach", COMMIT])
                    staging.replace(engine)
                finally:
                    if staging.exists():
                        shutil.rmtree(staging)
            verify_checkout(engine)
            print("Installiere Python 3.11 und Compiler-Abhängigkeiten; erster Download mehrere GB …", flush=True)
            run([str(uv), "sync", "--project", str(engine), "--frozen", "--no-dev", "--python", "3.11"])
        verify_checkout(engine)
        # Importing authoring is a real native-library load, not just a wheel metadata test.
        run([str(python), "-c", "import coreai.authoring; import coreai_torch; import coreai_models.diffusion.pipeline; print('Compiler-Imports: OK')"])
        print(MARKER + json.dumps({"engine": str(engine), "python": str(python),
                                  "upstream_commit": COMMIT, "platform": platform.platform(),
                                  "work_root": str(root / "work")}), flush=True)


def verify_checkout(engine):
    head = run(["git", "-C", str(engine), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != COMMIT:
        raise RuntimeError("Unexpected engine version; existing checkout was left unchanged.")
    run(["git", "-C", str(engine), "diff", "--quiet", "HEAD", "--"])


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print("Einrichtung fehlgeschlagen: " + str(exc), file=sys.stderr)
        raise SystemExit(4)
