#!/usr/bin/env python3
"""Deterministic escrow event fixture generator."""
from __future__ import annotations

import random
from collections import Counter
from typing import Any

from reconcile import event_hash, reconcile


def generate_fixture(seed: int, lifecycle_count: int) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, int]]:
    if lifecycle_count < 4:
        raise ValueError("lifecycle_count must be at least 4")
    rng = random.Random(seed)
    events: list[dict[str, Any]] = []
    previous_hash = "GENESIS"
    block = 9_000_000

    def emit(kind: str, **fields: Any) -> None:
        nonlocal previous_hash, block
        block += rng.randint(1, 3)
        seq = len(events)
        event = {"seq": seq, "event_id": f"evt-{seq:06d}", "block": block, "type": kind, "prev_hash": previous_hash, **fields}
        event["event_hash"] = event_hash(event)
        events.append(event)
        previous_hash = event["event_hash"]

    wallets = [f"0x{index:040x}" for index in range(1, 13)]
    awarded_count = expired_count = failed_count = 0
    credit_counts: Counter[str] = Counter()
    for index in range(lifecycle_count):
        bounty = f"bounty-{index:04d}"
        amount = rng.randint(10_000, 900_000)
        emit("BountyFunded", bounty_id=bounty, amount=amount)
        mode = index % 5
        if mode in (0, 1, 3):
            wallet = wallets[index % len(wallets)]
            emit("BountyAwarded", bounty_id=bounty, wallet=wallet, amount=amount)
            awarded_count += 1
            credit_counts[wallet] += 1
            if mode == 1:
                emit("WithdrawalFailed", wallet=wallet, amount=max(1, amount // 2))
                failed_count += 1
            elif mode == 3:
                emit("WithdrawalSucceeded", wallet=wallet, amount=amount)
        else:
            emit("BountyExpired", bounty_id=bounty)
            expired_count += 1
            if mode == 4:
                emit("BountyRefunded", bounty_id=bounty, amount=amount)
        if index in (7, lifecycle_count // 2, lifecycle_count - 1):
            emit("Donation", wallet=f"0x{'d':>040}", amount=111 + index)

    report = reconcile(events, snapshot=None)
    snapshot = {
        "block": report["block"],
        "bounty_rewards": report["bounty_rewards"],
        "wallet_credits": report["wallet_credits"],
        "total_liabilities": report["total_liabilities"],
        "token_balance": report["token_balance"],
    }
    metadata = {
        "seed": seed,
        "lifecycle_count": lifecycle_count,
        "awarded_count": awarded_count,
        "expired_count": expired_count,
        "failed_withdrawal_count": failed_count,
        "donation_count": sum(1 for e in events if e["type"] == "Donation"),
        "donation_total": report["donation_total"],
        "multi_credit_wallet_count": sum(count > 1 for count in credit_counts.values()),
    }
    return events, snapshot, metadata
