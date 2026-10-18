from __future__ import annotations

import json
import os
import platform
import subprocess
import sys

from . import UPSTREAM_COMMIT, __version__
from .backend import BackendError, Controller
from .options import check_options, parser


def main(argv=None):
    # Frozen Windows CLIs can otherwise use a legacy code page when logs are redirected.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = parser().parse_args(argv)
    if args.command == "gui":
        from .gui import main as gui_main
        return gui_main()
    controller = None
    try:
        check_options(args)
        secrets = {key: os.environ.get(key, "") for key in ("HF_TOKEN", "CIVITAI_API_TOKEN")}
        if getattr(args, "civitai_token", None):
            secrets["CIVITAI_API_TOKEN"] = args.civitai_token
        controller = Controller(backend=args.backend, distro=args.distro, engine_dir=args.engine_dir,
                                secrets=secrets, emit=lambda line: print(line, flush=True))
        if args.command == "doctor":
            print(json.dumps({"version": __version__, "host": platform.platform(), "backend": controller.backend,
                              "native_win32_compiler": False, "requires_mac": False,
                              "upstream_commit": UPSTREAM_COMMIT}, indent=2))
            controller.prepare(install=False)
            return 0
        if args.command == "setup":
            controller.prepare(install=True)
            return 0
        return controller.execute(args, install=not args.no_setup)
    except (OSError, ValueError, BackendError, subprocess.SubprocessError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        if controller:
            try:
                controller.cancel()
            except (OSError, BackendError, subprocess.SubprocessError):
                pass
        return 130
