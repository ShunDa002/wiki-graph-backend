# syntax=docker/dockerfile:1.7

FROM public.ecr.aws/lambda/python:3.12

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GRAPH_OUTPUT_PATH=/tmp/generated/graph.json \
    GRAPH_WRITE_SNAPSHOT=false

# Install application dependencies into Lambda's task root.
COPY requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt

RUN python -m pip install --upgrade pip && \
    python -m pip install \
        --only-binary=:all: \
        --requirement ${LAMBDA_TASK_ROOT}/requirements.txt \
        --target ${LAMBDA_TASK_ROOT}

# Copy the FastAPI application, Lambda handler, graph modules,
# chat modules, and bundled Wiki content.
COPY . ${LAMBDA_TASK_ROOT}

# Lambda's Runtime Interface Emulator listens internally on port 8080
# when the container is run locally.
EXPOSE 8080

# Invoke the Mangum handler, not app.py or Uvicorn.
CMD ["lambda_handler.handler"]