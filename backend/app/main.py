from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.ai.extractors import ExtractionError
from app.config import settings
from app.database import engine, Base
# Import all models to ensure metadata is populated
import app.models  # noqa: F401
from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.workspaces import router as workspaces_router
from app.api.v1.tickets import router as tickets_router
from app.api.v1.portal import router as portal_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.ai import router as ai_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.audit import router as audit_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: dispose engine
    await engine.dispose()

app = FastAPI(
    title="SupportPilot AI API",
    description="Multi-tenant AI Customer Support SaaS with Human-in-the-Loop Approval Safeguards",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Domain validation errors from upload/document parsing keep their HTTP semantics
# while still returning the consistent {"detail": "..."} error shape.
@app.exception_handler(ExtractionError)
async def extraction_error_handler(request: Request, exc: ExtractionError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

# Exception handler to prevent stack trace leaks
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
    )

# Routers
app.include_router(auth_router)
app.include_router(workspaces_router)
app.include_router(tickets_router)
app.include_router(portal_router)
app.include_router(knowledge_router)
app.include_router(ai_router)
app.include_router(approvals_router)
app.include_router(audit_router)
app.include_router(analytics_router)

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app": "SupportPilot AI",
        "version": "1.0.0",
        "demo_mode": settings.DEMO_MODE,
        "llm_provider": settings.LLM_PROVIDER,
    }
