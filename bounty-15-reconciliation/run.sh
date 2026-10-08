#!/bin/sh
set -eu
cd "$(dirname "$0")"
rm -rf fixtures/seed-150015
python generate.py --seed 150015 --lifecycles 120 --output fixtures/seed-150015
python verify.py > seeded-report.json
python -m unittest discover -s tests -v
python - <<'PY'
import json
r = json.load(open('seeded-report.json'))
assert r['status'] == 'verified'
assert r['fixture']['lifecycle_count'] >= 100
assert all(c['status'] == 'detected' for c in r['negative_checks'])
print(json.dumps({
    'status': r['status'],
    'lifecycles': r['fixture']['lifecycle_count'],
    'events': r['reconciliation']['event_count'],
    'fixed_block': r['reconciliation']['block'],
    'liabilities': r['reconciliation']['total_liabilities'],
    'balance': r['reconciliation']['token_balance'],
    'surplus': r['reconciliation']['surplus'],
    'negative_checks': len(r['negative_checks'])
}, sort_keys=True))
PY
