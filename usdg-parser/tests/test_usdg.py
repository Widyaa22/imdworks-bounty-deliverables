import random
import unittest
from pathlib import Path

from cases import INVALID_INPUTS
from reference import reference_parse
from verify import build_results
from usdg import ParseError, format_usdg, parse_usdg


class ParserTests(unittest.TestCase):
    def test_parses_whole_and_fraction_to_microunits(self):
        self.assertEqual(parse_usdg("12.3456"), 12_345_600)

    def test_formats_canonical_six_decimal_display(self):
        self.assertEqual(format_usdg(12_345_600), "12.345600")

    def test_accepts_explicit_ascii_grammar(self):
        cases = {
            "0": 0, "0.0": 0, "0.000001": 1, "1": 1_000_000,
            "1.2": 1_200_000, "999999999999.999999": 999_999_999_999_999_999,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_usdg(text), expected)

    def test_rejects_hand_picked_ambiguous_or_lossy_inputs(self):
        self.assertGreaterEqual(len(INVALID_INPUTS), 30)
        for text in INVALID_INPUTS:
            with self.subTest(text=repr(text)):
                with self.assertRaises(ParseError):
                    parse_usdg(text)

    def test_rejects_non_strings_and_invalid_formatter_values(self):
        for value in (None, 1, b"1", 1.0):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ParseError)):
                    parse_usdg(value)
        for value in (-1, 1.0, True, "1"):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    format_usdg(value)

    def test_seeded_generated_cases_match_independent_reference_and_round_trip(self):
        rng = random.Random(0x55D6_0009)
        for _ in range(100_000):
            units = rng.randrange(0, 10**24)
            canonical = format_usdg(units)
            self.assertEqual(parse_usdg(canonical), units)
            self.assertEqual(reference_parse(canonical), units)

            # Also exercise accepted non-canonical precision (1..6 places).
            places = rng.randrange(1, 7)
            whole = rng.randrange(0, 10**18)
            fractional = rng.randrange(0, 10**places)
            text = f"{whole}.{fractional:0{places}d}"
            expected = whole * 1_000_000 + fractional * 10 ** (6 - places)
            self.assertEqual(parse_usdg(text), expected)
            self.assertEqual(reference_parse(text), expected)
            self.assertEqual(parse_usdg(format_usdg(expected)), expected)

    def test_machine_readable_results_include_counts_and_float_counterexamples(self):
        result = build_results(case_count=100_000)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["seed"], 0x55D6_0009)
        self.assertEqual(result["generated_cases"], 100_000)
        self.assertGreaterEqual(result["hand_picked_invalid_cases"], 30)
        self.assertGreaterEqual(len(result["floating_point_counterexamples"]), 3)
        for example in result["floating_point_counterexamples"]:
            self.assertNotEqual(example["float_microunits"], example["exact_microunits"])

    def test_one_command_runner_and_documentation_exist(self):
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / "run.sh").is_file())
        readme = (root / "README.md").read_text(encoding="utf-8")
        for phrase in ("Grammar", "Canonical", "integer", "100,000", "round-trip"):
            self.assertIn(phrase, readme)


if __name__ == "__main__":
    unittest.main()
