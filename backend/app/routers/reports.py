import asyncio
import json
import logging
import uuid
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..agents.advisor import answer_question, compare_localities, recommend, stream_answer
from ..agents.graph import run_report
from ..config import settings
from ..db import db, utcnow
from ..localities import BANGALORE, BY_SLUG, find_locality, search_localities
from ..rubric import (BASELINE_WEIGHTS, FRESHNESS_POLICY, MODULES, PERSONAS, RUBRIC_DOC,
                      SOURCE_TYPES, select_modules)
from ..security import get_current_user
from ..services.llm import ledger_snapshot

logger = logging.getLogger("localiq.api")
router = APIRouter(prefix="/api", tags=["core"])


# ------------------------------------------------------------- entitlements
def entitlement(user: dict) -> dict:
    used = user.get("reports_used", 0)
    credits = user.get("credits", 0)
    pro = user.get("plan", "free") in ("pro_monthly", "pro_annual")
    free_left = max(0, settings.free_report_limit - used)
    return {
        "plan": user.get("plan", "free"), "pro": pro, "used": used, "credits": credits,
        "free_left": free_left, "free_limit": settings.free_report_limit,
        "can_generate": pro or free_left > 0 or credits > 0,
        "can_compare": pro,
        "recommend_runs": user.get("recommend_runs", 0),
        "can_recommend": pro or user.get("recommend_runs", 0) < 1,
    }


async def spend_report_credit(user: dict):
    if user.get("plan") in ("pro_monthly", "pro_annual"):
        return
    if user.get("credits", 0) > 0:
        await db.users.update_one({"_id": ObjectId(user["id"])}, {"$inc": {"credits": -1}})
    else:
        await db.users.update_one({"_id": ObjectId(user["id"])}, {"$inc": {"reports_used": 1}})


# ------------------------------------------------------------------ catalogue
@router.get("/localities")
async def list_localities(q: str = "", limit: int = 40):
    results = search_localities(q, limit) if q else BANGALORE[:limit]
    warm = {d["locality_slug"] async for d in db.dossiers.find({}, {"locality_slug": 1})}
    return [{**loc, "warm": loc["slug"] in warm} for loc in results]


@router.get("/personas")
async def list_personas():
    return [{"key": key, "label": value["label"], "summary": value["summary"],
             "weights": value["weights"], "modules": select_modules(key)}
            for key, value in PERSONAS.items()]


@router.get("/modules")
async def list_modules():
    return [{"key": key, **value} for key, value in MODULES.items()]


@router.get("/trust/rubric")
async def trust_rubric():
    return {
        "rubric": RUBRIC_DOC,
        "modules": [{"key": k, **v} for k, v in MODULES.items()],
        "personas": [{"key": k, **v} for k, v in PERSONAS.items()],
        "baseline_weights": BASELINE_WEIGHTS,
        "freshness_policy": FRESHNESS_POLICY,
        "source_types": SOURCE_TYPES,
        "principles": [
            "Every number carries a source, a date and a confidence level.",
            "Distances and counts are computed geometry from OpenStreetMap. A language model never computes a distance.",
            "Media-reported incident counts are not crime rates. They are coverage-biased and are labelled as such everywhere they appear.",
            "Absence of data is displayed as absence. It is never averaged away.",
            "The composite score is persona-weighted and is always shown next to a neutral baseline.",
            "Community fact claims need photo proof and independent corroboration before they can move a score.",
            "A community claim that contradicts an official source raises a dispute; it never silently overrides.",
            "Decision support, not advice. No investment guarantees, no steering, no claims about who a locality is safe for.",
        ],
    }


# --------------------------------------------------------------- generation
class GenerateIn(BaseModel):
    locality: str
    persona_key: Optional[str] = None
    overrides: Optional[dict] = None
    force: bool = False


async def _execute_job(job_id: str, user_id: str, loc: dict, persona_key: str, profile: dict,
                       overrides: dict, force: bool):
    try:
        result = await run_report(loc, persona_key, profile, overrides, job_id=job_id, force=force)
        doc = {
            "user_id": user_id, "locality_slug": loc["slug"], "locality": loc,
            "persona_key": persona_key, "persona_label": PERSONAS[persona_key]["label"],
            "overrides": overrides or {}, "job_id": job_id, "created_at": utcnow().isoformat(),
            **result,
        }
        inserted = await db.reports.insert_one(doc)
        await db.jobs.update_one({"job_id": job_id}, {"$set": {
            "status": "done", "report_id": str(inserted.inserted_id),
            "finished_at": utcnow().isoformat(), "cost": result["cost"]}})
    except Exception as exc:
        logger.exception("report job failed")
        await db.jobs.update_one({"job_id": job_id}, {"$set": {
            "status": "failed", "error": str(exc)[:400], "finished_at": utcnow().isoformat()}})


@router.post("/reports/generate")
async def generate(payload: GenerateIn, background: BackgroundTasks,
                   user: dict = Depends(get_current_user)):
    loc = find_locality(payload.locality)
    if not loc:
        raise HTTPException(status_code=404,
                            detail="LocalIQ covers Bengaluru only right now. Try a Bengaluru locality "
                                   "name or pin code.")
    persona_key = payload.persona_key or user.get("persona_key") or "bachelor"
    if persona_key not in PERSONAS:
        raise HTTPException(status_code=400, detail="Unknown persona")

    ent = entitlement(user)
    existing = await db.reports.find_one(
        {"user_id": user["id"], "locality_slug": loc["slug"], "persona_key": persona_key},
        sort=[("created_at", -1)])
    charge = payload.force or existing is None
    if charge and not ent["can_generate"]:
        raise HTTPException(status_code=402, detail={
            "code": "paywall",
            "message": f"You have used all {ent['free_limit']} free locality reports.",
            "entitlement": ent})
    if not charge and existing:
        return {"job_id": None, "report_id": str(existing["_id"]), "cached": True}

    job_id = str(uuid.uuid4())
    await db.jobs.insert_one({
        "job_id": job_id, "user_id": user["id"], "locality_slug": loc["slug"],
        "locality_name": loc["name"], "persona_key": persona_key, "status": "running",
        "created_at": utcnow().isoformat(), "trace": [],
    })
    if charge:
        await spend_report_credit(user)
    background.add_task(_execute_job, job_id, user["id"], loc, persona_key,
                        user.get("profile") or {}, payload.overrides or {}, payload.force)
    return {"job_id": job_id, "report_id": None, "cached": False}


@router.get("/reports/job/{job_id}")
async def job_status(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"job_id": job_id, "user_id": user["id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/reports")
async def list_reports(user: dict = Depends(get_current_user)):
    docs = await db.reports.find(
        {"user_id": user["id"]},
        {"cards": 0, "sources": 0, "module_scores": 0}).sort("created_at", -1).limit(80).to_list(80)
    seen, unique = set(), []
    for doc in docs:
        key = (doc["locality_slug"], doc["persona_key"])
        if key in seen:
            continue
        seen.add(key)
        unique.append({"id": str(doc.pop("_id")), **doc})
    return unique[:40]


@router.get("/reports/{report_id}")
async def get_report(report_id: str, user: dict = Depends(get_current_user)):
    if not ObjectId.is_valid(report_id):
        raise HTTPException(status_code=400, detail="Bad report id")
    doc = await db.reports.find_one({"_id": ObjectId(report_id), "user_id": user["id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")
    doc["id"] = str(doc.pop("_id"))
    return doc


class LensIn(BaseModel):
    persona_key: str
    overrides: Optional[dict] = None


@router.post("/reports/{report_id}/lens")
async def switch_lens(report_id: str, payload: LensIn, user: dict = Depends(get_current_user)):
    """Re-score and re-narrate from the cached dossier. Free: spends no credit and
    triggers no collection."""
    if payload.persona_key not in PERSONAS:
        raise HTTPException(status_code=400, detail="Unknown persona")
    doc = await db.reports.find_one({"_id": ObjectId(report_id), "user_id": user["id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")
    loc = doc["locality"]
    result = await run_report(loc, payload.persona_key, user.get("profile") or {},
                              payload.overrides or {}, job_id=None, force=False)
    new_doc = {
        "user_id": user["id"], "locality_slug": loc["slug"], "locality": loc,
        "persona_key": payload.persona_key, "persona_label": PERSONAS[payload.persona_key]["label"],
        "overrides": payload.overrides or {}, "job_id": None, "lens_of": report_id,
        "created_at": utcnow().isoformat(), **result,
    }
    inserted = await db.reports.insert_one(new_doc)
    new_doc["id"] = str(inserted.inserted_id)
    new_doc.pop("_id", None)
    return new_doc


# --------------------------------------------------------------------- chat
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


@router.post("/reports/{report_id}/chat")
async def report_chat(report_id: str, payload: ChatIn, user: dict = Depends(get_current_user)):
    doc = await db.reports.find_one({"_id": ObjectId(report_id), "user_id": user["id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")
    today = utcnow().strftime("%Y-%m-%d")
    used_today = await db.chat_messages.count_documents(
        {"user_id": user["id"], "role": "user", "day": today})
    if used_today >= 100:
        raise HTTPException(status_code=429, detail="Daily chat limit reached. Resets tomorrow.")

    history = (await db.chat_messages.find(
        {"report_id": report_id}, {"_id": 0, "role": 1, "content": 1}
    ).sort("created_at", -1).limit(20).to_list(20))[::-1]

    await db.chat_messages.insert_one({"report_id": report_id, "user_id": user["id"], "role": "user",
                                       "content": payload.message, "day": today,
                                       "created_at": utcnow().isoformat()})
    result = await answer_question(doc, payload.message, history)
    await db.chat_messages.insert_one({"report_id": report_id, "user_id": user["id"],
                                       "role": "assistant", "content": result.get("answer", ""),
                                       "used_sources": result.get("used_sources", []),
                                       "missing": result.get("missing", ""), "day": today,
                                       "created_at": utcnow().isoformat()})
    return result


@router.post("/reports/{report_id}/chat/stream")
async def report_chat_stream(report_id: str, payload: ChatIn,
                             user: dict = Depends(get_current_user)):
    doc = await db.reports.find_one({"_id": ObjectId(report_id), "user_id": user["id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")
    today = utcnow().strftime("%Y-%m-%d")
    used_today = await db.chat_messages.count_documents(
        {"user_id": user["id"], "role": "user", "day": today})
    if used_today >= 100:
        raise HTTPException(status_code=429, detail="Daily chat limit reached. Resets tomorrow.")

    history = (await db.chat_messages.find(
        {"report_id": report_id}, {"_id": 0, "role": 1, "content": 1}
    ).sort("created_at", -1).limit(20).to_list(20))[::-1]
    user_turn = await db.chat_messages.insert_one(
        {"report_id": report_id, "user_id": user["id"], "role": "user",
         "content": payload.message, "day": today, "created_at": utcnow().isoformat()})

    async def events():
        meta = {"answer": "", "used_sources": [], "missing": ""}
        partial = ""
        try:
            async for kind, data in stream_answer(doc, payload.message, history):
                if kind == "delta":
                    partial += data
                    yield f"data: {json.dumps({'type': 'delta', 'text': data})}\n\n"
                else:
                    meta = data
        except Exception as exc:
            logger.exception("chat stream failed")
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)[:200]})}\n\n"

        meta["answer"] = meta["answer"] or partial.strip()
        if meta["answer"]:
            await db.chat_messages.insert_one(
                {"report_id": report_id, "user_id": user["id"], "role": "assistant",
                 "content": meta["answer"], "used_sources": meta["used_sources"],
                 "missing": meta["missing"], "day": today, "created_at": utcnow().isoformat()})
        else:
            # nothing was written - drop the user turn so history has no orphan
            await db.chat_messages.delete_one({"_id": user_turn.inserted_id})
        yield f"data: {json.dumps({'type': 'done', **meta})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                                      "Connection": "keep-alive"})


@router.get("/reports/{report_id}/chat")
async def chat_history(report_id: str, user: dict = Depends(get_current_user)):
    """Most recent 80 turns, oldest first."""
    recent = await db.chat_messages.find(
        {"report_id": report_id, "user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).limit(80).to_list(80)
    return recent[::-1]


# ------------------------------------------------------------------ compare
class CompareIn(BaseModel):
    slugs: list[str] = Field(min_length=2, max_length=3)
    persona_key: Optional[str] = None


@router.post("/compare")
async def compare(payload: CompareIn, user: dict = Depends(get_current_user)):
    ent = entitlement(user)
    if not ent["can_compare"]:
        raise HTTPException(status_code=402, detail={
            "code": "premium",
            "message": "Side-by-side comparison is a Pro feature.",
            "entitlement": ent})
    persona_key = payload.persona_key or user.get("persona_key") or "bachelor"
    reports = []
    for slug in payload.slugs:
        loc = BY_SLUG.get(slug)
        if not loc:
            raise HTTPException(status_code=404, detail=f"Unknown locality: {slug}")
        result = await run_report(loc, persona_key, user.get("profile") or {}, {}, force=False)
        reports.append({**result, "locality": loc})
    verdict = await compare_localities(reports, persona_key, user.get("profile") or {})
    selected = select_modules(persona_key)
    return {
        "persona": {"key": persona_key, **PERSONAS[persona_key]},
        "modules": [{"key": m, **MODULES[m]} for m in selected],
        "localities": [{
            "slug": r["locality"]["slug"], "name": r["locality"]["name"],
            "zone": r["locality"]["zone"], "score": r["composite"].get("score"),
            "baseline": r["baseline_composite"].get("score"),
            "confidence": r["composite"].get("confidence"),
            "coverage": r["composite"].get("coverage"),
            "modules": {m: (r["module_scores"].get(m) or {}).get("score") for m in selected},
            "narrative": r["narrative"].get("headline"),
            "sources": len(r["sources"]),
        } for r in reports],
        "verdict": verdict,
        "generated_at": utcnow().isoformat(),
    }


# ---------------------------------------------------------------- recommend
@router.post("/recommend")
async def recommend_localities(user: dict = Depends(get_current_user)):
    ent = entitlement(user)
    if not ent["can_recommend"]:
        raise HTTPException(status_code=402, detail={
            "code": "premium",
            "message": "You have used your free recommendation run. Upgrade for unlimited runs.",
            "entitlement": ent})
    persona_key = user.get("persona_key") or "bachelor"
    result = await recommend(user.get("profile") or {}, persona_key)
    if user.get("plan", "free") == "free":
        await db.users.update_one({"_id": ObjectId(user["id"])}, {"$inc": {"recommend_runs": 1}})
    await db.recommendations.insert_one({"user_id": user["id"], **result})
    return result


# ------------------------------------------------------------------- traces
@router.get("/traces")
async def my_traces(user: dict = Depends(get_current_user)):
    jobs = await db.jobs.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)
    return {"jobs": jobs, "ledger": ledger_snapshot()}


@router.get("/entitlement")
async def my_entitlement(user: dict = Depends(get_current_user)):
    return entitlement(user)
