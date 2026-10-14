# FastAPI Wiki Graph Backend

Read-only graph API for a synchronized Markdown wiki.

## Run

1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env`, then set paths and the rebuild key.
4. `uvicorn app:app --reload --workers 1`

## Graph API

- `GET /health`
- `GET /graph`
- `GET /graph/metadata`
- `GET /graph/node?id=concepts%2Fexample.md`
- `POST /graph/rebuild` with `X-Graph-API-Key`

The implementation validates that `WIKI_DIR` is under `WIKI_REPO_DIR`, never accepts filesystem paths from requests, reads only `.md` files under the configured wiki directory, constrains file size and node count, excludes self-links from edges, and writes snapshots outside the synchronized repository.

## Chat API

- `GET /random-topics`
- `POST /ask` (Server-Sent Events)
- `POST /reload-wiki` with `X-Graph-API-Key`
- `GET /health` returns combined graph and chat readiness

Set `OPENROUTER_API_KEY` and the chat-related values in `.env`. The chat index reads only the configured `CHAT_SOURCE_FOLDERS`, which default to `sources` and `concepts`. The graph continues to read all seven knowledge folders.
