#!/bin/bash

set -euo pipefail

if [ ! -f /solution/reference_submission.md ]; then
  echo "Missing /solution/reference_submission.md; add a reviewed oracle answer before running the oracle agent." >&2
  exit 1
fi

cp /solution/reference_submission.md /app/submission.md
