from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response

from .models import WikiGraph, WikiNode


def make_router(service, settings):
    router = APIRouter(tags=["graph"])

    def authorize_rebuild(
        x_graph_api_key: str | None = Header(default=None),
    ) -> None:
        if (
            not settings.graph_rebuild_secret_key
            or x_graph_api_key != settings.graph_rebuild_secret_key
        ):
            raise HTTPException(status_code=403, detail="Forbidden")

    @router.get(
        "/graph",
        response_model=WikiGraph,
        response_model_exclude_none=True,
    )
    def graph(response: Response):
        result = service.get_graph()
        response.headers["Cache-Control"] = "private, max-age=60"
        return result

    @router.get("/graph/metadata")
    def metadata():
        result = service.get_graph()
        return {
            "schemaVersion": result.schemaVersion,
            "generatedAt": result.generatedAt,
            "sourceVersion": result.sourceVersion,
            "metadata": result.metadata,
        }

    @router.get(
        "/graph/node",
        response_model=WikiNode,
        response_model_exclude_none=True,
    )
    def node(id: str = Query(...)):
        result = next(
            (node for node in service.get_graph().nodes if node.id == id),
            None,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Node not found")
        return result

    @router.post(
        "/graph/rebuild",
        response_model=WikiGraph,
        response_model_exclude_none=True,
        dependencies=[Depends(authorize_rebuild)],
    )
    def rebuild():
        return service.build_graph()

    return router
