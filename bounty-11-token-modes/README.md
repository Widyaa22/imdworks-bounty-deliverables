# IMD Works bounty #11 — ERC-20 behavior matrix

A local Foundry suite exercising the **unmodified, published** `IMDWorksEscrow`
source from Robinhood Chain Etherscan address
`0xd93aEd6f9F89699969B4967364D464fe7856EFaE`.

## Reproduce

```sh
forge test -vv
```

Pinned inputs:

- Solidity `0.8.29`
- OpenZeppelin Contracts `v5.4.0`
- forge-std `v1.15.0`
- Foundry used during verification: `forge 1.8.5`

## Executable behavior matrix

| Token behavior | Deposit | Award/refund bookkeeping after a funded deposit | Withdrawal | Classification / recovery |
|---|---|---|---|---|
| Standard bool return | succeeds exactly | succeeds | succeeds exactly | Supported |
| No return data | succeeds exactly via `SafeERC20` | succeeds | succeeds exactly | Supported |
| Returns `false` | `SafeERC20FailedOperation`, all escrow/token state rolls back | succeeds because award/refund does not transfer tokens | fails and preserves `claimable`; issuer stops false-return mode, then retry succeeds | Unsupported |
| Transfer tax | `UnsupportedTransfer`, including rollback of tax/burn and escrow state | succeeds because award/refund does not transfer tokens | exact-balance check reverts and preserves `claimable`; issuer sets tax to zero, then retry succeeds | Unsupported |
| Paused | transfer reverts | award, cancel, and expire bookkeeping succeed while paused | reverts and preserves `claimable`; issuer unpauses, then retry succeeds | Conditionally supported / issuer-dependent liveness |
| Sender restricted | deposit fails if creator blocked | award/refund bookkeeping succeeds | fails if escrow is blocked sender and preserves `claimable`; issuer unblocks escrow, then retry succeeds | Conditionally supported / issuer-dependent liveness |
| Recipient restricted | deposit fails if escrow blocked recipient | award/refund bookkeeping succeeds | fails for blocked recipient and preserves `claimable`; issuer unblocks recipient, then retry succeeds | Conditionally supported / issuer-dependent liveness |
| Transfer callback | nested deposit/withdraw hits `ReentrancyGuardReentrantCall` | outer lifecycle remains valid | nested withdrawal fails; outer withdrawal succeeds exactly | Supported against tested callback reentrancy |

Every successful lifecycle and every failed-withdraw recovery checks:

```text
token.balanceOf(escrow) == escrow.liabilities()
escrow.liabilities() == totalLocked + totalClaimable
```

## TDD record

The initial RED test was executed before implementation and failed as intended:

```text
[FAIL: RED: token-mode behavior matrix not implemented]
0 passed; 1 failed; 0 skipped
```

The completed suite result is recorded in `verification.txt`.
