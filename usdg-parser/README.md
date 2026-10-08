# Exact USDG six-decimal parser

A Python-standard-library-only parser, formatter, and deterministic verification suite for a non-negative token with six decimal places. Production conversion uses integer arithmetic only; it never converts token values through binary floating point.

## Grammar

Accepted input is exactly:

```text
(0|[1-9][0-9]*)(\.[0-9]{1,6})?
```

Every symbol is ASCII. The whole part is mandatory. Leading zeroes are forbidden except for the single whole part `0`. A decimal point, when present, must have one through six digits. There are no signs, whitespace, grouping separators, exponents, underscores, or Unicode digits/lookalikes. Values are non-negative and arbitrary precision, bounded only by available memory.

Examples accepted: `0`, `0.1`, `1`, `12.3456`, `999999999999.999999`.

## Canonical display

`format_usdg` always emits a base-10 whole part with no leading zeroes and exactly six fractional digits, such as `12.345600`. Thus canonical text has grammar `(0|[1-9][0-9]*)\.[0-9]{6}`. Multiple accepted spellings can represent the same value (`1`, `1.0`, and `1.000000`), but each value has one canonical display.

The internal value is an integer count of microunits (`1 USDG = 1,000,000 microunits`). Parsing pads a fractional integer by powers of ten; formatting uses integer `divmod`. This avoids rounding and precision loss.

## Verification

Run everything with one command:

```sh
./run.sh
```

It runs the unit suite and then writes `results.json`. Verification includes:

- 38 hand-picked invalid edge cases, including leading-zero ambiguities, signs, whitespace, exponents, more than six fractional digits, and Unicode lookalikes.
- 100,000 deterministic generated iterations using seed `0x55D60009`; each iteration checks a canonical and a variable-precision accepted form.
- Comparison with `reference.py`, an independently implemented character-scanning parser that shares no regex or parsing logic with production.
- The round-trip property `parse_usdg(format_usdg(n)) == n` for every generated non-negative integer value, plus normalization round trips for generated accepted values.
- At least three concrete cases where `int(float(text) * 1_000_000)` differs from exact parsing.

### Round-trip proof

For any non-negative integer microunit value `n`, Euclidean division gives unique integers `q, r = divmod(n, 1_000_000)` with `0 <= r < 1,000,000`. Formatting writes `q`, a point, and exactly six digits for `r`. Parsing multiplies `q` by `1,000,000` and adds those six digits as `r`, yielding `q * 1,000,000 + r = n`. Therefore every formatter output is accepted and round-trips exactly.

For any accepted text, its 1–6 fractional digits denote an integer multiplied by `10^(6-length)`, so its parsed result is also an integer microunit value. Formatting and parsing that result therefore preserves it by the argument above.

## Files

- `usdg.py` — production parser/formatter.
- `reference.py` — independent reference parser.
- `tests/test_usdg.py` — unit, edge, generated, and artifact tests.
- `verify.py` — deterministic verification and JSON results generator.
- `run.sh` — one-command runner.
- `results.json` — generated machine-readable evidence.
