import hashlib
import hmac
import logging

import razorpay
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..config import settings
from ..db import db, utcnow
from ..security import get_current_user

logger = logging.getLogger("localiq.billing")
router = APIRouter(prefix="/api/billing", tags=["billing"])

client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))

PLANS = {
    "pro_monthly": {"key": "pro_monthly", "label": "Pro Monthly", "amount_paise": 49900,
                    "period": "month", "display": "\u20b9499",
                    "features": ["Unlimited locality reports", "Side-by-side comparison",
                                 "Unlimited recommendation runs", "Unlimited grounded chat",
                                 "Priority dossier refresh"]},
    "pro_annual": {"key": "pro_annual", "label": "Pro Annual", "amount_paise": 449900,
                   "period": "year", "display": "\u20b94,499",
                   "features": ["Everything in Pro Monthly", "Two months free",
                                "Early access to new cities", "Full agent run traces"]},
}


@router.get("/plans")
async def plans(user: dict = Depends(get_current_user)):
    return {
        "free": {"key": "free", "label": "Free", "display": "\u20b90",
                 "features": [f"{settings.free_report_limit} full locality reports",
                              "Unlimited chat inside unlocked reports", "One recommendation run",
                              "Full source citations", "Community posting"]},
        "paid": list(PLANS.values()),
        "current": user.get("plan", "free"),
        "key_id": settings.razorpay_key_id,
        "mode": "test",
    }


class OrderIn(BaseModel):
    plan: str


@router.post("/order")
async def create_order(payload: OrderIn, user: dict = Depends(get_current_user)):
    plan = PLANS.get(payload.plan)
    if not plan:
        raise HTTPException(status_code=400, detail="Unknown plan")
    receipt = f"lq_{user['id'][-8:]}_{int(utcnow().timestamp())}"[:40]
    try:
        order = client.order.create({"amount": plan["amount_paise"], "currency": "INR",
                                     "receipt": receipt, "payment_capture": 1,
                                     "notes": {"plan": plan["key"], "user_id": user["id"]}})
    except Exception as exc:
        logger.exception("razorpay order failed")
        raise HTTPException(status_code=502, detail=f"Payment gateway error: {str(exc)[:160]}")
    await db.orders.insert_one({"razorpay_order_id": order["id"], "user_id": user["id"],
                                "plan": plan["key"], "amount": plan["amount_paise"],
                                "status": "created", "created_at": utcnow().isoformat()})
    return {"order_id": order["id"], "amount": order["amount"], "currency": order["currency"],
            "key_id": settings.razorpay_key_id, "plan": plan}


class VerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/verify")
async def verify_payment(payload: VerifyIn, user: dict = Depends(get_current_user)):
    expected = hmac.new(settings.razorpay_key_secret.encode(),
                        f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}".encode(),
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, payload.razorpay_signature):
        await db.orders.update_one({"razorpay_order_id": payload.razorpay_order_id},
                                   {"$set": {"status": "signature_failed"}})
        raise HTTPException(status_code=400, detail="Payment signature verification failed")

    order = await db.orders.find_one({"razorpay_order_id": payload.razorpay_order_id,
                                      "user_id": user["id"]})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    await db.orders.update_one({"_id": order["_id"]}, {"$set": {
        "status": "paid", "payment_id": payload.razorpay_payment_id,
        "paid_at": utcnow().isoformat()}})
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {
        "plan": order["plan"], "plan_since": utcnow().isoformat()}})
    return {"ok": True, "plan": order["plan"]}


@router.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    expected = hmac.new(settings.razorpay_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    payload = await request.json()
    event = payload.get("event", "")
    entity = ((payload.get("payload") or {}).get("payment") or {}).get("entity") or {}
    order_id = entity.get("order_id")
    if order_id:
        await db.orders.update_one({"razorpay_order_id": order_id},
                                   {"$set": {"webhook_event": event,
                                             "webhook_at": utcnow().isoformat()}})
        if event == "payment.captured":
            order = await db.orders.find_one({"razorpay_order_id": order_id})
            if order:
                await db.users.update_one({"_id": ObjectId(order["user_id"])},
                                          {"$set": {"plan": order["plan"]}})
    return {"status": "processed"}
