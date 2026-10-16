# syntax=docker/dockerfile:1.7

FROM public.ecr.aws/lambda/python:3.12

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WIKI_REPO_DIR=/var/task/data/source-repo \
    WIKI_DIR=/var/task/data/source-repo/wiki \
    GRAPH_OUTPUT_PATH=/tmp/generated/graph.json \
    GRAPH_WRITE_SNAPSHOT=false

# Install dependencies separately to preserve Docker layer caching.
COPY requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install \
        --only-binary=:all: \
        --requirement ${LAMBDA_TASK_ROOT}/requirements.txt \
        --target ${LAMBDA_TASK_ROOT} \
    && rm -rf /root/.cache/pip

# Copy application code and bundled Wiki content.
COPY . ${LAMBDA_TASK_ROOT}

# Validate the application and bundled Wiki without relying on
# optional Linux utilities such as find/findutils.
RUN set -eux; \
    test -f "${LAMBDA_TASK_ROOT}/lambda_handler.py"; \
    test -f "${LAMBDA_TASK_ROOT}/app.py"; \
    test -d "${WIKI_REPO_DIR}"; \
    test -d "${WIKI_DIR}"; \
    WIKI_FILE_COUNT="$( \
        python -c ' \
from pathlib import Path; \
import os; \
wiki_dir = Path(os.environ["WIKI_DIR"]); \
print(sum( \
    1 for path in wiki_dir.rglob("*") \
    if path.is_file() \
    and path.suffix.lower() in {".md", ".markdown"} \
))' \
    )"; \
    test "${WIKI_FILE_COUNT}" -gt 0; \
    echo "Verified Wiki directory: ${WIKI_DIR}"; \
    echo "Markdown Wiki file count: ${WIKI_FILE_COUNT}"; \
    mkdir -p /tmp/generated

EXPOSE 8080

CMD ["lambda_handler.handler"]