# Verification record

## Reproduced during implementation (2026-10-18)

- Exact upstream commit: `873560b6f9c9865d0aee0cc7ddc0b034045cd051`.
- Real upstream lockfile installed on Linux x86-64, Python 3.11.17, PyTorch 2.9.0, coreai-core 1.0.0b2, coreai-torch 0.4.2, coreai-opt 0.2.1.
- Upstream offline tests: **402 passed, 1 skipped, 11 deselected**. Live/network/model download tests are excluded by the upstream default test configuration.
- Native compiler probe: an actual Torch exported program was converted with `TorchConverter` and saved as `.aimodel`, containing `main.mlirb`, `main.hash` and `metadata.json`.
- Full local adapter path: generated a small random-weight SD1-compatible diffusers pipeline with `scripts/compiler_smoke.py`, exported it through `python -m konverter --engine-dir ... convert ... --target ios`, produced real TextEncoder, UNet and VAEDecoder assets, tokenizer and manifest, and passed the upstream `.caipack` validator. No fake converter/program objects were used in this export.

## Continuous verification

The [GitHub workflow](https://github.com/pawel27111/konverter/actions/workflows/build.yml) is the source of truth for the latest commit's test/build results:

- Unit and process integration tests on Windows and Linux.
- Exact upstream CLI flag contract check.
- Native Windows Tk UI startup and PowerShell script syntax.
- Build both Windows x64 executables and start the frozen GUI/CLI.
- Fresh automatic Linux engine installation from the pinned dependency lock.
- Real synthetic diffusion export and independent package validation.
- Actual frozen Windows CLI → newly installed WSL2 → real synthetic export → package validation, including spaces, Unicode and `&` in a Windows source path.

## Scope of the evidence

The synthetic export verifies the compiler and packaging path; its small random weights do not establish real-model image quality. Family support is inherited from the original converter and is not a claim that every family has been converted here. Structural package validation does not execute the model on Apple hardware.

UAC/reboot handling on a clean consumer Windows installation, full-size production checkpoints on Windows 10/11, and inference on supported Apple devices still require their corresponding hardware acceptance checks. The automated Windows/WSL2 integration test runs on GitHub's Windows Server 2025 runner.

## Why local WSL2 is possible

The original README describes macOS setup, but its locked `coreai-core==1.0.0b2` dependency publishes CPython 3.11 Linux x86-64 wheels as well. This was verified both from [PyPI package metadata](https://pypi.org/pypi/coreai-core/1.0.0b2/json) and by actually loading the native compiler and exporting models. Captured filenames and hashes are in `compiler-wheels.json`. Windows uses that Linux compiler in WSL2; there is no claim of a native Windows wheel.
