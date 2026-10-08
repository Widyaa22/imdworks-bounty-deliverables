#!/usr/bin/env python3
"""Independently reconstruct escrow liabilities from an ordered event journal."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


class ReconciliationError(ValueError):
    """The journal or snapshot cannot be reconciled."""


def canonical_event(event: dict[str, Any]) -> bytes:
    payload = {key: value for key, value in event.items() if key != "event_hash"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def event_hash(event: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_event(event)).hexdigest()


def _require_nonnegative_amount(event: dict[str, Any]) -> int:
    amount = event.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        raise ReconciliationError(f"event {event.get('event_id')} {event.get('type')} amount must be a non-negative integer")
    return amount


def _compare_mapping(label: str, actual: dict[str, int], expected: dict[str, int]) -> None:
    for key in sorted(set(actual) | set(expected)):
        left, right = actual.get(key, 0), expected.get(key, 0)
        if left != right:
            raise ReconciliationError(f"{label}.{key} mismatch: reconstructed {left}, snapshot {right}")


def reconcile(events: list[dict[str, Any]], snapshot: dict[str, Any] | None, verify_chain: bool = True) -> dict[str, Any]:
    bounties: dict[str, int] = {}
    credits: defaultdict[str, int] = defaultdict(int)
    statuses: dict[str, str] = {}
    balance = 0
    donations = 0
    seen: set[str] = set()
    previous_hash = "GENESIS"

    for position, event in enumerate(events):
        event_id = event.get("event_id")
        if event_id in seen:
            raise ReconciliationError(f"duplicate event_id {event_id} at position {position}")
        seen.add(event_id)
        if event.get("seq") != position:
            raise ReconciliationError(
                f"event chain gap at position {position}: expected seq {position}, got {event.get('seq')}; missing event_id evt-{position:06d}"
            )
        if verify_chain:
            if event.get("prev_hash") != previous_hash:
                raise ReconciliationError(f"event {event_id} prev_hash mismatch")
            calculated = event_hash(event)
            if event.get("event_hash") != calculated:
                raise ReconciliationError(f"event {event_id} hash mismatch: expected {calculated}, got {event.get('event_hash')}")
            previous_hash = calculated

        kind = event.get("type")
        amount = _require_nonnegative_amount(event) if "amount" in event else 0
        bounty = event.get("bounty_id")
        wallet = event.get("wallet")
        if kind == "BountyFunded":
            if bounty in statuses:
                raise ReconciliationError(f"event {event_id} BountyFunded repeats bounty {bounty}")
            bounties[bounty], statuses[bounty] = amount, "open"
            balance += amount
        elif kind == "BountyAwarded":
            locked = bounties.get(bounty, 0)
            if statuses.get(bounty) != "open" or amount != locked:
                raise ReconciliationError(f"event {event_id} BountyAwarded amount {amount} does not equal locked reward {locked} for {bounty}")
            del bounties[bounty]
            statuses[bounty] = "awarded"
            credits[wallet] += amount
        elif kind == "BountyExpired":
            if statuses.get(bounty) != "open":
                raise ReconciliationError(f"event {event_id} BountyExpired invalid state for {bounty}")
            statuses[bounty] = "expired"
        elif kind == "BountyRefunded":
            locked = bounties.get(bounty, 0)
            if statuses.get(bounty) != "expired" or amount != locked:
                raise ReconciliationError(f"event {event_id} BountyRefunded amount {amount} does not equal expired reward {locked} for {bounty}")
            del bounties[bounty]
            statuses[bounty] = "refunded"
            balance -= amount
        elif kind == "WithdrawalSucceeded":
            available = credits.get(wallet, 0)
            if amount > available:
                raise ReconciliationError(f"event {event_id} WithdrawalSucceeded amount {amount} exceeds credit {available} for {wallet}")
            credits[wallet] -= amount
            balance -= amount
        elif kind == "WithdrawalFailed":
            if amount > credits.get(wallet, 0):
                raise ReconciliationError(f"event {event_id} WithdrawalFailed amount {amount} exceeds credit {credits.get(wallet, 0)} for {wallet}")
        elif kind == "Donation":
            balance += amount
            donations += amount
        else:
            raise ReconciliationError(f"event {event_id} has unknown type {kind!r}")

    clean_credits = {key: value for key, value in sorted(credits.items()) if value}
    clean_bounties = dict(sorted(bounties.items()))
    liabilities = sum(clean_bounties.values()) + sum(clean_credits.values())
    report = {
        "status": "ok",
        "block": events[-1]["block"] if events else 0,
        "event_count": len(events),
        "lifecycle_count": sum(1 for e in events if e.get("type") == "BountyFunded"),
        "bounty_rewards": clean_bounties,
        "wallet_credits": clean_credits,
        "total_liabilities": liabilities,
        "token_balance": balance,
        "surplus": balance - liabilities,
        "donation_total": donations,
    }
    if report["surplus"] != donations:
        raise ReconciliationError(f"surplus invariant mismatch: balance minus liabilities is {report['surplus']}, donations total {donations}")

    if snapshot is not None:
        if snapshot.get("block") != report["block"]:
            raise ReconciliationError(f"snapshot block mismatch: events end at block {report['block']}, snapshot is {snapshot.get('block')}")
        _compare_mapping("bounty_rewards", clean_bounties, snapshot.get("bounty_rewards", {}))
        _compare_mapping("wallet_credits", clean_credits, snapshot.get("wallet_credits", {}))
        for field in ("total_liabilities", "token_balance"):
            if snapshot.get(field) != report[field]:
                raise ReconciliationError(f"{field} mismatch: reconstructed {report[field]}, snapshot {snapshot.get(field)}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    args = parser.parse_args()
    try:
        events = [json.loads(line) for line in args.events.read_text().splitlines() if line.strip()]
        snapshot = json.loads(args.snapshot.read_text())
        print(json.dumps(reconcile(events, snapshot), indent=2, sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, ReconciliationError) as exc:
        print(f"reconciliation failed: {exc}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
