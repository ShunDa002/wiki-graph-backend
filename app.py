import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# import uvicorn

from chat.routes import make_chat_router
from chat.service import ChatService
from config import Settings
from graph.graph_service import GraphService
from graph.routes import make_router
from wiki_store import WikiStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings()
graph_service = GraphService(settings)
wiki_store = WikiStore(settings.wiki_dir, settings.chat_source_folders)
chat_service = ChatService(
    store=wiki_store,
    model=settings.openrouter_model,
    top_k=settings.chat_top_k,
    max_page_chars=settings.chat_max_page_chars,
    max_total_context_chars=settings.chat_max_total_context_chars,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading graph and chat indexes")
    graph_service.get_graph()
    wiki_store.ensure_loaded()
    yield
    logger.info("LLM Wiki API shutting down")


app = FastAPI(
    title="LLM Wiki API",
    description="Read-only Wiki graph and English Q&A endpoints.",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Graph-API-Key"],
)

app.include_router(make_router(graph_service, settings))
app.include_router(make_chat_router(chat_service, settings))


@app.get("/health", tags=["system"])
def health() -> dict:
    # Lambda adapters may not always run ASGI lifespan initialization before a
    # probe. Make readiness explicit and idempotent instead of reporting 0.
    wiki_store.ensure_loaded()
    graph = graph_service.get_graph()
    return {
        "status": "ok",
        "language": "English",
        "model": settings.openrouter_model,
        "wiki_pages": len(wiki_store.documents),
        "wiki": wiki_store.diagnostics(),
        "graph": {
            "ready": True,
            "node_count": graph.metadata.nodeCount,
            "edge_count": graph.metadata.edgeCount,
            "source_version": graph.sourceVersion,
        },
    }


# if __name__ == "__main__":
#     uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True, log_level="debug")
