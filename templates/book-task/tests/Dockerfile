FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

# Separate verifier environments are built from the tests/ directory.
# Harbor does not upload tests/ into that environment at runtime, so the
# verifier image must contain /tests/test.sh and all hidden rubric files.
COPY . /tests/
RUN chmod +x /tests/test.sh
