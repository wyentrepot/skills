import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "compact_log.py"
RUNNER = Path(__file__).parents[1] / "run_logged.py"


class CompactLogTests(unittest.TestCase):
    def run_script(self, text, *args):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "run.log"
            log.write_text(text, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(log), *args],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_unity_summary_excludes_unrelated_bulk(self):
        noise = "\n".join(f"unrelated boot noise {i}" for i in range(200))
        data = self.run_script(
            noise
            + "\nFAIL: test_footer_round_trip: expected 1 was 0\n"
            + "-----------------------\n12 Tests 1 Failures 0 Ignored\n",
            "--kind",
            "unity",
            "--max-lines",
            "12",
        )
        self.assertEqual(data["source_lines"], 203)
        self.assertLessEqual(data["emitted_lines"], 12)
        self.assertIn("test_footer_round_trip", "\n".join(data["evidence"]))
        self.assertNotIn("unrelated boot noise 0", "\n".join(data["evidence"]))

    def test_keyword_returns_bounded_context(self):
        text = "\n".join(
            ["discard me"] * 50
            + ["before target", "sversion   : 002401", "after target"]
            + ["discard me too"] * 50
        )
        data = self.run_script(
            text,
            "--kind",
            "serial",
            "--keyword",
            "sversion",
            "--context",
            "1",
            "--max-lines",
            "8",
        )
        self.assertEqual(data["emitted_lines"], 3)
        self.assertEqual(
            data["evidence"],
            ["before target", "sversion   : 002401", "after target"],
        )

    def test_long_compiler_line_is_truncated(self):
        data = self.run_script(
            "error: " + ("very-long-link-command " * 400),
            "--kind",
            "build",
            "--max-chars",
            "120",
        )
        self.assertEqual(data["emitted_lines"], 1)
        self.assertLessEqual(len(data["evidence"][0]), 120)
        self.assertTrue(data["evidence"][0].endswith("...<truncated>"))

    def test_runner_hides_bulk_and_reports_elapsed_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "command.log"
            code = (
                "print('\\n'.join('bulk %d' % i for i in range(100)));"
                "print('FAILED test_example')"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--log",
                    str(log),
                    "--kind",
                    "pytest",
                    "--max-lines",
                    "8",
                    "--",
                    sys.executable,
                    "-c",
                    code,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            data = json.loads(result.stdout)
            saved = log.read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data["exit_code"], 0)
        self.assertGreaterEqual(data["elapsed_seconds"], 0)
        self.assertIn("bulk 0", saved)
        self.assertNotIn("bulk 0", result.stdout)
        self.assertIn("FAILED test_example", "\n".join(data["summary"]["evidence"]))

    def test_runner_returns_no_tail_for_unmatched_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "success.log"
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--log",
                    str(log),
                    "--kind",
                    "build",
                    "--",
                    sys.executable,
                    "-c",
                    "print('ordinary successful output')",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        data = json.loads(result.stdout)
        self.assertEqual(data["exit_code"], 0)
        self.assertEqual(data["summary"]["emitted_lines"], 0)
        self.assertEqual(data["summary"]["evidence"], [])

    def test_gbk_console_does_not_break_replacement_char_json(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "gbk"
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "invalid.log"
            log.write_bytes(b"\xff\nFAILED bad byte\n")
            compact = subprocess.run(
                [sys.executable, str(SCRIPT), str(log), "--kind", "pytest"],
                capture_output=True,
                check=False,
                env=env,
            )
            runner = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--log",
                    str(log),
                    "--kind",
                    "pytest",
                    "--",
                    sys.executable,
                    "-c",
                    "import sys;sys.stdout.buffer.write(b'\\xff\\nFAILED bad byte\\n')",
                ],
                capture_output=True,
                check=False,
                env=env,
            )
        self.assertEqual(compact.returncode, 0, compact.stderr)
        self.assertEqual(runner.returncode, 0, runner.stderr)
        json.loads(compact.stdout.decode("utf-8"))
        json.loads(runner.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
