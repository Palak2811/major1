from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.services.career  # noqa: F401  (registers background jobs)
import app.services.generation  # noqa: F401
import app.services.judging  # noqa: F401
import app.services.rag  # noqa: F401
from app.core.config import get_settings
from app.routers import (
    ai,
    auth,
    career,
    companies,
    kb,
    progress,
    questions,
    study,
    submissions,
    tests,
    topics,
    users,
)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI-Powered Adaptive Placement Preparation Platform — REST API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

for r in (auth.router, users.router, topics.router, questions.router, companies.router,
          study.router, tests.router, progress.router, submissions.router, ai.router,
          kb.router, career.router):
    app.include_router(r, prefix="/api/v1")


@app.get("/api/health", tags=["meta"])
async def health():
    return {"status": "ok"}
