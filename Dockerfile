# syntax=docker/dockerfile:1.7

ARG TARGETPLATFORM

FROM --platform=${TARGETPLATFORM} public.ecr.aws/lambda/python:3.12

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WIKI_REPO_DIR=/var/task/data/source-repo \
    WIKI_DIR=/var/task/data/source-repo/wiki \
    GRAPH_OUTPUT_PATH=/tmp/generated/graph.json \
    GRAPH_WRITE_SNAPSHOT=false

# Install dependencies separately so dependency layers can be cached.
COPY requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install \
        --only-binary=:all: \
        --requirement ${LAMBDA_TASK_ROOT}/requirements.txt \
        --target ${LAMBDA_TASK_ROOT} \
    && rm -rf /root/.cache/pip

# Copy the application and bundled Wiki content.
COPY . ${LAMBDA_TASK_ROOT}

# Fail the image build immediately if required Lambda files or Wiki
# content were excluded by checkout, .gitmodules, or .dockerignore.
RUN set -eux; \
    test -f "${LAMBDA_TASK_ROOT}/lambda_handler.py"; \
    test -f "${LAMBDA_TASK_ROOT}/app.py"; \
    test -d "${WIKI_REPO_DIR}"; \
    test -d "${WIKI_DIR}"; \
    WIKI_FILE_COUNT="$(find "${WIKI_DIR}" -type f | wc -l | tr -d '[:space:]')"; \
    test "${WIKI_FILE_COUNT}" -gt 0; \
    echo "Verified Wiki directory: ${WIKI_DIR}"; \
    echo "Wiki file count: ${WIKI_FILE_COUNT}"; \
    mkdir -p /tmp/generated

# AWS Lambda Runtime Interface Emulator listens on 8080 when the
# container is executed locally.
EXPOSE 8080

# lambda_handler.py must contain:
# handler = Mangum(app, lifespan="off")
CMD ["lambda_handler.handler"]