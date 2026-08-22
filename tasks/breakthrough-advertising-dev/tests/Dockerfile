FROM python:3.12-slim

ARG JSONSCHEMA_VERSION=4.25.1
ARG LITELLM_VERSION=1.97.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir \
    "jsonschema==${JSONSCHEMA_VERSION}" \
    "litellm==${LITELLM_VERSION}"

WORKDIR /app

# A separate Harbor verifier is built with tests/ as its Docker context.
COPY . /tests/
RUN chmod +x \
    /tests/test.sh \
    /tests/provider_adapter.py \
    /tests/scripts/harbor_cognitive_verifier.py \
    /tests/scripts/discourse_semantic_runtime.py
