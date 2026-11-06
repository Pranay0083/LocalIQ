import base64
import re
import uuid
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from ..db import db, utcnow
from ..localities import BY_SLUG
from ..security import get_current_user
from ..services.llm import chat_json

router = APIRouter(prefix="/api/community", tags=["community"])

CLAIM_TYPES = ["water_hours", "water_quality", "power_cuts", "noise", "parking", "rent_paid",
               "safety_night", "internet", "other"]

PII_PATTERNS = [
    (re.compile(r"\b(?:\+91[\-\s]?)?[6-9]\d{9}\b"), "[phone removed]"),
    (re.compile(r"\b[\w.\-]+@[\w\-]+\.[a-zA-Z]{2,}\b"), "[email removed]"),
    (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "[id removed]"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[id removed]"),
]


def scrub_pii(text: str) -> tuple:
    cleaned, hits = text, 0
    for pattern, replacement in PII_PATTERNS:
        cleaned, count = pattern.subn(replacement, cleaned)
        hits += count
    return cleaned, hits


async def screen_post(body: str) -> dict:
    result = await chat_json(
        f"Classify this neighbourhood community post.\n\nPOST: {body[:1200]}\n\n"
        f'Return {{"toxic":true|false,"reason":"","sentiment":"positive|negative|mixed|neutral",'
        f'"topics":["max 3 short lowercase topic tags"]}}',
        system="You moderate and tag community posts about Bengaluru neighbourhoods. Flag as toxic "
               "only for harassment, hate speech, targeting of communities, or doxxing. Criticism of "
               "a locality's infrastructure is NOT toxic. Output strict JSON only.",
        max_tokens=300)
    if not isinstance(result, dict):
        return {"toxic": False, "sentiment": "neutral", "topics": []}
    return result


class PostIn(BaseModel):
    locality_slug: str
    kind: str = Field(pattern="^(experience|fact_claim)$")
    body: str = Field(min_length=10, max_length=2000)
    claim_type: Optional[str] = None
    claim_value: Optional[str] = None
    proof_id: Optional[str] = None


@router.post("/proof")
async def upload_proof(payload: dict, user: dict = Depends(get_current_user)):
    data_url = payload.get("data_url", "")
    if not data_url.startswith("data:image/"):
        raise HTTPException(status_code=400, detail="Proof must be an image")
    header, _, encoded = data_url.partition(",")
    try:
        blob = base64.b64decode(encoded)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode image")
    if len(blob) > 3 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image must be under 3 MB")
    proof_id = str(uuid.uuid4())
    await db.proofs.insert_one({"proof_id": proof_id, "user_id": user["id"], "data": encoded,
                                "mime": header.split(";")[0].replace("data:", ""),
                                "created_at": utcnow().isoformat()})
    return {"proof_id": proof_id, "url": f"/api/community/proof/{proof_id}"}


@router.get("/proof/{proof_id}")
async def get_proof(proof_id: str):
    doc = await db.proofs.find_one({"proof_id": proof_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(content=base64.b64decode(doc["data"]), media_type=doc.get("mime", "image/png"))


@router.post("/posts")
async def create_post(payload: PostIn, user: dict = Depends(get_current_user)):
    if payload.locality_slug not in BY_SLUG:
        raise HTTPException(status_code=404, detail="Unknown locality")
    if payload.kind == "fact_claim":
        if payload.claim_type not in CLAIM_TYPES:
            raise HTTPException(status_code=400, detail="Fact claims need a valid claim type")
        if not payload.proof_id:
            raise HTTPException(status_code=400,
                                detail="Fact claims require a photo or screenshot as proof")

    today = utcnow().strftime("%Y-%m-%d")
    posted_today = await db.posts.count_documents({"user_id": user["id"], "day": today})
    if posted_today >= 10:
        raise HTTPException(status_code=429, detail="Daily posting limit reached")

    body, pii_hits = scrub_pii(payload.body.strip())
    screen = await screen_post(body)
    if screen.get("toxic"):
        raise HTTPException(status_code=422, detail={
            "code": "moderation",
            "message": "This post was held by automated moderation.",
            "reason": screen.get("reason", "")})

    doc = {
        "locality_slug": payload.locality_slug, "kind": payload.kind, "body": body,
        "claim_type": payload.claim_type, "claim_value": payload.claim_value,
        "proof_url": f"/api/community/proof/{payload.proof_id}" if payload.proof_id else None,
        "user_id": user["id"], "author_name": user.get("name", "Resident"),
        "sentiment": screen.get("sentiment", "neutral"), "topics": screen.get("topics", [])[:3],
        "upvotes": 0, "downvotes": 0, "status": "pending", "pii_scrubbed": pii_hits,
        "credit_granted": False, "day": today, "created_at": utcnow().isoformat(),
    }
    result = await db.posts.insert_one(doc)
    await _reconcile_claim_status(payload.locality_slug, payload.claim_type)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


async def _reconcile_claim_status(slug: str, claim_type: Optional[str]):
    if not claim_type:
        return
    # anonymous link contributions publish as `unverified` and never take part in corroboration
    items = await db.posts.find({"locality_slug": slug, "kind": "fact_claim",
                                 "claim_type": claim_type, "anonymous": {"$ne": True},
                                 "status": {"$ne": "removed"}}).to_list(100)
    contributors = {i["user_id"] for i in items}
    with_proof = [i for i in items if i.get("proof_url")]
    status = "corroborated" if len(contributors) >= 2 and len(with_proof) >= 2 else "pending"
    if len(contributors) >= 3 and len(with_proof) >= 3:
        status = "verified"
    for item in items:
        await db.posts.update_one({"_id": item["_id"]}, {"$set": {"status": status}})
        if status in ("corroborated", "verified") and not item.get("credit_granted"):
            await db.posts.update_one({"_id": item["_id"]}, {"$set": {"credit_granted": True}})
            await db.users.update_one({"_id": ObjectId(item["user_id"])}, {"$inc": {"credits": 1}})


@router.get("/posts")
async def list_posts(locality_slug: Optional[str] = None, kind: Optional[str] = None, limit: int = 50):
    query = {"status": {"$ne": "removed"}}
    if locality_slug:
        query["locality_slug"] = locality_slug
    if kind:
        query["kind"] = kind
    docs = await db.posts.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    return [{"id": str(d.pop("_id")), **d} for d in docs]


class VoteIn(BaseModel):
    value: int = Field(ge=-1, le=1)


@router.post("/posts/{post_id}/vote")
async def vote(post_id: str, payload: VoteIn, user: dict = Depends(get_current_user)):
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="Bad post id")
    existing = await db.votes.find_one({"post_id": post_id, "user_id": user["id"]})
    if existing:
        if existing["value"] == payload.value:
            raise HTTPException(status_code=409, detail="You already voted on this post")
        field_out = "upvotes" if existing["value"] == 1 else "downvotes"
        await db.posts.update_one({"_id": ObjectId(post_id)}, {"$inc": {field_out: -1}})
        await db.votes.update_one({"_id": existing["_id"]}, {"$set": {"value": payload.value}})
    else:
        await db.votes.insert_one({"post_id": post_id, "user_id": user["id"], "value": payload.value,
                                   "created_at": utcnow().isoformat()})
    field_in = "upvotes" if payload.value == 1 else "downvotes"
    await db.posts.update_one({"_id": ObjectId(post_id)}, {"$inc": {field_in: 1}})
    post = await db.posts.find_one({"_id": ObjectId(post_id)})
    net = post.get("upvotes", 0) - post.get("downvotes", 0)
    if net >= 5 and not post.get("credit_granted") and post.get("user_id"):
        await db.posts.update_one({"_id": ObjectId(post_id)}, {"$set": {"credit_granted": True}})
        await db.users.update_one({"_id": ObjectId(post["user_id"])}, {"$inc": {"credits": 1}})
    post["id"] = str(post.pop("_id"))
    return post


@router.get("/leaderboard")
async def leaderboard(locality_slug: Optional[str] = None, limit: int = 10):
    match = {"status": {"$ne": "removed"}}
    if locality_slug:
        match["locality_slug"] = locality_slug
    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$user_id", "author_name": {"$first": "$author_name"},
                    "posts": {"$sum": 1}, "upvotes": {"$sum": "$upvotes"},
                    "verified": {"$sum": {"$cond": [{"$in": ["$status", ["verified", "corroborated"]]}, 1, 0]}}}},
        {"$sort": {"verified": -1, "upvotes": -1, "posts": -1}},
        {"$limit": limit},
    ]
    rows = await db.posts.aggregate(pipeline).to_list(limit)
    return [{"user_id": r["_id"], "name": r.get("author_name", "Resident"), "posts": r["posts"],
             "upvotes": r["upvotes"], "verified": r["verified"]} for r in rows]


@router.get("/me")
async def my_contributions(user: dict = Depends(get_current_user)):
    docs = await db.posts.find({"user_id": user["id"]}).sort("created_at", -1).limit(50).to_list(50)
    posts = [{"id": str(d.pop("_id")), **d} for d in docs]
    days = sorted({p["day"] for p in posts}, reverse=True)
    streak = 0
    from datetime import date, timedelta
    cursor = date.today()
    for _ in range(60):
        if cursor.isoformat() in days:
            streak += 1
            cursor -= timedelta(days=1)
        elif streak == 0 and cursor == date.today():
            cursor -= timedelta(days=1)
        else:
            break
    return {
        "posts": posts,
        "stats": {
            "total": len(posts),
            "verified": sum(1 for p in posts if p.get("status") in ("verified", "corroborated")),
            "upvotes": sum(p.get("upvotes", 0) for p in posts),
            "credits_earned": sum(1 for p in posts if p.get("credit_granted")),
            "streak_days": streak,
        },
    }
