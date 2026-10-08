#!/usr/bin/env python3
"""Run the offline benchmark and emit its deterministic JSON report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from prompt_boundary import load_fixtures, run_benchmark

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, default=ROOT / "fixtures.json")
    parser.add_argument("--output", type=Path, default=ROOT / "report.json")
    args = parser.parse_args()
    report = run_benchmark(load_fixtures(args.fixtures))
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["requirements_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
