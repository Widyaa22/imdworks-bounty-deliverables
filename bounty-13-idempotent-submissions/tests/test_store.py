import concurrent.futures
import http.client
import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest

from pathlib import Path

from api import create_server
from submission_store import ConflictError, StaleUpdateError, SubmissionStore
from verify import run_verification


DB_NAME = "store.db"


class SubmissionStoreTests(unittest.TestCase):
    def test_retry_after_lost_response_returns_original_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SubmissionStore(Path(directory) / "store.db")
            first = store.submit("wallet-1", "bounty-13", "idem-1", "cid:first")
            retry = store.submit("wallet-1", "bounty-13", "idem-1", "cid:first")
            self.assertEqual(first, retry)
            self.assertEqual(store.count_submissions(), 1)
            store.close()

    def test_concurrent_requests_create_one_per_wallet_and_bounty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / DB_NAME

            def request(number):
                wallet = f"wallet-{number % 10}"
                store = SubmissionStore(path)
                try:
                    return store.submit(wallet, "bounty-13", f"key-{wallet}", f"cid:{wallet}")
                finally:
                    store.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
                rows = list(pool.map(request, range(120)))
            store = SubmissionStore(path)
            self.assertEqual(store.count_submissions(), 10)
            for wallet in range(10):
                ids = {r["id"] for r in rows if r["wallet"] == f"wallet-{wallet}"}
                self.assertEqual(len(ids), 1)
            store.close()

    def test_conflicting_retry_does_not_replace_active_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SubmissionStore(Path(directory) / DB_NAME)
            original = store.submit("wallet", "bounty", "key", "cid:original")
            with self.assertRaises(ConflictError):
                store.submit("wallet", "bounty", "different-key", "cid:replacement")
            self.assertEqual(store.get(original["id"])["content"], "cid:original")
            store.close()

    def test_review_transition_is_compare_and_swap_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SubmissionStore(Path(directory) / DB_NAME)
            pending = store.submit("wallet", "bounty", "key", "cid")
            approved = store.review(pending["id"], "approved", expected_version=0)
            self.assertEqual((approved["status"], approved["version"]), ("approved", 1))
            with self.assertRaises(StaleUpdateError):
                store.review(pending["id"], "rejected", expected_version=0)
            with self.assertRaises(ConflictError):
                store.review(pending["id"], "rejected", expected_version=1)
            self.assertEqual(store.get(pending["id"])["status"], "approved")
            store.close()

    def test_restart_recovers_committed_submission_after_response_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / DB_NAME
            store = SubmissionStore(path)
            created = store.submit("wallet", "bounty", "lost", "cid")
            store.close()
            restarted = SubmissionStore(path)
            recovered = restarted.submit("wallet", "bounty", "lost", "cid")
            self.assertEqual(created, recovered)
            restarted.close()

    def test_schema_constraints_reject_duplicates_and_invalid_status(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / DB_NAME
            store = SubmissionStore(path)
            row = store.submit("wallet", "bounty", "key", "cid")
            store.close()
            connection = sqlite3.connect(path)
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO submissions VALUES(?,?,?,?,?,?,?,?,?)",
                    ("other", "wallet", "bounty", "other-key", "other", "pending", 0, 1, 1),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE submissions SET status='corrupt' WHERE id=?", (row["id"],)
                )
            connection.close()

    def test_trace_records_commits_idempotent_hits_conflicts_and_reviews(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SubmissionStore(Path(directory) / DB_NAME)
            row = store.submit("wallet", "bounty", "key", "cid")
            store.submit("wallet", "bounty", "key", "cid")
            with self.assertRaises(ConflictError):
                store.submit("wallet", "bounty", "other", "other")
            store.review(row["id"], "approved", 0)
            actions = [event["action"] for event in store.trace()]
            self.assertEqual(actions, ["submitted", "idempotent_hit", "submit_conflict", "approved"])
            store.close()

    def test_verification_replays_200_requests_with_loss_and_restarts(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_verification(Path(directory), requests=200, wallets=10, seed=13)
            self.assertEqual(result["requests"], 200)
            self.assertEqual(result["wallets"], 10)
            self.assertEqual(result["logical_submissions"], 10)
            self.assertGreater(result["lost_responses"], 0)
            self.assertGreater(result["restarts"], 0)
            self.assertTrue(result["no_duplicates"])
            self.assertTrue(result["review_immutable"])
            self.assertTrue(result["stale_deterministic"])

    def test_process_interruption_after_commit_recovers_on_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / DB_NAME
            code = (
                "from submission_store import SubmissionStore; import os; "
                f"s=SubmissionStore({str(path)!r}); "
                "s.submit('wallet','bounty','key','cid'); os._exit(91)"
            )
            child = subprocess.run([sys.executable, "-c", code], check=False)
            self.assertEqual(child.returncode, 91)
            store = SubmissionStore(path)
            recovered = store.submit("wallet", "bounty", "key", "cid")
            self.assertEqual(store.count_submissions(), 1)
            self.assertEqual(recovered["content"], "cid")
            store.close()

    def test_http_api_returns_same_submission_for_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, Path(directory) / DB_NAME)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                host, port = server.server_address
                payload = json.dumps({
                    "wallet": "wallet", "bounty": "bounty",
                    "idempotency_key": "key", "content": "cid",
                })
                responses = []
                for _ in range(2):
                    connection = http.client.HTTPConnection(host, port, timeout=5)
                    connection.request("POST", "/submissions", payload, {"Content-Type": "application/json"})
                    response = connection.getresponse()
                    responses.append((response.status, json.loads(response.read())))
                    connection.close()
                self.assertEqual([item[0] for item in responses], [201, 200])
                self.assertEqual(responses[0][1], responses[1][1])
            finally:
                server.shutdown()
                thread.join()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
