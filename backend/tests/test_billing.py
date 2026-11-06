"""Billing: plans, order, verify (bad signature)."""
import requests
from .conftest import BASE_URL


class TestBilling:
    def test_plans(self, pro_session):
        r = pro_session.get(f"{BASE_URL}/api/billing/plans", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "test"
        assert data["key_id"].startswith("rzp_")
        keys = {p["key"] for p in data["paid"]}
        assert {"pro_monthly", "pro_annual"}.issubset(keys)
        by_key = {p["key"]: p for p in data["paid"]}
        assert by_key["pro_monthly"]["amount_paise"] == 49900
        assert by_key["pro_annual"]["amount_paise"] == 449900

    def test_order_creates_razorpay_order(self, buyer_session):
        r = buyer_session.post(f"{BASE_URL}/api/billing/order",
                               json={"plan": "pro_monthly"}, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["order_id"].startswith("order_")
        assert data["amount"] == 49900
        assert data["currency"] == "INR"

    def test_order_bad_plan(self, buyer_session):
        r = buyer_session.post(f"{BASE_URL}/api/billing/order",
                               json={"plan": "platinum_infinite"}, timeout=30)
        assert r.status_code == 400

    def test_verify_bad_signature(self, buyer_session):
        # First need an order id to reference
        order = buyer_session.post(f"{BASE_URL}/api/billing/order",
                                   json={"plan": "pro_monthly"}, timeout=60).json()
        r = buyer_session.post(f"{BASE_URL}/api/billing/verify",
                               json={"razorpay_order_id": order["order_id"],
                                     "razorpay_payment_id": "pay_FAKEXXXXX",
                                     "razorpay_signature": "deadbeef" * 8},
                               timeout=30)
        assert r.status_code == 400
