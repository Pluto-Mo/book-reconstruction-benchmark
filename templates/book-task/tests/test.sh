#!/bin/bash

set -euo pipefail

mkdir -p /logs/verifier

missing=0
for required in \
  /tests/gold/book_card.json \
  /tests/gold/discourse_card.json; do
  if [ ! -f "$required" ]; then
    echo "Missing finalized $required" >&2
    missing=1
  fi
done

if [ "$missing" -ne 0 ]; then
  exit 1
fi

# The production verifier has not been implemented yet. Fail loudly instead
# of emitting a syntactically valid zero score that could be mistaken for a
# completed benchmark run.
cat > /logs/verifier/verifier-status.json <<'JSON'
{
  "status": "verifier_not_implemented",
  "message": "Implement the Cognitive Structure and Discourse Reconstruction pipelines before running this task."
}
JSON

echo "Book reconstruction verifier is not implemented." >&2
exit 2

# A production implementation must write one of:
#   /logs/verifier/reward.txt   # one numeric value
#   /logs/verifier/reward.json  # an object whose values are all numeric
#
# Expected audit artifacts include:
#   reward-details.json
#   cognitive-judge-results.jsonl
#   authorial-edge-results.jsonl
#   editorial-probe-results.jsonl
#   verifier-status.json
#
# Put strings, versions, quotes, edge panels, perturbation text, reasons, and
# other audit metadata in those files rather than reward.json.
