"""Minimal SQLite-backed, reorg-safe event indexer."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Event:
    tx_hash: str
    log_index: int
    kind: str
    data: dict


@dataclass(frozen=True)
class Block:
    number: int
    hash: str
    parent_hash: str
    events: tuple[Event, ...] = ()


class FixtureChain:
    def __init__(self, blocks: Iterable[Block]):
        self._blocks = {block.number: block for block in blocks}

    @property
    def height(self) -> int:
        return max(self._blocks, default=0)

    def block(self, number: int) -> Block:
        return self._blocks[number]


class Indexer:
    def __init__(self, path: Path | str):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS checkpoints(
                block_number INTEGER PRIMARY KEY, block_hash TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS events(
                block_number INTEGER NOT NULL,
                block_hash TEXT NOT NULL,
                tx_hash TEXT NOT NULL,
                log_index INTEGER NOT NULL,
                kind TEXT NOT NULL,
                data TEXT NOT NULL,
                PRIMARY KEY(tx_hash, log_index)
            );
        """)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def checkpoints(self) -> list[list]:
        return [list(row) for row in self.db.execute(
            "SELECT block_number, block_hash FROM checkpoints ORDER BY block_number"
        )]

    def sync(self, chain: FixtureChain, before_checkpoint=None) -> None:
        rows = self.checkpoints()
        ancestor = 0
        for number, block_hash in rows:
            if number <= chain.height and chain.block(number).hash == block_hash:
                ancestor = number
            else:
                break
        with self.db:
            self.db.execute("DELETE FROM events WHERE block_number > ?", (ancestor,))
            self.db.execute("DELETE FROM checkpoints WHERE block_number > ?", (ancestor,))
        for number in range(ancestor + 1, chain.height + 1):
            block = chain.block(number)
            expected_parent = "genesis" if number == 1 else chain.block(number - 1).hash
            if block.parent_hash != expected_parent:
                raise ValueError(f"broken canonical chain at block {number}")
            with self.db:
                for event in block.events:
                    self.db.execute(
                        "INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?, ?, ?)",
                        (number, block.hash, event.tx_hash, event.log_index,
                         event.kind, json.dumps(event.data, sort_keys=True, separators=(",", ":"))),
                    )
                if before_checkpoint is not None:
                    before_checkpoint(block)
                self.db.execute(
                    "INSERT INTO checkpoints VALUES (?, ?)", (number, block.hash)
                )

    def snapshot(self) -> dict[str, list[list]]:
        bounties: dict[str, list] = {}
        submissions: dict[str, list] = {}
        withdrawals: dict[tuple[str, int], list] = {}
        for tx_hash, log_index, kind, encoded in self.db.execute(
            "SELECT tx_hash, log_index, kind, data FROM events "
            "ORDER BY block_number, log_index, tx_hash"
        ):
            data = json.loads(encoded)
            if kind == "BountyCreated":
                bounties[data["bounty_id"]] = [data["bounty_id"], data["owner"], data["amount"], 0, 0]
            elif kind == "WorkSubmitted":
                submissions.setdefault(data["submission_id"], [data["submission_id"], data["bounty_id"], data["worker"]])
            elif kind == "BountyAwarded":
                bounty = bounties[data["bounty_id"]]
                bounty[3] += data["amount"]
            elif kind == "BountyRefunded":
                bounty = bounties[data["bounty_id"]]
                bounty[4] += data["amount"]
            elif kind == "Withdrawn":
                withdrawals.setdefault((tx_hash, log_index), [tx_hash, log_index, data["account"], data["amount"]])
        return {
            "bounties": sorted(bounties.values()),
            "submissions": sorted(submissions.values()),
            "withdrawals": sorted(withdrawals.values()),
        }
