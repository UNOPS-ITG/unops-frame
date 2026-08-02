"""The application factory.

MIDDLEWARE EXECUTION ORDER IS THE REVERSE OF REGISTRATION ORDER. Starlette's
``add_middleware`` prepends, so the last registered runs first.

Desired request flow, outermost to innermost:

    CORS -> BodySizeLimit -> Correlation -> Timing -> [DevAuthBypass ->]
    IapAssertion -> router

so they are registered in exactly the opposite order below. Every position is
load-bearing:

* BodySizeLimit outermost   an oversized body is refused before auth does work
* Correlation next          so even a 401 log line carries the id (PM-7)
* Timing above auth         so duration includes JWKS fetch and JWT verify
* DevAuthBypass above IAP   it works by pre-setting state["auth"]; below IAP the
                            assertion check would already have run
* IapAssertion innermost    the last thing that can establish identity

The DevAuthBypass registration being both conditional and last expresses
"optional" and "outermost" in one line. That is neat and it is fragile:
anything added after that block silently breaks the outermost invariant.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import Depends, FastAPI
from starlette.middleware.cors import CORSMiddleware

from api.core.config import Settings, get_settings
from api.core.exceptions import APIException
from api.core.logging import configure_logging

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    import anyio.to_thread
    import httpx

    settings = get_settings()

    # TWO SEPARATE POOLS, and sizing one does not size the other — which is not
    # obvious from either API. anyio's limiter backs FastAPI's sync handlers;
    # asyncio.to_thread uses the loop's default executor, which at the Python
    # default is about five threads on a small container.
    anyio.to_thread.current_default_thread_limiter().total_tokens = settings.thread_limiter_tokens
    executor = ThreadPoolExecutor(
        max_workers=settings.to_thread_executor_workers, thread_name_prefix="to-thread"
    )
    asyncio.get_running_loop().set_default_executor(executor)

    # Constructed HERE and not at import time: anything loop-bound built at
    # import binds to the wrong loop, or to none. Same class of bug as the
    # Firestore AsyncClient.
    app.state.http = httpx.AsyncClient(timeout=10.0)

    try:
        yield
    finally:
        await app.state.http.aclose()
        executor.shutdown(wait=False)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application.

    ``settings`` is an explicit parameter rather than a global lookup so that
    the middleware is constructed against the *same* object the caller
    configured. Reaching for ``get_settings()`` inside each middleware instead
    means a test (or a second app in one process) silently gets production
    defaults, and the failure surfaces as an unrelated error on the first
    request rather than at construction.
    """
    settings = settings or get_settings()
    configure_logging(settings)

    # Checked here, at build time, and not only inside the middleware. Starlette
    # constructs middleware lazily on the first request, so a check that lives
    # only in ``__init__`` would let the process start, report healthy, and fail
    # every request afterwards — which is not "refusing to start".
    if not settings.iap_audience:
        raise RuntimeError(
            "iap_audience is not configured. Refusing to start: an empty audience "
            "would disable assertion validation entirely. Locally, set it to the "
            "Google OAuth client id that oauth2-proxy is configured with."
        )

    app = FastAPI(
        title="Frame API",
        version="0.0.0",
        lifespan=lifespan,
        # The global schema is not the product. Frame publishes an OpenAPI
        # document per Blueprint version, served from a version-keyed cache;
        # memoising one schema onto app.openapi_schema would freeze the first
        # one observed for the life of the process.
        docs_url=None,
        redoc_url=None,
    )

    # Routers read settings from here, never from the module-level cache.
    # Otherwise an app built with explicit settings has handlers answering from
    # a different object — which is how a health endpoint ends up reporting the
    # wrong state about itself.
    app.state.settings = settings

    _register_middleware(app, settings)
    _register_exception_handlers(app)
    _include_routers(app, settings)
    return app


def _register_middleware(app: FastAPI, settings: Settings) -> None:
    from api.middleware.body_limit import BodySizeLimitMiddleware
    from api.middleware.correlation import CorrelationMiddleware
    from api.middleware.iap_assertion import IapAssertionMiddleware
    from api.middleware.timing import TimingMiddleware

    app.add_middleware(IapAssertionMiddleware, settings=settings)

    if settings.dev_auth_bypass_enabled:
        # Imported only when the gate passes, so a deployed process contains no
        # bypass code path at all rather than one guarded by a runtime flag.
        from api.middleware.dev_auth_bypass import DevAuthBypassMiddleware

        app.add_middleware(DevAuthBypassMiddleware, settings=settings)

    app.add_middleware(TimingMiddleware)
    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(  # runs first, so a preflight never authenticates
        CORSMiddleware,
        allow_origins=[
            f"http://localhost:{settings.ports['frontend']}",
            f"http://localhost:{settings.ports['oauth_proxy']}",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _include_routers(app: FastAPI, settings: Settings) -> None:
    """The complete router surface. It does not grow per Blueprint, ever.

    ``{blueprintId}`` is a path parameter, not a module name. The fitness suite
    fails the build if a file appears in ``api/routers/`` that is not on its
    allowlist, which is what keeps "zero per-Blueprint code" demonstrable
    rather than aspirational.
    """
    from api.dependencies.auth import require_auth
    from api.routers import blueprints, corporate_data, docs, health, rows, views

    prefix = settings.api_prefix
    app.include_router(health.router, prefix=prefix)

    # Authenticated by default, at include time. Declaring the dependency per
    # route is fine when a human writes each route and unsafe when a generator
    # emits them: one missed decorator is a silently public endpoint.
    guarded: list[Any] = [Depends(require_auth)]
    app.include_router(blueprints.router, prefix=prefix, dependencies=guarded)
    # Views before rows: `/views/{id}/rows` must not be captured by the row
    # route's `/rows/{row_id}` pattern, which would resolve a view id as a row.
    app.include_router(views.router, prefix=prefix, dependencies=guarded)
    app.include_router(rows.router, prefix=prefix, dependencies=guarded)
    app.include_router(corporate_data.router, prefix=prefix, dependencies=guarded)
    app.include_router(docs.router, prefix=prefix, dependencies=guarded)


def _register_exception_handlers(app: FastAPI) -> None:
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    @app.exception_handler(APIException)
    async def _api_exception(_request: Request, exc: APIException) -> JSONResponse:
        # SHAPING ONLY. Denial auditing does not happen here. Hanging a 403
        # audit off this handler means scraping the resource type back out of
        # the URL, which is both the per-noun coupling Frame's generated routers
        # exist to remove and trivially routed around by raising a different
        # exception class. Frame audits inside the permission library at the
        # decision point, where the Blueprint, row, fields, principal and
        # deciding rule are already structured data.
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, **exc.extra},
            headers=exc.headers,
        )
