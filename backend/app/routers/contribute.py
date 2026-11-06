"""Shareable contribution links.

A resident with no LocalIQ account can open /c/{token} and close a data gap for one
locality. Anonymous contributions publish immediately, tagged `unverified`: they are
visible everywhere, they are never scored, and they can never corroborate a claim.
"""
import base64
import hashlib
import secrets
import uuid
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..db import db, utcnow
from ..localities import BY_SLUG
from ..security import get_current_user
from .community import CLAIM_TYPES, screen_post, scrub_pii

router = APIRouter(prefix="/api", tags=["contribute"])

CLAIM_LABELS = {
    "water_hours": "Water supply hours",
    "water_quality": "Water quality",
    "power_cuts": "Power cuts",
    "noise": "Noise / construction",
    "parking": "Parking",
    "rent_paid": "Rent actually paid",
    "safety_night": "Late-night safety",
    "internet": "Internet reliability",
    "other": "Something else",
}

DAILY_PER_TOKEN = 25
DAILY_PER_IP = 8
MAX_PROOF_BYTES = 3 * 1024 * 1024


def _ip_hash(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    raw = forwarded.split(",")[0].strip()
    if not raw:
        # no proxy header: behind a reverse proxy every request would share its IP, so skip the per-IP cap
        return ""
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def _link_or_404(token: str) -> dict:
    link = await db.contrib_links.find_one({"token": token})
    if not link or link.get("revoked"):
        raise HTTPException(status_code=404, detail="This contribution link is not valid.")
    return link


async def _guard_quota(token: str, request: Request) -> str:
    today = utcnow().strftime("%Y-%m-%d")
    ip = _ip_hash(request)
    by_token = await db.posts.count_documents({"link_token": token, "day": today})
    if by_token >= DAILY_PER_TOKEN:
        raise HTTPException(status_code=429, detail="This link has taken all it can for today.")
    if ip:
        by_ip = await db.posts.count_documents({"ip_hash": ip, "day": today})
        if by_ip >= DAILY_PER_IP:
            raise HTTPException(status_code=429,
                                detail="You have posted enough for today. Come back tomorrow.")
    return ip


# ------------------------------------------------------------------ minting
class LinkIn(BaseModel):
    locality_slug: str
    report_id: Optional[str] = None


@router.post("/contribute/links")
async def create_link(payload: LinkIn, user: dict = Depends(get_current_user)):
    """Mint (once per user + locality) a public link that asks residents to fill the gaps."""
    if payload.locality_slug not in BY_SLUG:
        raise HTTPException(status_code=404, detail="Unknown locality")

    gaps = []
    if payload.report_id and ObjectId.is_valid(payload.report_id):
        report = await db.reports.find_one(
            {"_id": ObjectId(payload.report_id), "user_id": user["id"]}, {"cards": 1})
        for card in (report or {}).get("cards", []):
            prompt = card.get("contribute") or {}
            if card.get("empty") and prompt.get("claim_type"):
                gaps.append({"module": card["module"], "title": card["title"],
                             "claim_type": prompt["claim_type"],
                             "cta": prompt.get("cta") or card["empty"].get("cta_label"),
                             "missing": card["empty"].get("missing") or []})

    existing = await db.contrib_links.find_one(
        {"locality_slug": payload.locality_slug, "created_by": user["id"], "revoked": {"$ne": True}})
    if existing:
        if gaps:
            await db.contrib_links.update_one({"_id": existing["_id"]}, {"$set": {"gaps": gaps[:6]}})
        return {"token": existing["token"], "path": f"/c/{existing['token']}", "gaps": gaps[:6]}

    token = secrets.token_urlsafe(9)
    await db.contrib_links.insert_one({
        "token": token, "locality_slug": payload.locality_slug, "created_by": user["id"],
        "created_by_name": user.get("name") or "A LocalIQ reader", "report_id": payload.report_id,
        "gaps": gaps[:6], "created_at": utcnow().isoformat(),
    })
    return {"token": token, "path": f"/c/{token}", "gaps": gaps[:6]}


@router.get("/contribute/links")
async def my_links(user: dict = Depends(get_current_user)):
    docs = await db.contrib_links.find({"created_by": user["id"], "revoked": {"$ne": True}},
                                       {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)
    for doc in docs:
        doc["contributions"] = await db.posts.count_documents({"link_token": doc["token"]})
        doc["path"] = f"/c/{doc['token']}"
    return docs


# ------------------------------------------------------------------- public
@router.get("/public/contribute/{token}")
async def public_link(token: str):
    link = await _link_or_404(token)
    loc = BY_SLUG.get(link["locality_slug"]) or {"slug": link["locality_slug"]}
    recent = await db.posts.find(
        {"locality_slug": link["locality_slug"], "status": {"$ne": "removed"}},
        {"body": 1, "claim_type": 1, "claim_value": 1, "author_name": 1, "status": 1,
         "created_at": 1, "kind": 1}
    ).sort("created_at", -1).limit(5).to_list(5)

    return {
        "locality": loc,
        "invited_by": link.get("created_by_name") or "A LocalIQ reader",
        "gaps": link.get("gaps") or [],
        "claim_types": [{"key": k, "label": CLAIM_LABELS[k]} for k in CLAIM_TYPES],
        "contributions": await db.posts.count_documents({"link_token": token}),
        "locality_total": await db.posts.count_documents(
            {"locality_slug": link["locality_slug"], "status": {"$ne": "removed"}}),
        "recent": [{"id": str(r.pop("_id")), **r, "body": (r.get("body") or "")[:180]}
                   for r in recent],
    }


@router.post("/public/contribute/{token}/proof")
async def public_proof(token: str, payload: dict, request: Request):
    await _link_or_404(token)
    ip = _ip_hash(request)
    data_url = payload.get("data_url", "")
    if not data_url.startswith("data:image/"):
        raise HTTPException(status_code=400, detail="Proof must be an image")
    header, _, encoded = data_url.partition(",")
    try:
        blob = base64.b64decode(encoded)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode image")
    if len(blob) > MAX_PROOF_BYTES:
        raise HTTPException(status_code=413, detail="Image must be under 3 MB")

    proof_id = str(uuid.uuid4())
    await db.proofs.insert_one({"proof_id": proof_id, "user_id": None, "anonymous": True,
                                "link_token": token, "ip_hash": ip, "data": encoded,
                                "mime": header.split(";")[0].replace("data:", ""),
                                "created_at": utcnow().isoformat()})
    return {"proof_id": proof_id, "url": f"/api/community/proof/{proof_id}"}


class PublicClaimIn(BaseModel):
    kind: str = Field(default="fact_claim", pattern="^(experience|fact_claim)$")
    claim_type: Optional[str] = None
    claim_value: Optional[str] = Field(default=None, max_length=140)
    body: str = Field(min_length=10, max_length=2000)
    proof_id: Optional[str] = None
    display_name: Optional[str] = Field(default=None, max_length=32)


@router.post("/public/contribute/{token}")
async def public_contribute(token: str, payload: PublicClaimIn, request: Request):
    link = await _link_or_404(token)
    ip = await _guard_quota(token, request)

    claim_type = payload.claim_type if payload.kind == "fact_claim" else None
    if payload.kind == "fact_claim" and claim_type not in CLAIM_TYPES:
        raise HTTPException(status_code=400, detail="Pick what your claim is about")

    body, pii_hits = scrub_pii(payload.body.strip())
    screen = await screen_post(body)
    if screen.get("toxic"):
        raise HTTPException(status_code=422, detail={
            "code": "moderation",
            "message": "This post was held by automated moderation.",
            "reason": screen.get("reason", "")})

    name, _ = scrub_pii((payload.display_name or "").strip())
    doc = {
        "locality_slug": link["locality_slug"], "kind": payload.kind, "body": body,
        "claim_type": claim_type,
        "claim_value": payload.claim_value if payload.kind == "fact_claim" else None,
        "proof_url": f"/api/community/proof/{payload.proof_id}" if payload.proof_id else None,
        "user_id": None, "anonymous": True, "author_name": name[:32] or "Anonymous resident",
        "link_token": token, "invited_by": link.get("created_by"), "ip_hash": ip,
        "sentiment": screen.get("sentiment", "neutral"), "topics": screen.get("topics", [])[:3],
        "upvotes": 0, "downvotes": 0, "status": "unverified", "pii_scrubbed": pii_hits,
        "credit_granted": False, "day": utcnow().strftime("%Y-%m-%d"),
        "created_at": utcnow().isoformat(),
    }
    result = await db.posts.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    doc.pop("ip_hash", None)
    return {
        "post": doc,
        "message": "Published as unverified. It shows up in the report immediately, labelled "
                   "anonymous, and it will not move any score until residents with accounts "
                   "corroborate it with proof.",
    }
