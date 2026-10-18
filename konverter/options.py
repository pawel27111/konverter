"""Public option contract, matching AcmeUp 0.2.0; no ML imports on Windows."""
from __future__ import annotations

import argparse
import math
import ntpath
from pathlib import Path

from . import __version__

VALUE_OPTIONS = ("size", "precision", "name", "license_name", "steps", "guidance", "revision",
                 "clip_skip", "prediction_type")
PATH_OPTIONS = ("license_file", "cache_dir", "output_dir", "work_dir")
SOURCE_OPTIONS = ("base", "vae")
FLAGS = ("allow_missing_license", "allow_unverified_download", "keep_work", "overwrite", "dry_run", "verbose")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="konverter", description="Windows → Apple Core AI, lokal mit WSL2")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--backend", choices=("auto", "wsl", "local"), default="auto")
    p.add_argument("--distro", help="WSL distribution; omitted uses the WSL default")
    p.add_argument("--engine-dir", help="Use an existing pinned engine checkout (developer option)")
    p.add_argument("--no-setup", action="store_true", help="Do not install missing engine dependencies")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("gui")
    sub.add_parser("doctor")
    sub.add_parser("setup")
    c = sub.add_parser("convert")
    c.add_argument("source", help="Hugging Face ID, Civitai reference, local .safetensors or diffusers folder")
    c.add_argument("--target", required=True, choices=("ios", "macos"))
    c.add_argument("--size", type=int, choices=(512, 768, 1024))
    c.add_argument("--precision", choices=("fp16", "4bit"))
    c.add_argument("--name")
    c.add_argument("--license-file", "--licence-file", dest="license_file")
    c.add_argument("--license-name", "--licence-name", dest="license_name")
    c.add_argument("--allow-missing-license", "--allow-missing-licence", dest="allow_missing_license", action="store_true")
    c.add_argument("--steps", type=int)
    c.add_argument("--guidance", type=float)
    c.add_argument("--revision")
    c.add_argument("--base")
    c.add_argument("--vae")
    c.add_argument("--lora", action="append", default=[])
    c.add_argument("--civitai-token", help="Prefer CIVITAI_API_TOKEN in the environment")
    c.add_argument("--cache-dir")
    c.add_argument("--allow-unverified-download", action="store_true")
    c.add_argument("--clip-skip", type=int, default=1, choices=(1, 2, 3, 4))
    c.add_argument("--prediction-type", choices=("epsilon", "v_prediction"))
    c.add_argument("--output-dir", default="outputs")
    c.add_argument("--work-dir")
    c.add_argument("--keep-work", action="store_true")
    c.add_argument("--overwrite", action="store_true")
    c.add_argument("--dry-run", action="store_true")
    c.add_argument("-v", "--verbose", action="store_true")
    for command in ("inspect", "validate"):
        sub.add_parser(command).add_argument("pack")
    return p


def check_options(args):
    if args.command != "convert":
        return
    if args.steps is not None and not 1 <= args.steps <= 100:
        raise ValueError("Schritte müssen zwischen 1 und 100 liegen.")
    if args.guidance is not None and (not math.isfinite(args.guidance) or not 0 <= args.guidance <= 30):
        raise ValueError("Guidance muss zwischen 0 und 30 liegen.")
    if len(args.lora) > 8:
        raise ValueError("Maximal acht LoRAs pro Export.")
    if args.name is not None and not 1 <= len(args.name.strip()) <= 80:
        raise ValueError("Modellname muss 1 bis 80 Zeichen enthalten.")
    if not args.source.strip() or "\x00" in args.source:
        raise ValueError("Eine Modellquelle ist erforderlich.")


def is_local(value: str) -> bool:
    return (bool(ntpath.splitdrive(value)[0]) or value.startswith(("/", "./", "../", ".\\", "..\\", "~"))
            or Path(value).expanduser().exists())


def split_lora(value: str) -> tuple[str, str]:
    # A drive colon is never a scale separator. Existing paths win over suffix guessing.
    if Path(value).expanduser().is_file():
        return value, ""
    base, separator, scale = value.rpartition(":")
    if separator and base:
        try:
            float(scale)
        except ValueError:
            pass
        else:
            return base, ":" + scale
    return value, ""


def engine_args(args, map_path, work_dir: str) -> list[str]:
    check_options(args)
    if args.command in ("validate", "inspect"):
        return [args.command, map_path(args.pack)]
    if args.command != "convert":
        raise ValueError("No engine command for this action.")
    source = map_path(args.source) if is_local(args.source) else args.source
    result = ["convert", source, "--target", args.target]
    for key in VALUE_OPTIONS:
        value = getattr(args, key)
        if value is not None:
            result.extend(["--" + key.replace("_", "-"), str(value)])
    for key in PATH_OPTIONS:
        value = getattr(args, key)
        if value is not None:
            result.extend(["--" + key.replace("_", "-"), map_path(value)])
    if args.work_dir is None:
        result.extend(["--work-dir", work_dir])
    for key in SOURCE_OPTIONS:
        value = getattr(args, key)
        if value:
            result.extend(["--" + key, map_path(value) if is_local(value) else value])
    for value in args.lora:
        base, scale = split_lora(value)
        result.extend(["--lora", (map_path(base) if is_local(base) else base) + scale])
    for key in FLAGS:
        if getattr(args, key):
            result.append("--" + key.replace("_", "-"))
    # Credentials travel over stdin/environment, never in the Linux process arguments.
    return result
