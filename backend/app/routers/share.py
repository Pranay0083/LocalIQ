"""Public, unauthenticated read-only teaser of a report the owner chose to share."""
import secrets

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from ..db import db, utcnow
from ..security import get_current_user

router = APIRouter(prefix="/api")

HERO_CARDS = 3


@router.post("/reports/{report_id}/share")
async def create_share_link(report_id: str, user: dict = Depends(get_current_user)):
    """Mint (once) and return the public token for a report the caller owns."""
    if not ObjectId.is_valid(report_id):
        raise HTTPException(status_code=400, detail="Bad report id")
    doc = await db.reports.find_one({"_id": ObjectId(report_id), "user_id": user["id"]},
                                    {"share_token": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")

    token = doc.get("share_token")
    if not token:
        token = secrets.token_urlsafe(9)
        await db.reports.update_one(
            {"_id": doc["_id"]},
            {"$set": {"share_token": token, "shared_at": utcnow().isoformat()}})
    return {"token": token, "path": f"/r/{token}"}


@router.get("/public/reports/{token}")
async def public_report(token: str):
    """The teaser: both scores, the verdict, three hero modules with full citations."""
    doc = await db.reports.find_one({"share_token": token})
    if not doc:
        raise HTTPException(status_code=404, detail="This link is not valid.")

    cards = doc.get("cards") or []
    hero_modules = [c["module"] for c in cards if not c.get("empty")][:HERO_CARDS]
    narrative = doc.get("narrative") or {}

    return {
        "locality": doc.get("locality"),
        "persona_key": doc.get("persona_key"),
        "persona_label": doc.get("persona_label"),
        "composite": doc.get("composite"),
        "baseline_composite": doc.get("baseline_composite"),
        "narrative": {"headline": narrative.get("headline"), "verdict": narrative.get("verdict"),
                      "living_here": narrative.get("living_here"),
                      "wins": narrative.get("wins") or [], "watchouts": narrative.get("watchouts") or []},
        "cards": [c for c in cards if c["module"] in hero_modules],
        "locked": [{"module": c["module"], "title": c["title"], "tier": c["tier"],
                    "has_data": not c.get("empty")}
                   for c in cards if c["module"] not in hero_modules],
        "sources_count": len(doc.get("sources") or []),
        "modules_total": len(cards),
        "created_at": doc.get("created_at"),
    }
