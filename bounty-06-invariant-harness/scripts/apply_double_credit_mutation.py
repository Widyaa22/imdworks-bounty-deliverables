#!/usr/bin/env python3
"""Negative control: make award credit the winner twice."""
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "src" / "IMDWorksEscrow.sol"
s = p.read_text()
needle = "        _credit(winner, b.reward);\n        emit BountyAwarded"
replacement = "        _credit(winner, b.reward);\n        claimable[winner] += b.reward; // deliberate accounting bug\n        totalClaimable += b.reward;\n        emit BountyAwarded"
if s.count(needle) != 1:
    raise SystemExit("expected award credit site not found exactly once")
p.write_text(s.replace(needle, replacement))
