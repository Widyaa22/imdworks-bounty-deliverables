# Bounty 13 — Idempotent SQLite submissions

A Python-standard-library harness proving exactly one active submission per `(wallet, bounty)` under concurrent retries, response loss, stale updates, review transitions, and process/connection restarts.

## Replay

```sh
chmod +x run.sh
./run.sh
```

`run.sh` executes the complete unit/integration suite and a seeded 200-request replay across 10 wallets. The replay writes `artifacts/verification.db` (including durable `trace_events`) and `artifacts/result.json`.

## Guarantees

- SQLite uniqueness constraints enforce one logical submission per wallet/bounty.
- `BEGIN IMMEDIATE` serializes check-and-create; WAL and busy timeout support concurrent callers.
- Matching idempotency key plus content returns the committed original, including after response loss/restart.
- A mismatched retry returns `ConflictError` and cannot replace existing work.
- Reviews use version compare-and-swap. Stale versions return deterministic `StaleUpdateError`; terminal reviews are immutable.
- Submission and review state changes and retry outcomes are transactionally traced.
- `naive.py` is an intentionally broken check-then-insert baseline; its expected-failure test demonstrates duplicate creation.
