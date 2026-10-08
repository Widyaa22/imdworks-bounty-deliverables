#!/usr/bin/env python3
import argparse
import concurrent.futures
import json
import random
import sqlite3
from pathlib import Path

from submission_store import ConflictError, StaleUpdateError, SubmissionStore


def run_verification(directory, requests=200, wallets=10, seed=13):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "verification.db"
    if path.exists():
        path.unlink()
    rng = random.Random(seed)
    lost = {n for n in range(requests) if rng.random() < 0.20}
    restart_points = {n for n in range(requests) if rng.random() < 0.08}

    def request(number):
        wallet = f"wallet-{number % wallets}"
        store = SubmissionStore(path)
        try:
            row = store.submit(wallet, "bounty-13", f"key-{wallet}", f"cid:{wallet}")
            if number in lost:
                # Commit happened; model transport loss by discarding then retrying.
                store.close()
                store = SubmissionStore(path)
                row = store.submit(wallet, "bounty-13", f"key-{wallet}", f"cid:{wallet}")
            if number in restart_points:
                store.close()
                store = SubmissionStore(path)
            return row["id"]
        finally:
            store.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=40) as pool:
        list(pool.map(request, range(requests)))

    store = SubmissionStore(path)
    logical = store.count_submissions()
    connection = sqlite3.connect(path)
    duplicates = connection.execute(
        "SELECT COUNT(*) FROM (SELECT wallet,bounty,COUNT(*) n FROM submissions "
        "GROUP BY wallet,bounty HAVING n>1)"
    ).fetchone()[0]
    row = connection.execute("SELECT id FROM submissions ORDER BY wallet LIMIT 1").fetchone()
    connection.close()
    reviewed = store.review(row[0], "approved", 0)
    review_immutable = False
    stale_deterministic = False
    try:
        store.review(row[0], "rejected", 1)
    except ConflictError:
        review_immutable = True
    try:
        store.review(row[0], "rejected", 0)
    except StaleUpdateError as exc:
        stale_deterministic = str(exc) == "expected version 0, current version 1"
    trace_events = len(store.trace())
    store.close()
    return {
        "seed": seed,
        "requests": requests,
        "wallets": wallets,
        "lost_responses": len(lost),
        "restarts": len(restart_points),
        "logical_submissions": logical,
        "trace_events": trace_events,
        "no_duplicates": duplicates == 0 and logical == wallets,
        "review_immutable": review_immutable and reviewed["status"] == "approved",
        "stale_deterministic": stale_deterministic,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default="artifacts")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--wallets", type=int, default=10)
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args()
    result = run_verification(args.directory, args.requests, args.wallets, args.seed)
    output = Path(args.directory) / "result.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    if not all(result[key] for key in ("no_duplicates", "review_immutable", "stale_deterministic")):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
