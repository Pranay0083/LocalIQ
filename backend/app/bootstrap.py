"""Startup work: indexes, the demo accounts, and the city-wide percentile table."""
import asyncio
import logging

from .config import settings
from .db import db, ensure_indexes, utcnow
from .security import hash_password, verify_password

logger = logging.getLogger("localiq")

DEMO_USERS = [
    # (email, password, name, role, plan)
    (None, None, "LocalIQ Admin", "admin", "pro_annual"),  # credentials from ADMIN_EMAIL / ADMIN_PASSWORD
    ("buyer@localiq.in", "buyer123", "Aarti Menon", "user", "free"),
    ("pro@localiq.in", "pro12345", "Rohit Shetty", "user", "pro_monthly"),
]


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


async def refresh_city_stats():
    """Percentiles need a few localities with geometry; skip quietly on an empty corpus."""
    from .services.citystats import compute_city_stats
    try:
        if await db.dossiers.count_documents({"domains.geo.ok": True}) >= 3:
            await compute_city_stats()
    except Exception as exc:
        logger.warning("city stats refresh failed: %s", exc)


async def on_startup():
    await ensure_indexes()
    for email, password, name, role, plan in DEMO_USERS:
        await seed_user(email or settings.admin_email, password or settings.admin_password,
                        name, role, plan)
    asyncio.create_task(refresh_city_stats())
