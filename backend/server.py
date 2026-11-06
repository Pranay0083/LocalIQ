import logging

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import db, ensure_indexes, utcnow
from app.routers import auth, billing, community, contribute, evals, reports, share
from app.security import hash_password, verify_password

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("localiq")

app = FastAPI(title="LocalIQ - Neighbourhood Quality Reports")

app.include_router(auth.router)
app.include_router(reports.router)
app.include_router(share.router)
app.include_router(community.router)
app.include_router(contribute.router)
app.include_router(billing.router)
app.include_router(evals.router)

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


async def seed_user(email: str, password: str, name: str, role: str, plan: str = "free"):
    existing = await db.users.find_one({"email": email})
    if existing is None:
        await db.users.insert_one({
            "email": email, "password_hash": hash_password(password), "name": name, "role": role,
            "plan": plan, "reports_used": 0, "credits": 0, "profile": {}, "persona_key": None,
            "created_at": utcnow().isoformat()})
        logger.info("seeded %s", email)
    elif not verify_password(password, existing["password_hash"]):
        await db.users.update_one({"email": email},
                                  {"$set": {"password_hash": hash_password(password)}})
        logger.info("reset password for %s", email)


@app.on_event("startup")
async def startup():
    await ensure_indexes()
    await seed_user(settings.admin_email, settings.admin_password, "LocalIQ Admin", "admin",
                    "pro_annual")
    await seed_user("buyer@localiq.in", "buyer123", "Aarti Menon", "user", "free")
    await seed_user("pro@localiq.in", "pro12345", "Rohit Shetty", "user", "pro_monthly")

    import asyncio
    from app.services.citystats import compute_city_stats

    async def refresh_stats():
        try:
            if await db.dossiers.count_documents({"domains.geo.ok": True}) >= 3:
                await compute_city_stats()
        except Exception as exc:
            logger.warning("city stats refresh failed: %s", exc)

    asyncio.create_task(refresh_stats())


@app.on_event("shutdown")
async def shutdown():
    from app.db import client
    client.close()
