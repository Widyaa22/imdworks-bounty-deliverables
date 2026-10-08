# IMDWorksEscrow bytecode provenance

Reproducible verification for Robinhood Chain contract `0xd93aEd6f9F89699969B4967364D464fe7856EFaE` (chain ID 4663).

## Result

The published `IMDWorksEscrow` source rebuilds byte-for-byte to the deployed 6,258-byte runtime after substituting the constructor-set immutable `paymentToken` value. The address derived independently from all nine deployed immutable words is `0x5fc5360d0400a0fd4f2af552add042d716f1d168`.

## Pinned build

- Solidity `0.8.29+commit.ab55807c` (`solc` npm package `0.8.29`)
- OpenZeppelin Contracts `5.4.0`
- optimizer enabled, 200 runs
- EVM version `paris`
- `viaIR: false`
- metadata: CBOR appended, `bytecodeHash: none`, literal content disabled
- remapping: `@openzeppelin/contracts/=node_modules/@openzeppelin/contracts/`

`package-lock.json` pins package tarball integrity. `evidence/report.json` includes SHA-256 for every compiler input, the lockfile, standard input and an aggregate OpenZeppelin source manifest.

## Run

```sh
npm ci
npm test
npm run verify
npm run verify:mutations
npm run verify:live
```

`npm run verify` is deterministic and uses the checked-in runtime fixture. `npm run verify:live` performs read-only `eth_getCode` against the public Robinhood Chain RPC, saves the response, rebuilds, compares, and exits nonzero on any mismatch.

To demonstrate immutable failure directly:

```sh
node verify.js --offline --token 0x0000000000000000000000000000000000000001
```

This exits 1. The automated test suite also mutates one source statement and confirms failure.

## Immutable substitution

Solc reports nine `paymentToken` references, each 32 bytes long, at runtime byte offsets listed in `evidence/report.json`. During deployment, the constructor replaces each compiler placeholder with the ABI word for the token: twelve zero bytes followed by its twenty address bytes. The verifier derives the deployed address only when all nine words agree, then applies exactly that value to the rebuilt runtime before comparing every byte. Metadata is not stripped or ignored; it remains part of the comparison.

## Evidence provenance

- `fixtures/deployed-runtime.hex`: fetched with public JSON-RPC `eth_getCode`, block tag `latest`.
- `fixtures/sources/**` and `fixtures/standard-input.json`: published verification bundle obtained from Sourcify's public API; Sourcify match ID and deployment fields are retained in `fixtures/sourcify-attestation.json`.
- `src/IMDWorksEscrow.sol`: reviewable project-source copy used by the build.
- `evidence/report.json`: machine-readable byte comparison, settings, immutable offsets and integrity hashes.
- `evidence/mutations.json`: machine-readable proof that source and token mutations fail.
- `evidence/rebuilt-runtime.hex`: post-substitution compiler output.

No explorer badge or trusted match flag is used as the proof: the local compiler output and RPC runtime are compared directly.
