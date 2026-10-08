# IMD Works bounty #6 — stateful escrow invariant harness

A local Foundry state-machine harness for the verified `IMDWorksEscrow` deployed on Robinhood Chain at [`0xd93aEd6f9F89699969B4967364D464fe7856EFaE`](https://robin.etherscan.io/address/0xd93aEd6f9F89699969B4967364D464fe7856EFaE#code).

## One-command verification

```bash
./scripts/verify.sh
```

This first applies a deliberately broken double-credit mutation and requires Foundry to detect it (**RED**), then restores and runs the clean contract for **1,000 invariant sequences at depth 100** (100,000 calls, **GREEN**). Outputs are saved under `artifacts/`.

## Model and invariants

`EscrowHandler` models exactly 3 creators and 5 workers. Stateful actions cover bounty creation, worker-to-worker delegation, direct and delegated submissions, creator top-ups, bounded time jumps, cancellation, award, expiry, and pull withdrawals.

The model maintains its own bounty status/reward/submission records, locked principal, per-account credits, and aggregate claimable amount. Model values are updated only after successful calls; they are not derived from `totalLocked`, `totalClaimable`, `liabilities()`, or token balances.

The invariants assert:

1. The escrow token balance covers independently computed model liabilities, and the contract's reported liabilities equal that independent amount.
2. Each modeled bounty executes at most one terminal transition, and all modeled terminal fields match contract state. Repeated award/cancel/expire attempts therefore cannot pay a terminal bounty twice.

## Reproducibility

- Solidity: `0.8.29` pinned in `foundry.toml`.
- Foundry run seed: `0x494d44574f524b532d424f554e54592d3036` (`IMDWORKS-BOUNTY-06`).
- Invariant settings: `runs = 1000`, `depth = 100`.
- forge-std tag `v1.9.7`, commit recorded by `scripts/verify.sh`.
- OpenZeppelin Contracts tag `v5.4.0`, commit recorded by `scripts/verify.sh`.
- Verified source and complete Sourcify response are retained locally; SHA-256 is recorded on every run.

## TDD record

- **RED negative control:** `scripts/apply_double_credit_mutation.py` introduces an extra winner credit without a corresponding model transition. `scripts/verify.sh` requires the invariant suite to fail and captures the trace in `artifacts/red-mutation.txt`.
- **GREEN:** the unmodified verified source passes both invariants for 1,000 × 100 calls; output is in `artifacts/green.txt`.

The mutation is temporary. The runner restores the verified source even if testing is interrupted.

## Assumptions and scope

- Entirely local EVM; no fork or live-chain writes.
- `MockUSDG` is a standard exact-transfer, non-rebasing ERC-20, matching the deployed contract's documented token requirement.
- Creators are pre-funded and grant unlimited approval only to exercise escrow transitions.
- At most 32 bounties are tracked per sequence to keep terminal-state iteration bounded.
- Handler methods absorb expected invalid state transitions; a successful contract call must be reflected by the independent model.
- The verified source was fetched read-only from Sourcify chain ID `4663`; deployed bytecode provenance is retained in `sourcify-response.json`.
