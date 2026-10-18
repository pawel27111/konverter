import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from konverter import UPSTREAM_COMMIT
from konverter.backend import BackendError, Controller, MARKER, decode_wsl, redact, source_file


class BackendTests(unittest.TestCase):
    def controller(self, **kwargs):
        return Controller(backend="wsl", **kwargs)

    def test_wsl_decoding(self):
        self.assertEqual(decode_wsl("Ubuntu\nDebian".encode("utf-16-le")), "Ubuntu\nDebian")
        self.assertEqual(decode_wsl("Ubuntu".encode("utf-16")), "Ubuntu")
        self.assertEqual(decode_wsl("ä".encode()), "ä")

    def test_redacts_credentials_and_url_queries(self):
        text = redact("token=a&x=2 Bearer abc https://x/?api_key=foo secret%2Bvalue secret+value", {"HF_TOKEN": "secret+value"})
        for value in ("token=a", "Bearer abc", "api_key=foo", "secret%2Bvalue", "secret+value"):
            self.assertNotIn(value, text)
        self.assertIn("&x=2", text)

    def test_rejects_invalid_distro_and_environment_fields(self):
        for value in ("--help", "a\nb", "\x00"):
            with self.assertRaises(ValueError):
                self.controller(distro=value)
        for secrets in ({"PATH": "x"}, {"HF_TOKEN": "a\nb"}):
            with self.assertRaises(ValueError):
                self.controller(secrets=secrets)

    def test_prefix_has_no_shell(self):
        with patch("konverter.backend.shutil.which", return_value="wsl.exe"):
            self.assertEqual(self.controller(distro="Ubuntu-24.04").prefix(), ["wsl.exe", "--distribution", "Ubuntu-24.04", "--exec"])

    def test_missing_wsl_gives_actionable_error(self):
        with patch("konverter.backend.shutil.which", return_value=None):
            with self.assertRaisesRegex(BackendError, "Setup-Windows"):
                self.controller().prefix()

    def test_path_mapping_is_argument_safe_and_cached(self):
        controller = self.controller()
        value = str(Path("A & Unicode ä $(unsafe)").resolve())
        with patch.object(controller, "small", return_value="/mnt/c/translated") as small:
            self.assertEqual(controller.map_path(value), "/mnt/c/translated")
            self.assertEqual(controller.map_path(value), "/mnt/c/translated")
            small.assert_called_once_with(["wslpath", "-a", "-u", value])

    def test_ambiguous_path_mapping_is_refused(self):
        controller = self.controller()
        for value in ("relative", "/a\n/b", "/a\x00b"):
            with patch.object(controller, "small", return_value=value):
                with self.assertRaises(BackendError):
                    controller.map_path("x")

    def test_runtime_marker_and_version_are_checked(self):
        c = self.controller(emit=lambda line: None)
        runtime = dict(engine="/engine", python="/python", work_root="/work", upstream_commit=UPSTREAM_COMMIT)
        with patch.object(c, "small", return_value="6.6.0-microsoft-standard-WSL2"), patch.object(c, "stream", return_value=(0, [MARKER + json.dumps(runtime)])):
            self.assertEqual(c.prepare(), runtime)
        for lines in ([], [MARKER + "{}"], [MARKER + json.dumps(runtime)] * 2):
            c = self.controller(emit=lambda line: None)
            with patch.object(c, "small", return_value="6.6.0-microsoft-standard-WSL2"), patch.object(c, "stream", return_value=(0, lines)):
                with self.assertRaises(BackendError):
                    c.prepare()

    def test_stream_uses_stdin_and_redacts_output(self):
        output = []
        controller = self.controller(emit=output.append, secrets={"HF_TOKEN": "private-token"})
        command = [sys.executable, "-u", "-c", "import sys; print(sys.stdin.read()); print('private-token')"]
        with patch.object(controller, "prefix", return_value=[]):
            code, _ = controller.stream(command, b"hello from stdin")
        self.assertEqual(code, 0)
        self.assertEqual(output, ["hello from stdin", "[REDACTED]"])
        self.assertIsNone(controller.process)

    def test_cancel_before_start_does_not_launch_conversion(self):
        from konverter.options import parser
        c = self.controller(emit=lambda line: None)
        c.runtime = {"python": "/python", "engine": "/engine", "work_root": "/work"}
        c.cancel()
        args = parser().parse_args(["convert", "owner/model", "--target", "ios"])
        with patch.object(c, "stream") as stream:
            self.assertEqual(c.execute(args), 130)
            stream.assert_not_called()

    def test_runtime_sources_are_packaged(self):
        self.assertIn("def main", source_file("bootstrap.py"))
        self.assertIn("def main", source_file("supervisor.py"))
        self.assertTrue(Path(__file__).resolve().parents[1].joinpath("konverter/Setup-Windows.ps1").is_file())

    def test_cli_redirected_to_a_legacy_code_page_preserves_unicode(self):
        result = subprocess.run([sys.executable, "-m", "konverter", "--help"],
            env={**os.environ, "PYTHONIOENCODING": "cp1252"}, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Windows → Apple", result.stdout.decode("utf-8"))


@unittest.skipUnless(sys.platform == "linux", "Process group semantics require Linux/WSL")
class SupervisorIntegration(unittest.TestCase):
    def test_cancel_stops_compiler_descendant_and_cleans_control_file(self):
        import time
        import uuid
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "coreai_diffusion_converter"
            package.mkdir()
            (package / "__init__.py").write_text("")
            (package / "cli.py").write_text("import subprocess,sys,time\nfrom pathlib import Path\np=subprocess.Popen([sys.executable,'-c','import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)'])\nPath('child.pid').write_text(str(p.pid))\nprint('ready',flush=True)\ntime.sleep(60)\n")
            job_id = uuid.uuid4().hex
            env = {**os.environ, "HOME": tmp, "PYTHONPATH": tmp}
            payload = {"job_id": job_id, "args": ["convert"], "cwd": tmp, "secrets": {}}
            process = subprocess.Popen([sys.executable, "-u", "-c", source_file("supervisor.py")],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
            try:
                process.stdin.write(json.dumps(payload).encode())
                process.stdin.close()
                process.stdin = None
                deadline = time.monotonic() + 10
                while not (root / "child.pid").exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue((root / "child.pid").exists(), "Worker never started")
                child = int((root / "child.pid").read_text())
                cancel = root / ".cache/konverter/control" / (job_id + ".cancel")
                cancel.touch()
                output, _ = process.communicate(timeout=12)
                self.assertEqual(process.returncode, 130, output.decode())
                self.assertFalse(cancel.exists())
                stat = Path(f"/proc/{child}/stat")
                if stat.exists():
                    self.assertEqual(stat.read_text().split()[2], "Z", "Compiler descendant survived cancellation")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def test_malformed_job_cannot_execute_arbitrary_action(self):
        result = subprocess.run([sys.executable, "-c", source_file("supervisor.py")],
            input=json.dumps({"job_id": "a" * 32, "args": ["shell", "touch /tmp/forbidden"]}).encode(),
            capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 4)
        self.assertIn(b"Invalid engine action", result.stderr)


if __name__ == "__main__":
    unittest.main()
