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

# Copy application code and the Wiki bundled in this repository.
COPY . ${LAMBDA_TASK_ROOT}

# Validate all required runtime files during image construction.
RUN set -eux; \
    test -f "${LAMBDA_TASK_ROOT}/lambda_handler.py"; \
    test -f "${LAMBDA_TASK_ROOT}/app.py"; \
    test -d "${WIKI_REPO_DIR}"; \
    test -d "${WIKI_DIR}"; \
    WIKI_FILE_COUNT="$( \
        find "${WIKI_DIR}" \
            -type f \
            \( -iname '*.md' -o -iname '*.markdown' \) \
            -print \
        | wc -l \
        | tr -d '[:space:]' \
    )"; \
    test "${WIKI_FILE_COUNT}" -gt 0; \
    echo "Verified Wiki directory: ${WIKI_DIR}"; \
    echo "Markdown Wiki file count: ${WIKI_FILE_COUNT}"; \
    mkdir -p /tmp/generated

# Used by the Lambda Runtime Interface Emulator during local execution.
EXPOSE 8080

CMD ["lambda_handler.handler"]