from __future__ import annotations

import random
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from .models import ChatRequest


def make_chat_router(chat_service, settings):
    router = APIRouter(tags=["chat"])

    def authorize_reload(
        x_graph_api_key: str | None = Header(default=None),
    ) -> None:
        expected = settings.wiki_reload_secret_key or settings.graph_rebuild_secret_key
        if not expected or x_graph_api_key != expected:
            raise HTTPException(status_code=403, detail="Forbidden")

    @router.get("/random-topics")
    async def random_topics() -> list[str]:
        concepts = chat_service.store.concepts_docs
        sample_size = min(3, len(concepts))
        return [str(item["title"]) for item in random.sample(concepts, k=sample_size)]

    @router.post("/ask", response_class=StreamingResponse)
    async def ask_question(request: ChatRequest) -> StreamingResponse:
        question = request.user_input.strip()
        thread_id = request.thread_id.strip()
        search_results = await run_in_threadpool(
            chat_service.store.search,
            question,
            settings.chat_top_k,
        )
        return StreamingResponse(
            chat_service.answer_stream(question, search_results, thread_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post(
        "/reload-wiki",
        dependencies=[Depends(authorize_reload)],
    )
    async def reload_wiki() -> dict[str, Any]:
        await run_in_threadpool(chat_service.store.load)
        return {
            "status": "reloaded",
            "language": "English",
            "wiki_pages": len(chat_service.store.documents),
        }

    return router
