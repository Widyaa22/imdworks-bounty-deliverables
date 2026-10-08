# Reorg-safe bounty event indexer

A minimal Python-standard-library implementation that stores raw canonical events and block-hash checkpoints in SQLite, then derives bounty state deterministically.

## Guarantees

- Indexes `BountyCreated`, `WorkSubmitted`, `BountyAwarded`, `BountyRefunded`, and `Withdrawn`.
- Uses `(tx_hash, log_index)` as the event identity, making duplicate delivery idempotent.
- Accepts fixture blocks in arbitrary batch order; block numbers define canonical order.
- Writes each block's events and checkpoint in one SQLite transaction.
- Detects reorgs by comparing saved checkpoint hashes, deletes the divergent suffix, and replays the new canonical branch.
- Derived state is reconstructed from canonical raw events, preventing orphaned submissions and payouts.

## Run

Requires Python 3.10+ and no third-party packages.

```sh
./run_tests.sh
```

The deterministic test fixture covers all five event types, duplicate delivery, out-of-order blocks, restart at the event/checkpoint fault boundary, duplicate award protection, and a five-block competing-branch reorg compared byte-for-value with a fresh replay.
