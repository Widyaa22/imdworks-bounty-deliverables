import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reconcile import ReconciliationError, reconcile
from generator import generate_fixture


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = generate_fixture(seed=150015, lifecycle_count=120)

    def test_generated_fixture_covers_required_lifecycles_and_reconciles(self):
        events, snapshot, metadata = self.fixture
        result = reconcile(events, snapshot)
        self.assertEqual(metadata["lifecycle_count"], 120)
        self.assertGreaterEqual(metadata["awarded_count"], 1)
        self.assertGreaterEqual(metadata["expired_count"], 1)
        self.assertGreaterEqual(metadata["failed_withdrawal_count"], 1)
        self.assertGreaterEqual(metadata["donation_count"], 1)
        self.assertGreater(metadata["multi_credit_wallet_count"], 0)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["surplus"], metadata["donation_total"])
        self.assertEqual(result["total_liabilities"], sum(result["bounty_rewards"].values()) + sum(result["wallet_credits"].values()))
        self.assertEqual(result["token_balance"], result["total_liabilities"] + result["surplus"])

    def test_removed_event_is_detected_with_precise_position(self):
        events, snapshot, _ = self.fixture
        removed = copy.deepcopy(events)
        missing = removed.pop(17)
        with self.assertRaisesRegex(ReconciliationError, rf"event chain gap at position 17: expected seq 17, got 18; missing event_id {missing['event_id']}"):
            reconcile(removed, snapshot)

    def test_duplicated_event_is_detected_with_precise_id(self):
        events, snapshot, _ = self.fixture
        duplicated = copy.deepcopy(events)
        duplicated.insert(31, copy.deepcopy(events[30]))
        event_id = events[30]["event_id"]
        with self.assertRaisesRegex(ReconciliationError, rf"duplicate event_id {event_id} at position 31"):
            reconcile(duplicated, snapshot)

    def test_mismatched_snapshot_block_is_detected(self):
        events, snapshot, _ = self.fixture
        bad = copy.deepcopy(snapshot)
        bad["block"] += 1
        with self.assertRaisesRegex(ReconciliationError, r"snapshot block mismatch: events end at block \d+, snapshot is \d+"):
            reconcile(events, bad)

    def test_mismatched_snapshot_value_names_exact_field(self):
        events, snapshot, _ = self.fixture
        bad = copy.deepcopy(snapshot)
        wallet = sorted(bad["wallet_credits"])[0]
        bad["wallet_credits"][wallet] += 1
        with self.assertRaisesRegex(ReconciliationError, rf"wallet_credits\.{wallet} mismatch: reconstructed \d+, snapshot \d+"):
            reconcile(events, bad)

    def test_failed_withdrawal_has_no_accounting_effect(self):
        events, snapshot, _ = self.fixture
        failed = next(event for event in events if event["type"] == "WithdrawalFailed")
        prefix = events[: failed["seq"]]
        before = reconcile(prefix, snapshot=None)
        through = reconcile(events[: failed["seq"] + 1], snapshot=None)
        for field in ("bounty_rewards", "wallet_credits", "total_liabilities", "token_balance", "surplus"):
            self.assertEqual(before[field], through[field])

    def test_invalid_transition_fails_with_event_identity(self):
        events, _, _ = self.fixture
        target = next(event for event in events if event["type"] == "BountyAwarded")
        tampered = copy.deepcopy(events[: target["seq"] + 1])
        tampered[-1]["amount"] += 1
        with self.assertRaisesRegex(ReconciliationError, rf"event {target['event_id']} BountyAwarded amount"):
            reconcile(tampered, snapshot=None, verify_chain=False)

    def test_cli_generates_and_verifies_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            generate = subprocess.run(
                [sys.executable, str(ROOT / "generate.py"), "--seed", "42", "--lifecycles", "100", "--output", directory],
                text=True, capture_output=True,
            )
            self.assertEqual(generate.returncode, 0, generate.stderr)
            verify = subprocess.run(
                [sys.executable, str(ROOT / "reconcile.py"), "--events", f"{directory}/events.jsonl", "--snapshot", f"{directory}/snapshot.json"],
                text=True, capture_output=True,
            )
            self.assertEqual(verify.returncode, 0, verify.stderr)
            report = json.loads(verify.stdout)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["lifecycle_count"], 100)


if __name__ == "__main__":
    unittest.main()
