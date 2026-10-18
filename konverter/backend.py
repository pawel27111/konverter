"""Local Linux/WSL2 adapter. All user values are subprocess arguments or stdin data."""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import urllib.parse
import uuid
from pathlib import Path

from . import UPSTREAM_COMMIT
from .options import engine_args

MARKER = "__KONVERTER_RUNTIME__"


class BackendError(RuntimeError):
    pass


def decode_wsl(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16").lstrip("\ufeff")
    return data.decode("utf-16-le" if b"\x00" in data else "utf-8", errors="replace")


def redact(text: str, secrets: dict) -> str:
    for value in secrets.values():
        if value:
            text = text.replace(value, "[REDACTED]").replace(urllib.parse.quote(value, safe=""), "[REDACTED]")
    text = re.sub(r"(?i)((?:token|api_key|access_token|authorization)=)[^\s&]+", r"\1[REDACTED]", text)
    return re.sub(r"(?i)(Bearer\s+)\S+", r"\1[REDACTED]", text)


def source_file(name: str) -> str:
    # Also included as data files in the frozen Windows build.
    return Path(__file__).with_name(name).read_text(encoding="utf-8")


def process_options() -> dict:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}


class Controller:
    def __init__(self, *, backend="auto", distro=None, engine_dir=None, emit=print, secrets=None):
        self.backend = ("wsl" if platform.system() == "Windows" else "local") if backend == "auto" else backend
        if self.backend not in ("wsl", "local"):
            raise ValueError("Invalid backend.")
        if self.backend == "local" and platform.system() != "Linux":
            raise BackendError("Direkter Export benötigt Linux x86-64. Unter Windows WSL2 verwenden.")
        if distro and (not isinstance(distro, str) or distro.startswith("-") or any(ord(c) < 32 for c in distro)):
            raise ValueError("Ungültiger WSL-Verteilungsname.")
        self.distro, self.engine_dir, self.emit = distro, engine_dir, emit
        self.secrets = {key: value for key, value in (secrets or {}).items() if value}
        for key, value in self.secrets.items():
            if key not in ("HF_TOKEN", "CIVITAI_API_TOKEN") or any(ord(c) < 32 for c in value):
                raise ValueError("Ungültiges Zugangstoken.")
        self.runtime = None
        self.process = None
        self.job_id = uuid.uuid4().hex
        self.stage = "idle"
        self._cancel = threading.Event()
        self._paths = {}

    def prefix(self) -> list[str]:
        if self.backend == "local":
            return []
        if not shutil.which("wsl.exe"):
            raise BackendError("WSL ist nicht installiert. Setup-Windows.ps1 ausführen.")
        return ["wsl.exe", *(["--distribution", self.distro] if self.distro else []), "--exec"]

    def small(self, args: list[str], *, timeout=30) -> str:
        result = subprocess.run([*self.prefix(), *args], capture_output=True, timeout=timeout,
                                check=False, **process_options())
        if result.returncode:
            message = redact(decode_wsl(result.stderr or result.stdout), self.secrets).strip()
            raise BackendError(message or f"Backend-Aufruf fehlgeschlagen ({result.returncode}).")
        return decode_wsl(result.stdout).strip()

    def map_path(self, value: str) -> str:
        value = str(Path(value).expanduser().resolve())
        if self.backend == "local":
            return value
        if value not in self._paths:
            mapped = self.small(["wslpath", "-a", "-u", value])
            if not mapped.startswith("/") or any(c in mapped for c in "\r\n\x00"):
                raise BackendError("Windows-Pfad konnte nicht eindeutig nach WSL übersetzt werden.")
            self._paths[value] = mapped
        return self._paths[value]

    def stream(self, command: list[str], data: bytes, *, collect=False) -> tuple[int, list[str]]:
        result_lines = []
        with subprocess.Popen([*self.prefix(), *command], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, **process_options()) as process:
            self.process = process
            try:
                process.stdin.write(data)
                process.stdin.close()
                interrupted = False
                while True:
                    try:
                        raw = process.stdout.readline()
                    except KeyboardInterrupt:
                        interrupted = True
                        self.cancel()
                        continue
                    if not raw:
                        break
                    line = redact(raw.decode("utf-8", errors="replace").rstrip("\r\n"), self.secrets)
                    if line.startswith(MARKER):
                        result_lines.append(line)
                    else:
                        self.emit(line)
                    if collect and not line.startswith(MARKER):
                        result_lines.append(line)
                code = process.wait()
                if interrupted:
                    raise KeyboardInterrupt
                return code, result_lines
            finally:
                self.process = None

    def prepare(self, *, install=True) -> dict:
        if self.runtime is not None:
            return self.runtime
        self.stage = "setup" if install else "check"
        self.emit("Prüfe lokales WSL2/Linux-Backend …")
        # wsl --exec does not invoke a shell; a normal Linux kernel means WSL1 is unsuitable.
        if self.backend == "wsl":
            kernel = self.small(["uname", "-r"])
            if "microsoft-standard" not in kernel.lower() and "wsl2" not in kernel.lower():
                raise BackendError("Die ausgewählte Verteilung läuft nicht nachweislich mit WSL2.")
        override = self.map_path(self.engine_dir) if self.engine_dir else ""
        code, lines = self.stream(["python3", "-", "setup" if install else "check", override],
                                  source_file("bootstrap.py").encode("utf-8"))
        if code:
            raise BackendError(f"Backend-Einrichtung/-Prüfung fehlgeschlagen (Exit {code}); Details im Protokoll.")
        markers = [line[len(MARKER):] for line in lines if line.startswith(MARKER)]
        if len(markers) != 1:
            raise BackendError("Backend meldet keinen eindeutigen Installationsstand.")
        runtime = json.loads(markers[0])
        if runtime.get("upstream_commit") != UPSTREAM_COMMIT:
            raise BackendError("Backend-Version stimmt nicht mit dem Windows-Programm überein.")
        for key in ("python", "engine", "work_root"):
            if not isinstance(runtime.get(key), str) or not runtime[key].startswith("/"):
                raise BackendError("Ungültiger Backend-Pfad.")
        self.runtime, self.stage = runtime, "ready"
        self.emit("Lokaler Compiler bereit. Kein Mac und kein Modell-Cloudserver erforderlich.")
        return runtime

    def execute(self, args, *, install=True) -> int:
        runtime = self.prepare(install=install)
        if self._cancel.is_set():
            self.emit("Auftrag vor dem Export abgebrochen.")
            return 130
        mapped = engine_args(args, self.map_path, runtime["work_root"] + "/" + self.job_id)
        if getattr(args, "civitai_token", None):
            self.secrets["CIVITAI_API_TOKEN"] = args.civitai_token
        payload = {"job_id": self.job_id, "args": mapped, "cwd": self.map_path(str(Path.cwd())),
                   "secrets": self.secrets}
        self.stage = "running"
        try:
            code, _ = self.stream([runtime["python"], "-u", "-c", source_file("supervisor.py")],
                                  json.dumps(payload).encode("utf-8"))
        finally:
            self.stage = "finished"
        if code == 0:
            self.emit("Auftrag erfolgreich abgeschlossen.")
        elif code == 130:
            self.emit("Auftrag abgebrochen; unvollständige Arbeitsdaten bleiben für Diagnose erhalten.")
        else:
            self.emit(f"Auftrag fehlgeschlagen (Exit {code}).")
        return code

    def cancel(self):
        self._cancel.set()
        if self.stage != "running":
            self.emit("Export wird nicht gestartet. Eine bereits laufende Einrichtung wird noch beendet.")
            return
        code = ("from pathlib import Path; import re,sys; j=sys.argv[1]; "
                "assert re.fullmatch(r'[0-9a-f]{32}',j); "
                "p=Path.home()/'.cache'/'konverter'/'control'; p.mkdir(parents=True,exist_ok=True); "
                "(p/(j+'.cancel')).touch()")
        self.small(["python3", "-c", code, self.job_id])


def list_distros() -> list[str]:
    if not shutil.which("wsl.exe"):
        return []
    result = subprocess.run(["wsl.exe", "--list", "--quiet"], capture_output=True, timeout=15,
                            check=False, **process_options())
    if result.returncode:
        return []
    return [line.strip() for line in decode_wsl(result.stdout).splitlines() if line.strip()]
