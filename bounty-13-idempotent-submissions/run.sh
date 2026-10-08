#!/bin/sh
set -eu
cd "$(dirname "$0")"
rm -rf artifacts
python3 -m unittest discover -s tests -v
python3 verify.py --directory artifacts --requests 200 --wallets 10 --seed 13
