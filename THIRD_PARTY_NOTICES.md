# Third-party notices

Konverter's Windows UI and WSL adapter are original MIT-licensed code. The conversion engine is installed separately; its code and lockfile are not relicensed by this project.

| Component | Origin / license |
| --- | --- |
| coreai-diffusion-converter 0.2.0 | Copyright 2026 AcmeUp Inc.; [Apache-2.0](https://github.com/acmeup/coreai-diffusion-converter/blob/873560b6f9c9865d0aee0cc7ddc0b034045cd051/LICENSE). Pinned commit `873560b6f9c9865d0aee0cc7ddc0b034045cd051`. |
| coreai-models | Apple Inc.; [BSD-3-Clause](https://github.com/apple/coreai-models/blob/7359dbcf6c3babb4fbfadfd015ffcc1cb6d87420/LICENSE), pinned through the engine's lockfile. |
| coreai-core / coreai-torch / coreai-opt | Apple Inc.; package-specific licenses included with the separately installed wheels. |
| uv | Astral; [MIT or Apache-2.0](https://github.com/astral-sh/uv). |
| Python | Python Software Foundation License; bundled in the Windows executable. |
| Tcl/Tk | Tcl/Tk license; bundled for the native desktop UI. |
| PyInstaller bootloader | [GPL-2.0-or-later with an exception permitting distribution of bundled applications](https://pyinstaller.org/en/stable/license.html). |

The Windows build includes available Python, Tcl/Tk and PyInstaller license texts under `third-party-licenses/`. Model weights, model licenses, hub credentials and Apple runtimes are not part of the Windows download. Each model retains its own license. The generated random-weight compiler test fixture is a test asset and is not intended for image generation.
