import tempfile
import unittest
from pathlib import Path

from reorg_indexer import Block, Event, FixtureChain, Indexer


class IndexerTests(unittest.TestCase):
    def test_indexes_all_five_event_types_into_canonical_state(self):
        chain = FixtureChain([
            Block(1, "h1", "genesis", (
                Event("tx1", 0, "BountyCreated", {"bounty_id": "b1", "owner": "alice", "amount": 100}),
            )),
            Block(2, "h2", "h1", (
                Event("tx2", 0, "WorkSubmitted", {"bounty_id": "b1", "submission_id": "s1", "worker": "bob"}),
            )),
            Block(3, "h3", "h2", (
                Event("tx3", 0, "BountyAwarded", {"bounty_id": "b1", "submission_id": "s1", "worker": "bob", "amount": 70}),
                Event("tx3", 1, "BountyRefunded", {"bounty_id": "b1", "owner": "alice", "amount": 30}),
                Event("tx3", 2, "Withdrawn", {"account": "bob", "amount": 70}),
            )),
        ])
        with tempfile.TemporaryDirectory() as directory:
            indexer = Indexer(Path(directory) / "index.db")
            indexer.sync(chain)
            self.assertEqual(indexer.snapshot(), {
                "bounties": [["b1", "alice", 100, 70, 30]],
                "submissions": [["s1", "b1", "bob"]],
                "withdrawals": [["tx3", 2, "bob", 70]],
            })
            self.assertEqual(indexer.checkpoints(), [[1, "h1"], [2, "h2"], [3, "h3"]])
            indexer.close()

    def test_duplicate_delivery_and_out_of_order_fixture_are_idempotent(self):
        blocks = [
            Block(3, "h3", "h2", (Event("tx3", 0, "Withdrawn", {"account": "bob", "amount": 10}),)),
            Block(1, "h1", "genesis", (Event("tx1", 0, "BountyCreated", {"bounty_id": "b1", "owner": "alice", "amount": 10}),)),
            Block(2, "h2", "h1", (
                Event("tx2", 0, "WorkSubmitted", {"bounty_id": "b1", "submission_id": "s1", "worker": "bob"}),
                Event("tx2", 0, "WorkSubmitted", {"bounty_id": "b1", "submission_id": "s1", "worker": "bob"}),
            )),
        ]
        with tempfile.TemporaryDirectory() as directory:
            indexer = Indexer(Path(directory) / "index.db")
            chain = FixtureChain(blocks)
            indexer.sync(chain)
            first = indexer.snapshot()
            indexer.sync(chain)
            self.assertEqual(indexer.snapshot(), first)
            self.assertEqual(len(first["submissions"]), 1)
            indexer.close()

    def test_duplicate_award_delivery_does_not_double_payout(self):
        award = Event("award", 0, "BountyAwarded", {"bounty_id": "b1", "submission_id": "s1", "worker": "bob", "amount": 10})
        chain = FixtureChain([
            Block(1, "h1", "genesis", (Event("create", 0, "BountyCreated", {"bounty_id": "b1", "owner": "alice", "amount": 10}),)),
            Block(2, "h2", "h1", (award, award)),
        ])
        with tempfile.TemporaryDirectory() as directory:
            indexer = Indexer(Path(directory) / "index.db")
            indexer.sync(chain)
            indexer.sync(chain)
            self.assertEqual(indexer.snapshot()["bounties"], [["b1", "alice", 10, 10, 0]])
            indexer.close()

    def test_restart_after_failure_between_event_write_and_checkpoint_is_atomic(self):
        chain = FixtureChain([
            Block(1, "h1", "genesis", (Event("tx1", 0, "BountyCreated", {"bounty_id": "b1", "owner": "alice", "amount": 10}),)),
        ])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.db"
            indexer = Indexer(path)
            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                indexer.sync(chain, before_checkpoint=lambda _block: (_ for _ in ()).throw(RuntimeError("simulated crash")))
            indexer.close()
            restarted = Indexer(path)
            self.assertEqual(restarted.checkpoints(), [])
            self.assertEqual(restarted.snapshot(), {"bounties": [], "submissions": [], "withdrawals": []})
            restarted.sync(chain)
            self.assertEqual(restarted.checkpoints(), [[1, "h1"]])
            restarted.close()

    def test_five_block_reorg_exactly_matches_fresh_replay(self):
        prefix = [
            Block(1, "h1", "genesis", (Event("c1", 0, "BountyCreated", {"bounty_id": "b1", "owner": "alice", "amount": 100}),)),
            Block(2, "h2", "h1", ()),
        ]
        old = prefix + [
            Block(3, "old3", "h2", (Event("os", 0, "WorkSubmitted", {"bounty_id": "b1", "submission_id": "old", "worker": "mallory"}),)),
            Block(4, "old4", "old3", (Event("oa", 0, "BountyAwarded", {"bounty_id": "b1", "submission_id": "old", "worker": "mallory", "amount": 100}),)),
            Block(5, "old5", "old4", (Event("ow", 0, "Withdrawn", {"account": "mallory", "amount": 100}),)),
            Block(6, "old6", "old5", ()),
            Block(7, "old7", "old6", ()),
        ]
        new = prefix + [
            Block(3, "new3", "h2", (Event("ns", 0, "WorkSubmitted", {"bounty_id": "b1", "submission_id": "new", "worker": "bob"}),)),
            Block(4, "new4", "new3", (Event("na", 0, "BountyAwarded", {"bounty_id": "b1", "submission_id": "new", "worker": "bob", "amount": 80}),)),
            Block(5, "new5", "new4", (Event("nr", 0, "BountyRefunded", {"bounty_id": "b1", "owner": "alice", "amount": 20}),)),
            Block(6, "new6", "new5", (Event("nw", 0, "Withdrawn", {"account": "bob", "amount": 80}),)),
            Block(7, "new7", "new6", ()),
        ]
        with tempfile.TemporaryDirectory() as directory:
            recovered = Indexer(Path(directory) / "recovered.db")
            recovered.sync(FixtureChain(old))
            recovered.sync(FixtureChain(new))
            fresh = Indexer(Path(directory) / "fresh.db")
            fresh.sync(FixtureChain(new))
            self.assertEqual(recovered.snapshot(), fresh.snapshot())
            self.assertEqual(recovered.checkpoints(), fresh.checkpoints())
            self.assertEqual(recovered.snapshot()["submissions"], [["new", "b1", "bob"]])
            self.assertEqual(recovered.snapshot()["withdrawals"], [["nw", 0, "bob", 80]])
            recovered.close()
            fresh.close()


if __name__ == "__main__":
    unittest.main()
