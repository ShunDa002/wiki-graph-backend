import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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
    version="1.2.0",
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


@app.get("/health/live", tags=["system"])
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health", tags=["system"])
def health() -> dict:
    try:
        wiki_store.ensure_loaded()
        graph = graph_service.get_graph()
    except Exception as exc:
        logger.exception("Readiness check failed")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "message": "Application data could not be initialized.",
            },
        ) from exc

    diagnostics = wiki_store.diagnostics()
    if diagnostics["document_count"] == 0 or diagnostics["concept_count"] == 0:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "message": "Wiki documents or concepts are unavailable.",
                "wiki_pages": diagnostics["document_count"],
                "concept_count": diagnostics["concept_count"],
            },
        )

    return {
        "status": "ok",
        "language": "English",
        "wiki_pages": diagnostics["document_count"],
        "concept_count": diagnostics["concept_count"],
        "source_count": diagnostics["source_count"],
        "wiki": diagnostics,
        "graph": {
            "ready": True,
            "node_count": graph.metadata.nodeCount,
            "edge_count": graph.metadata.edgeCount,
            "source_version": graph.sourceVersion,
        },
    }
