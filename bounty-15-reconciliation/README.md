# Auditable bounty ledger reconciliation

A Python-standard-library tool that reconstructs escrow accounting from an append-only event journal at a fixed block and compares it with a separately supplied state snapshot.

## Accounting model

- `BountyFunded` locks a per-bounty reward and increases token balance.
- `BountyAwarded` moves the entire locked reward to the winner's wallet credit; balance is unchanged.
- `BountyExpired` leaves an unawarded reward locked until `BountyRefunded` removes the liability and balance.
- `WithdrawalSucceeded` reduces wallet credit and token balance.
- `WithdrawalFailed` changes no accounting state.
- `Donation` increases token balance but creates no contractual liability. An unsolicited transfer is therefore `token balance - (locked rewards + wallet credits)`, reported as **surplus**, not as user credit.

Amounts are non-negative integer token base units. Each event has a contiguous sequence number, unique ID, previous-event hash, and SHA-256 hash over canonical JSON. These fields make removed, reordered, duplicated, or modified records fail precisely.

## Reproduce

Requires Python 3.10+ and no third-party packages.

```sh
./run.sh
```

The command regenerates the committed fixture from seed `150015`, reconciles 120 lifecycles, exercises four deliberate corruption cases, writes `seeded-report.json`, then runs all tests.

Individual commands:

```sh
python generate.py --seed 150015 --lifecycles 120 --output fixtures/seed-150015
python reconcile.py --events fixtures/seed-150015/events.jsonl --snapshot fixtures/seed-150015/snapshot.json
python verify.py
python -m unittest discover -s tests -v
```

A successful reconciliation reports per-bounty rewards, per-wallet credits, total liabilities, token balance, donation surplus, event count, lifecycle count, and fixed block. Errors identify the exact event, position, snapshot field, or block that disagrees.
