# Threat model

## Scope and assets

This is an offline/local regression target for Ethereum EOA sign-in. The protected assets are authentication sessions and the binding between a session, wallet address, exact web origin, and EVM chain ID. Test wallets are generated at runtime and their private keys never leave process memory. No production service, RPC node, browser wallet, or real account is contacted.

## Trust boundaries

- Untrusted: every HTTP field, claimed address, origin, chain ID, message, nonce, timestamps, and signature.
- Trusted: CSPRNG, server clock, configured exact allowlists, in-memory challenge/session stores, and `ethers` signature recovery.
- The server, not the client, creates and stores each challenge tuple.

## Required invariants

1. The signed `personal_sign` payload canonically binds domain label, normalized address, exact origin, integer chain ID, 256-bit nonce, issuance, and expiration.
2. A challenge is accepted only if every submitted field exactly equals its server-side record.
3. Expiration uses a half-open validity interval: valid while `now < expiresAt`; invalid at and after the boundary.
4. The nonce transitions from fresh to consumed synchronously before signature verification can yield. Concurrent verification therefore produces exactly one session.
5. A malformed or failed attempt also consumes the nonce, preventing online retries against one challenge.
6. Sessions are opaque CSPRNG tokens stored server-side and retain address/origin/chain bindings.

## Covered attacks

Replay, concurrent replay, wrong signer, claimed-address substitution, exact/suffix/userinfo/path/case origin confusion, wrong and type-confused chain IDs, expiry boundaries, future timestamps, unknown/cross-wallet nonces, malformed/non-hex/oversized/high-s signatures, message whitespace/order/duplicate-field mutation, weak nonce formatting/collision, and session uniqueness/binding.

## Negative controls

`ReplayableAuthService` intentionally restores nonce state after verification. `ContextBlindAuthService` intentionally signs only the nonce and trusts submitted origin/chain context. Tests demonstrate their exploitable behavior; the verification runner separately asserts that the secure conformance probes reject both.

## Explicit limits

EOA `personal_sign` only. Contract wallets/EIP-1271, persistence across process restarts, distributed atomic storage, TLS termination, rate limiting, CSRF transport policy, and production session cookies are outside this local harness. A production deployment must replace in-memory state with an atomic shared datastore and enforce transport/session controls.
