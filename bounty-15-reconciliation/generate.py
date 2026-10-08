#!/usr/bin/env python3
"""Write a deterministic event journal, state snapshot and metadata."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from generator import generate_fixture


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=150015)
    parser.add_argument("--lifecycles", type=int, default=120)
    parser.add_argument("--output", type=Path, default=Path("fixtures/seed-150015"))
    args = parser.parse_args()
    events, snapshot, metadata = generate_fixture(args.seed, args.lifecycles)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "events.jsonl").write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events))
    (args.output / "snapshot.json").write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), **metadata}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
