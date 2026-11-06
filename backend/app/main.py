"""The FastAPI application: routers, CORS, health, and lifecycle hooks."""
import logging

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from .bootstrap import on_startup
from .config import settings
from .db import client, db, utcnow
from .routers import auth, billing, community, contribute, evals, reports, share

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

app = FastAPI(title="LocalIQ - Neighbourhood Quality Reports")

for router in (auth, reports, share, community, contribute, billing, evals):
    app.include_router(router.router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/")
async def root():
    return {"service": "LocalIQ", "city": "Bengaluru", "status": "ok"}


@app.get("/api/health")
async def health():
    await db.command("ping")
    return {"ok": True, "at": utcnow().isoformat()}


app.add_event_handler("startup", on_startup)
app.add_event_handler("shutdown", client.close)
