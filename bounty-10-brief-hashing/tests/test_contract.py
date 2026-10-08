import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))


class ContractTests(unittest.TestCase):
    def test_canonical_field_order_and_utf8(self):
        from brief_hash import canonicalize
        brief = {
            "deadline": "d", "token": "t", "reward": "1",
            "criteria": "café", "description": "line1\r\nline2", "title": "x",
        }
        self.assertEqual(
            canonicalize(brief),
            '{"title":"x","description":"line1\\r\\nline2","criteria":"café","reward":"1","token":"t","deadline":"d"}'.encode(),
        )

    def test_keccak_reference(self):
        from brief_hash import keccak256
        self.assertEqual(keccak256(b"").hex(), "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470")

    def test_rejects_non_exact_schema(self):
        from brief_hash import canonicalize, BriefError
        invalid = [
            {},
            {"title":"","description":"","criteria":"","reward":"","token":"","deadline":"","extra":""},
            {"title":"","description":"","criteria":[],"reward":"","token":"","deadline":""},
            {"title":"","description":"","criteria":"","reward":1,"token":"","deadline":""},
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(BriefError):
                canonicalize(value)

    def test_js_matches_python_vectors(self):
        from brief_hash import canonicalize, hash_brief
        vectors = json.loads((ROOT / "vectors.json").read_text())
        self.assertGreaterEqual(len(vectors["accepted"]), 50)
        proc = subprocess.run(
            ["node", str(ROOT / "javascript" / "cli.js")],
            input=json.dumps([v["input"] for v in vectors["accepted"]], ensure_ascii=False),
            text=True, capture_output=True, check=True,
        )
        js_results = json.loads(proc.stdout)
        for vector, js_result in zip(vectors["accepted"], js_results, strict=True):
            self.assertEqual(canonicalize(vector["input"]).hex(), vector["canonical_hex"])
            self.assertEqual(hash_brief(vector["input"]), vector["keccak256"])
            self.assertEqual(js_result, {"canonical_hex": vector["canonical_hex"], "keccak256": vector["keccak256"]})

    def test_all_rejection_vectors_rejected_in_both_languages(self):
        from brief_hash import canonicalize, BriefError
        vectors = json.loads((ROOT / "vectors.json").read_text())
        inputs = [v["input"] for v in vectors["rejected"]]
        for value in inputs:
            with self.assertRaises(BriefError):
                canonicalize(value)
        proc = subprocess.run(
            ["node", str(ROOT / "javascript" / "cli.js")], input=json.dumps(inputs),
            text=True, capture_output=True, check=True,
        )
        self.assertEqual(json.loads(proc.stdout), [{"error": "Error"}] * len(inputs))

    def test_rejects_unpaired_surrogates_in_both_languages(self):
        from brief_hash import canonicalize, BriefError
        value = {"title":"\ud800","description":"","criteria":"","reward":"","token":"","deadline":""}
        with self.assertRaises(BriefError):
            canonicalize(value)
        proc = subprocess.run(
            ["node", str(ROOT / "javascript" / "cli.js")], input=json.dumps([value]),
            text=True, capture_output=True, check=True,
        )
        self.assertEqual(json.loads(proc.stdout), [{"error": "Error"}])

    def test_current_immutable_brief_fixture(self):
        from brief_hash import hash_brief
        fixture = json.loads((ROOT / "historical" / "bounty-10.json").read_text())
        self.assertEqual(hash_brief(fixture["brief"]), fixture["canonical_hash"])


if __name__ == "__main__":
    unittest.main()
