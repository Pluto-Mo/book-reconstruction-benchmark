#!/bin/bash

set -euo pipefail

mkdir -p /logs/verifier

if [ ! -f /tests/gold/book_card.json ]; then
  echo "Missing finalized /tests/gold/book_card.json" >&2
  exit 1
fi

# V1 verifier wiring is intentionally left for design work. It will combine:
# 1) deterministic hard-constraint checks;
# 2) evidence-first binary checks for cognitive atoms;
# 3) anchored checks for genericity resistance and authorial organization.
echo '{"reward": 0.0, "status": "verifier_not_implemented"}' > /logs/verifier/reward.json
