import argparse
import os
import unittest
from pathlib import Path

from konverter.options import check_options, engine_args, is_local, parser, split_lora


class OptionContract(unittest.TestCase):
    def parse(self, *options):
        return parser().parse_args(["convert", "owner/model", "--target", "ios", *options])

    def test_remote_sources_are_preserved(self):
        for value in ("owner/model", "civitai:123@456", "https://civitai.com/models/123?modelVersionId=456"):
            with self.subTest(value=value):
                args = self.parse()
                args.source = value
                result = engine_args(args, lambda p: "/mapped/" + p, "/tmp/work")
                self.assertEqual(result[1], value)

    def test_windows_paths_and_weighted_loras_are_mapped_without_a_shell(self):
        args = self.parse("--base", r"D:\Models & stuff\base", "--vae", "owner/vae",
                          "--lora", r"C:\LoRAs\a $(touch bad).safetensors:0.7",
                          "--lora", "civitai:42@43:1.2", "--output-dir", r"C:\Export ä")
        args.source = r"C:\Models\source.safetensors"
        result = engine_args(args, lambda value: "mapped:" + value, "/work")
        self.assertEqual(result[1], "mapped:" + args.source)
        self.assertIn("mapped:" + args.base, result)
        self.assertIn("owner/vae", result)
        self.assertIn("mapped:" + args.lora[0], result)
        self.assertIn("civitai:42@43:1.2", result)
        self.assertIn("mapped:" + args.output_dir, result)

    def test_local_detection(self):
        for value in (r"C:\Models\x", r"\\server\share\x", "./local", "../local", "/tmp/x", "~/x"):
            with self.subTest(value=value):
                self.assertTrue(is_local(value))
        self.assertFalse(is_local("owner/model"))

    def test_lora_drive_colons(self):
        self.assertEqual(split_lora(r"C:\a.safetensors"), (r"C:\a.safetensors", ""))
        self.assertEqual(split_lora(r"C:\a.safetensors:0.75"), (r"C:\a.safetensors", ":0.75"))
        self.assertEqual(split_lora("civitai:12@34"), ("civitai:12@34", ""))

    def test_tokens_are_not_in_engine_arguments(self):
        args = self.parse("--civitai-token", "private-value")
        self.assertNotIn("private-value", engine_args(args, str, "/work"))

    def test_aliases_and_optional_values(self):
        args = self.parse("--licence-file", "license.txt", "--licence-name", "MIT", "--allow-missing-licence",
                          "--steps", "20", "--guidance", "5.5", "--prediction-type", "v_prediction",
                          "--clip-skip", "2", "--precision", "4bit", "--revision", "abc", "--dry-run", "-v")
        result = engine_args(args, str, "/tmp/work")
        for expected in ("--license-file", "--license-name", "--allow-missing-license", "--dry-run", "--verbose", "v_prediction", "5.5"):
            self.assertIn(expected, result)

    def test_invalid_numeric_values_and_lora_limit(self):
        for key, value in (("steps", 0), ("steps", 101), ("guidance", float("nan")),
                           ("guidance", float("inf")), ("guidance", -1), ("guidance", 31), ("lora", ["x"] * 9)):
            with self.subTest(key=key, value=value):
                args = self.parse()
                setattr(args, key, value)
                with self.assertRaises(ValueError):
                    check_options(args)

    def test_validate_and_inspect_map_pack(self):
        for command in ("validate", "inspect"):
            args = parser().parse_args([command, r"C:\Pack x.caipack"])
            self.assertEqual(engine_args(args, lambda p: "/mapped", "unused"), [command, "/mapped"])

    @unittest.skipUnless(os.environ.get("UPSTREAM_ENGINE"), "Optional contract check against installed engine")
    def test_all_upstream_options_are_available(self):
        # CI runs this with the frozen engine installed. Detect drift rather than silently drop flags.
        from coreai_diffusion_converter.cli import build_parser
        def actions(p):
            sub = next(a for a in p._actions if isinstance(a, argparse._SubParsersAction))
            return sub.choices["convert"]._actions
        upstream = {flag for a in actions(build_parser()) for flag in a.option_strings}
        ours = {flag for a in actions(parser()) for flag in a.option_strings}
        self.assertEqual(upstream - ours, set())


if __name__ == "__main__":
    unittest.main()
