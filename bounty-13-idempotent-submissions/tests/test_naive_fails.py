import concurrent.futures
import sqlite3
import tempfile
import unittest
from pathlib import Path

import naive


class NaiveImplementationFailureTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_naive_check_then_insert_does_not_duplicate_logical_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "naive.db"

            def request(_):
                return naive.submit(path, "wallet", "bounty", "key", "cid")

            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
                list(pool.map(request, range(20)))
            connection = sqlite3.connect(path)
            count = connection.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
            connection.close()
            self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
