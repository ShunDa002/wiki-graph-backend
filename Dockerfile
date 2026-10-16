# syntax=docker/dockerfile:1.7

FROM public.ecr.aws/lambda/python:3.12

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WIKI_REPO_DIR=/var/task/data/source-repo \
    WIKI_DIR=/var/task/data/source-repo/wiki \
    GRAPH_OUTPUT_PATH=/tmp/generated/graph.json \
    GRAPH_WRITE_SNAPSHOT=false

COPY requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install \
        --only-binary=:all: \
        --requirement ${LAMBDA_TASK_ROOT}/requirements.txt \
        --target ${LAMBDA_TASK_ROOT} \
    && rm -rf /root/.cache/pip

COPY . ${LAMBDA_TASK_ROOT}

RUN set -eux; \
    test -f "${LAMBDA_TASK_ROOT}/lambda_handler.py"; \
    test -f "${LAMBDA_TASK_ROOT}/app.py"; \
    test -d "${WIKI_REPO_DIR}"; \
    test -d "${WIKI_DIR}"; \
    mkdir -p /tmp/generated

RUN python <<'PY'
import os
import sys
from pathlib import Path

wiki_dir = Path(os.environ["WIKI_DIR"])
wiki_files = sorted(
    path
    for path in wiki_dir.rglob("*")
    if path.is_file() and path.suffix.lower() in {".md", ".markdown"}
)

print(f"Verified Wiki directory: {wiki_dir}")
print(f"Markdown Wiki file count: {len(wiki_files)}")

if not wiki_files:
    print(f"ERROR: No Markdown Wiki files found under: {wiki_dir}", file=sys.stderr)
    raise SystemExit(1)

print("Sample Wiki files:")
for path in wiki_files[:20]:
    print(path.relative_to(wiki_dir))
PY

EXPOSE 8080

CMD ["lambda_handler.handler"]
