from fastapi import FastAPI
from fastapi.routing import APIRoute, RouteContext, iter_route_contexts


def api_routes(app: FastAPI) -> list[RouteContext]:
    """Every API route in `app`, with included routers' prefixes and tags applied.

    `app.routes` alone won't do: FastAPI keeps each included router as one opaque
    entry, so a loop over it sees no API routes at all.
    """
    routes = [
        context
        for context in iter_route_contexts(app.routes)
        if isinstance(context.original_route, APIRoute)
    ]
    assert routes, "found no API routes: has FastAPI changed how it stores them?"
    return routes
