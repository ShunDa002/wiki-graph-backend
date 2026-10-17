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

wiki_repo_dir = Path(os.environ["WIKI_REPO_DIR"]).resolve()
wiki_dir = Path(os.environ["WIKI_DIR"]).resolve()
source_folders = ("sources", "concepts")

for required_dir in (wiki_repo_dir, wiki_dir):
    if not required_dir.is_dir():
        print(f"ERROR: Required directory does not exist: {required_dir}", file=sys.stderr)
        raise SystemExit(1)

wiki_files = []
for folder in source_folders:
    folder_path = wiki_dir / folder
    folder_files = sorted(folder_path.rglob("*.md")) if folder_path.is_dir() else []
    print(f"{folder}: {len(folder_files)} Markdown files")
    if not folder_files:
        print(f"ERROR: Required Wiki source folder is missing or empty: {folder_path}", file=sys.stderr)
        raise SystemExit(1)
    wiki_files.extend(folder_files)

print(f"Verified Wiki directory: {wiki_dir}")
print(f"Chatbot Markdown file count: {len(wiki_files)}")
print("Sample chatbot Wiki files:")
for path in wiki_files[:20]:
    print(path.relative_to(wiki_dir))
PY

EXPOSE 8080

CMD ["lambda_handler.handler"]
