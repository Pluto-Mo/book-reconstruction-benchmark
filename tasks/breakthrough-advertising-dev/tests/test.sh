#!/bin/bash

set -euo pipefail

exec python3 /tests/scripts/harbor_cognitive_verifier.py \
  --allow-draft-card \
  --min-chars 6000 \
  --max-chars 8000
