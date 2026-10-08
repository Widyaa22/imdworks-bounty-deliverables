import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class BenchmarkAcceptanceTests(unittest.TestCase):
    def setUp(self):
        from prompt_boundary import load_fixtures
        self.fixtures = load_fixtures(ROOT / "fixtures.json")

    def test_fixture_inventory_and_required_attack_categories(self):
        attacks = [f for f in self.fixtures if f["kind"] == "attack"]
        benign = [f for f in self.fixtures if f["kind"] == "benign"]
        self.assertGreaterEqual(len(attacks), 30)
        self.assertGreaterEqual(len(benign), 10)
        categories = {f["category"] for f in attacks}
        self.assertTrue({
            "tool_output_injection", "encoded_instruction",
            "forged_system_message", "credential_exfiltration"
        }.issubset(categories))
        self.assertEqual(len({f["id"] for f in self.fixtures}), len(self.fixtures))

    def test_defended_policy_blocks_every_unauthorized_call_and_allows_controls(self):
        from prompt_boundary import run_benchmark
        report = run_benchmark(self.fixtures)
        defended = report["systems"]["defended"]
        self.assertEqual(defended["unauthorized_calls"], 0)
        self.assertEqual(defended["attack_passed"], defended["attack_total"])
        self.assertEqual(defended["benign_passed"], defended["benign_total"])
        self.assertGreater(defended["authorized_calls"], 0)

    def test_naive_baseline_demonstrably_fails(self):
        from prompt_boundary import run_benchmark
        naive = run_benchmark(self.fixtures)["systems"]["naive"]
        self.assertGreater(naive["unauthorized_calls"], 0)
        self.assertLess(naive["attack_passed"], naive["attack_total"])

    def test_tool_gateway_fails_closed_for_unknown_tool_action_or_capability(self):
        from prompt_boundary import AuthorizationError, ToolGateway
        gateway = ToolGateway({"read_public": {"read"}})
        for tool, action, capability in (
            ("missing", "read", "read_public"),
            ("read_public", "delete", "read_public"),
            ("read_public", "read", "missing"),
        ):
            with self.subTest(tool=tool, action=action, capability=capability):
                with self.assertRaises(AuthorizationError):
                    gateway.call(tool, action, {}, capability)
        self.assertEqual(gateway.audit_log, [])

    def test_report_is_deterministic_and_machine_readable(self):
        from prompt_boundary import run_benchmark
        first = run_benchmark(self.fixtures)
        second = run_benchmark(self.fixtures)
        self.assertEqual(first, second)
        encoded = json.dumps(first, sort_keys=True)
        self.assertEqual(json.loads(encoded), first)
        self.assertEqual(first["schema_version"], "1.0")
        self.assertTrue(first["requirements_met"])
        self.assertEqual(len(first["results"]), len(self.fixtures) * 2)

    def test_cli_writes_report_and_exits_successfully(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            proc = subprocess.run(
                [sys.executable, str(ROOT / "verify.py"), "--output", str(report)],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(payload["requirements_met"])
            self.assertEqual(json.loads(proc.stdout), payload)


if __name__ == "__main__":
    unittest.main()
