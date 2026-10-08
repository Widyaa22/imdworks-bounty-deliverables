#!/usr/bin/env python3
"""Run the seeded reconciliation and required tamper-detection checks."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from reconcile import ReconciliationError, reconcile

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "fixtures" / "seed-150015"


def load() -> tuple[list[dict], dict, dict]:
    events = [json.loads(line) for line in (FIXTURE / "events.jsonl").read_text().splitlines()]
    snapshot = json.loads((FIXTURE / "snapshot.json").read_text())
    metadata = json.loads((FIXTURE / "metadata.json").read_text())
    return events, snapshot, metadata


def expected_failure(name: str, events: list[dict], snapshot: dict) -> dict[str, str]:
    try:
        reconcile(events, snapshot)
    except ReconciliationError as exc:
        return {"name": name, "status": "detected", "message": str(exc)}
    raise AssertionError(f"{name} was not detected")


def build_report() -> dict:
    events, snapshot, metadata = load()
    reconciled = reconcile(events, snapshot)
    removed = copy.deepcopy(events)
    removed.pop(17)
    duplicated = copy.deepcopy(events)
    duplicated.insert(31, copy.deepcopy(events[30]))
    wrong_block = copy.deepcopy(snapshot)
    wrong_block["block"] += 1
    wrong_credit = copy.deepcopy(snapshot)
    wallet = sorted(wrong_credit["wallet_credits"])[0]
    wrong_credit["wallet_credits"][wallet] += 1
    checks = [
        expected_failure("removed_event", removed, snapshot),
        expected_failure("duplicated_event", duplicated, snapshot),
        expected_failure("mismatched_block_snapshot", events, wrong_block),
        expected_failure("mismatched_state_snapshot", events, wrong_credit),
    ]
    return {
        "status": "verified",
        "fixture": metadata,
        "reconciliation": reconciled,
        "negative_checks": checks,
        "accounting_explanation": (
            "Donation events increase token balance but create neither a locked bounty reward "
            "nor a wallet credit. Therefore they increase balance-minus-liabilities and are "
            "reported as surplus, never as user credit."
        ),
    }


def main() -> int:
    report = build_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
