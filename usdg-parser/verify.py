"""Deterministic verification runner producing machine-readable JSON."""

import json
import random
import sys
from pathlib import Path

from cases import INVALID_INPUTS
from reference import reference_parse
from usdg import ParseError, format_usdg, parse_usdg

SEED = 0x55D6_0009
FLOAT_INPUTS = (
    "9007199254.740993",
    "999999999999.999999",
    "100000000000000001.000001",
    "123456789012345678.123456",
)


def build_results(case_count: int = 100_000) -> dict:
    for text in INVALID_INPUTS:
        try:
            parse_usdg(text)
        except ParseError:
            pass
        else:
            raise AssertionError(f"invalid input accepted: {text!r}")

    rng = random.Random(SEED)
    for _ in range(case_count):
        units = rng.randrange(0, 10**24)
        text = format_usdg(units)
        assert parse_usdg(text) == units
        assert reference_parse(text) == units

        places = rng.randrange(1, 7)
        whole = rng.randrange(0, 10**18)
        fraction = rng.randrange(0, 10**places)
        accepted = f"{whole}.{fraction:0{places}d}"
        expected = whole * 1_000_000 + fraction * 10 ** (6 - places)
        assert parse_usdg(accepted) == expected
        assert reference_parse(accepted) == expected
        assert parse_usdg(format_usdg(expected)) == expected

    examples = []
    for text in FLOAT_INPUTS:
        exact = parse_usdg(text)
        via_float = int(float(text) * 1_000_000)
        if via_float != exact:
            examples.append({
                "input": text,
                "exact_microunits": exact,
                "float_microunits": via_float,
                "error_microunits": via_float - exact,
            })
    assert len(examples) >= 3
    return {
        "status": "pass",
        "seed": SEED,
        "generated_cases": case_count,
        "accepted_forms_checked_per_case": 2,
        "round_trips_checked": case_count * 2,
        "reference_comparisons": case_count * 2,
        "hand_picked_invalid_cases": len(INVALID_INPUTS),
        "floating_point_counterexamples": examples,
        "arithmetic": "integer-only production parser/formatter",
    }


def main() -> int:
    output = Path("results.json")
    result = build_results()
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
