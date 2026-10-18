"""Standalone Linux worker: stdin JSON → upstream CLI, with process-group cancellation."""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path


def main():
    raw = sys.stdin.buffer.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("Job too large.")
    job = json.loads(raw)
    job_id = job["job_id"]
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise ValueError("Invalid job ID.")
    args = job["args"]
    if not isinstance(args, list) or not args or args[0] not in ("convert", "validate", "inspect"):
        raise ValueError("Invalid engine action.")
    if not all(isinstance(a, str) and "\x00" not in a for a in args):
        raise ValueError("Invalid engine arguments.")
    env = os.environ.copy()
    for key, value in job.get("secrets", {}).items():
        if key not in ("HF_TOKEN", "CIVITAI_API_TOKEN") or not isinstance(value, str):
            raise ValueError("Invalid credential environment field.")
        if value:
            env[key] = value
    env["PYTHONUNBUFFERED"] = "1"
    controls = Path.home() / ".cache" / "konverter" / "control"
    controls.mkdir(parents=True, exist_ok=True)
    cancel = controls / (job_id + ".cancel")
    if cancel.exists():
        cancel.unlink()
        print("Auftrag vor dem Start abgebrochen.", flush=True)
        return 130
    process = subprocess.Popen([sys.executable, "-m", "coreai_diffusion_converter.cli", *args],
                               stdin=subprocess.DEVNULL, env=env, cwd=job["cwd"], start_new_session=True)
    try:
        while process.poll() is None:
            if cancel.exists():
                print("Abbruch angefordert; stoppe Export-Prozessgruppe …", flush=True)
                stop(process)
                return 130
            time.sleep(0.2)
        return process.returncode
    finally:
        cancel.unlink(missing_ok=True)
        if process.poll() is None:
            stop(process)


def stop(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    # The parent may have exited while a compiler grandchild is still alive.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("Worker-Fehler: " + str(exc), file=sys.stderr)
        raise SystemExit(4)
