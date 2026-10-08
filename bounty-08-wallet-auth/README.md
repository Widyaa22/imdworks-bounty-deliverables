# IMD Works bounty #8 — wallet sign-in regression suite

Executable, local-only EOA wallet authentication reference and adversarial regression suite. It uses runtime-generated wallets, EIP-191 `personal_sign` semantics via `ethers`, exact origin and chain binding, expiring single-use nonces, and opaque server-backed sessions.

## Reproduce

Requires Node 22. Dependencies are exactly pinned in `package-lock.json`.

```sh
npm ci
npm run verify
```

`verify` runs all tests, exercises both intentionally vulnerable negative controls, and writes `results.json`. The suite makes no production or RPC calls; its one HTTP integration test binds an ephemeral loopback port.

## Layout

- `src/auth.js` — secure implementation, local HTTP adapter, and two labeled vulnerable negative controls.
- `test/auth.test.js` — 33 deterministic test cases, including 20+ adversarial cases and a 32-way same-nonce race.
- `verify.js` — executable runner and machine-readable results generator.
- `THREAT_MODEL.md` — boundaries, invariants, attacks, and explicit limits.
- `results.json` — latest verified result.

## Protocol

`POST /nonce` accepts `{address, origin, chainId}` and returns the server-generated canonical challenge. The client signs `buildMessage(challenge)` using `personal_sign`. `POST /verify` accepts `{c, message, signature}`. All challenge data is checked against server state; client data is never authoritative.

Expiry is half-open: `now < expiresAt`. A verification attempt atomically consumes its nonce before cryptographic checking, so replay and concurrent duplicate verification cannot issue multiple sessions.
