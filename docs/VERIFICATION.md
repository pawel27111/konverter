# Verification record

## Reproduced during implementation (2026-10-18)

- Exact upstream commit: `873560b6f9c9865d0aee0cc7ddc0b034045cd051`.
- Real upstream lockfile installed on Linux x86-64, Python 3.11.17, PyTorch 2.9.0, coreai-core 1.0.0b2, coreai-torch 0.4.2, coreai-opt 0.2.1.
- Upstream offline tests: **402 passed, 1 skipped, 11 deselected**. Live/network/model download tests are excluded by the upstream default test configuration.
- Native compiler probe: an actual Torch exported program was converted with `TorchConverter` and saved as `.aimodel`, containing `main.mlirb`, `main.hash` and `metadata.json`.
- Full local adapter path: generated a small random-weight SD1-compatible diffusers pipeline with `scripts/compiler_smoke.py`, exported it through `python -m konverter --engine-dir ... convert ... --target ios`, produced real TextEncoder, UNet and VAEDecoder assets, tokenizer and manifest, and passed the upstream `.caipack` validator. No fake converter/program objects were used in this export.
- Real INT4 export of the same fixture for the macOS target also succeeded. The native quantizer reported applied INT4 weight quantization, and the resulting package passed validation.

## Windows acceptance result

**All five jobs passed** in [workflow run 39153235201](https://github.com/pawel27111/konverter/actions/runs/39153235201), software commit `407d5e839410e4b0d87516dbb9083a07241a127d`:

- Windows and Linux unit/integration tests, including a regression for redirected legacy-code-page output.
- Native desktop startup at both 980×800 and 780×660, form-to-command mapping, and PowerShell installer syntax.
- Frozen Windows x64 GUI and CLI built and started successfully.
- Fresh Linux compiler setup, real synthetic SD1 export, and independent package validation.
- **Fresh WSL2/Ubuntu setup on Windows Server 2025, compiler installation through the actual Windows EXE, real export from `Modell ä & test` to a Windows output folder, and independent validation through that EXE.**

The downloadable `Konverter-Windows-x64.zip` contains both executables, the setup script, instructions and available bundled dependency licenses. SHA-256 of the inner application ZIP from that run:

```text
5d2bf9f9aaf256d34653411d38c3542a02d7fb4fc8d9ac68690651277198047a
```

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
