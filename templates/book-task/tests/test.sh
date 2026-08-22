#!/bin/bash

set -euo pipefail

mkdir -p /logs/verifier

if [ ! -f /tests/gold/book_card.json ]; then
  echo "Missing finalized /tests/gold/book_card.json" >&2
  exit 1
fi

# The production verifier has not been implemented yet. Fail loudly instead
# of emitting a syntactically valid zero score that could be mistaken for a
# completed benchmark run.
cat > /logs/verifier/verifier-status.json <<'JSON'
{
  "status": "verifier_not_implemented",
  "message": "Implement the Evidence Locator, Relation Adjudicator, Quote Validator, and Graph Aggregator before running this task."
}
JSON

echo "Book reconstruction verifier is not implemented." >&2
exit 2

# A production implementation must write one of:
#   /logs/verifier/reward.txt   # one numeric value
#   /logs/verifier/reward.json  # an object whose values are all numeric
# Put strings, versions, reasons, and other audit metadata in separate files
# such as verifier-status.json or reward-details.json.
