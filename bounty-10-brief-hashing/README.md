# IMD Works canonical brief hashing (v1)

This directory defines a byte-level contract for new brief commitments and preserves the observed Bounty #10 record as historical evidence. It uses only Python and Node.js standard libraries.

## One-command verification

```sh
./test.sh
```

The command checks 62 accepted cross-language vectors, 9 rejected vectors, canonical byte equality, Keccak-256 equality, the historical fixture, and known Keccak reference digests.

## Canonicalization contract

Input MUST be a JSON object with exactly these six own keys (input key order is ignored):

1. `title`
2. `description`
3. `criteria`
4. `reward`
5. `token`
6. `deadline`

Every value MUST be a string. Output is the UTF-8 encoding of a compact JSON object in the order above, with JSON string escaping and no insignificant whitespace. The digest is legacy Ethereum Keccak-256 of those exact bytes, rendered as `0x` plus 64 lowercase hexadecimal digits. It is **not** standardized SHA3-256.

## Rejection rules

Reject before hashing:

- non-object roots, including null and arrays;
- a missing canonical field;
- any additional field, including hostile nested keys;
- any non-string field value (number, boolean, null, object, or array);
- malformed JSON or text that cannot be decoded as Unicode by the caller's JSON decoder;
- JavaScript strings containing an unpaired UTF-16 surrogate (well-formed JSON can spell one with an escape, but it is not a Unicode scalar value).

No coercion is permitted. In particular numeric `1` is rejected; reward strings `"1"`, `"1.0"`, `"01"`, and `"1e0"` are distinct accepted values. This rule avoids Python/JavaScript numeric formatting and precision differences.

## Deliberate non-normalization

Canonicalization preserves committed content rather than editing its meaning:

- LF, CRLF, and CR are different byte sequences and produce different hashes.
- Unicode NFC/NFD/NFKC normalization is not performed. `"café"` and `"café"` can look alike but hash differently.
- Leading/trailing whitespace, case, timestamp spelling, and decimal spelling are preserved.
- Empty strings are valid for every field.
- JSON-looking, HTML, shell, and nested-object-looking **strings** remain strings and are accepted. Actual nested structures are rejected.

A client establishes **byte equality** by comparing `canonicalize(a)` and `canonicalize(b)` byte-for-byte, or their Keccak commitments. Semantic similarity (same visual glyphs, equivalent times, equivalent decimal values, normalized line endings) is an application-level comparison and MUST NOT be used to validate a commitment.

## Historical verification

`historical/bounty-10.json` is a frozen capture of the six source strings, the platform's observed commitment, and this specification's canonical commitment. The observed platform hash is `0x6e530a…d62d`; applying this new explicit v1 contract to the captured fields produces `0xcaf0ea…e9db7`. The mismatch is retained rather than rewritten: it proves the historical platform commitment used a different or undocumented preimage.

Immutable historical briefs remain verifiable only when the exact historical bytes (or an unambiguous historical serialization/version) are retained. New records should store `{algorithm: "keccak256", serialization: "imdworks-brief-v1", hash: ...}`. Never recompute an old record under a newly introduced serialization and replace its commitment. Verify legacy records using their original version/preimage; if that information is unavailable, report them as unverifiable under v1 rather than claiming semantic equality.

## Files

- `python/brief_hash.py` — independent Python implementation and Keccak permutation.
- `javascript/brief-hash.js` — independent JavaScript implementation and Keccak permutation.
- `vectors.json` — 62 accepted vectors with canonical bytes and digests, plus rejected inputs.
- `generate_vectors.py` — deterministic fixture generator.
- `historical/bounty-10.json` — immutable Bounty #10 capture and both commitments.
- `tests/test_contract.py` — cross-language and rejection tests.
