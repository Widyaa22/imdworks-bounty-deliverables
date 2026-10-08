#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="${HOME}/.foundry/bin:${PATH}"
cd "$ROOT"
mkdir -p artifacts
{
  echo "UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  forge --version
  cast --version
  solc --version 2>/dev/null || true
  git -C lib/forge-std rev-parse HEAD
  git -C lib/openzeppelin-contracts rev-parse HEAD
  sha256sum src/IMDWorksEscrow.sol
} | tee artifacts/tool-versions.txt

# RED: prove the harness rejects an intentionally broken accounting mutation.
cp src/IMDWorksEscrow.sol artifacts/IMDWorksEscrow.sol.clean
restore() { cp artifacts/IMDWorksEscrow.sol.clean src/IMDWorksEscrow.sol; }
trap restore EXIT
python3 scripts/apply_double_credit_mutation.py
set +e
forge test --match-path test/IMDWorksEscrow.invariant.t.sol \
  --fuzz-seed 0x494d44574f524b532d424f554e54592d3036 -vv \
  > artifacts/red-mutation.txt 2>&1
status=$?
set -e
restore
trap - EXIT
if [[ $status -eq 0 ]]; then
  echo "ERROR: deliberately broken double-credit mutation survived" >&2
  exit 1
fi
if ! grep -qE 'invariant_balanceCoversIndependentLiabilities|invariant_terminalBountyCannotPayTwice|FAIL' artifacts/red-mutation.txt; then
  echo "ERROR: mutation failed for an unrelated reason" >&2
  exit 1
fi
echo "RED: mutation detected as expected (forge exit $status)."

# GREEN: restore the exact verified source and require the full campaign to pass.
forge test --match-path test/IMDWorksEscrow.invariant.t.sol \
  --fuzz-seed 0x494d44574f524b532d424f554e54592d3036 -vv \
  2>&1 | tee artifacts/green.txt

echo "GREEN: clean 1000x100 invariant campaign passed."
echo "PASS: RED then GREEN verification completed."
