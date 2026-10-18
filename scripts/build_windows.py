"""Run on Windows with Python 3.11+ and PyInstaller installed."""
import shutil
import subprocess
import sys
import importlib.metadata
from pathlib import Path

root = Path(__file__).resolve().parents[1]
if sys.platform != "win32":
    raise SystemExit("Windows executables must be built on Windows.")
for name, entry, windowed in (("Konverter", "gui_entry.py", True), ("konverter-cli", "cli_entry.py", False)):
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--name", name,
            "--paths", str(root), "--collect-data", "konverter"]
    for filename in ("bootstrap.py", "supervisor.py", "Setup-Windows.ps1"):
        args += ["--add-data", f"{root / 'konverter' / filename};konverter"]
    if windowed:
        args.append("--windowed")
    subprocess.run([*args, str(root / "scripts" / entry)], cwd=root, check=True)
for filename in ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md"):
    shutil.copy2(root / filename, root / "dist" / filename)
(root / "dist" / "setup").mkdir(exist_ok=True)
shutil.copy2(root / "konverter" / "Setup-Windows.ps1", root / "dist" / "setup" / "Setup-Windows.ps1")
licenses = root / "dist" / "third-party-licenses"
licenses.mkdir(exist_ok=True)
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.is_file():
    shutil.copy2(python_license, licenses / "Python-LICENSE.txt")
distribution = importlib.metadata.distribution("pyinstaller")
for file in distribution.files or []:
    if "licenses" in file.parts and Path(file).suffix.lower() in ("", ".txt", ".rst", ".md"):
        source = Path(distribution.locate_file(file))
        if source.is_file():
            shutil.copy2(source, licenses / ("pyinstaller-" + source.name))
for folder in (Path(sys.base_prefix) / "tcl").glob("*"):
    for name in ("license.terms", "LICENSE", "license.txt"):
        source = folder / name
        if source.is_file():
            shutil.copy2(source, licenses / (folder.name + "-" + name))
shutil.make_archive(str(root / "Konverter-Windows-x64"), "zip", root / "dist")
