"""Capture every LocalIQ screen at desktop and mobile widths, light and dark.

    python project/scripts/capture_screenshots.py      # backend :8001 and frontend :3000 running
"""
import asyncio
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
API = [l.split("=", 1)[1].strip() for l in open(ROOT / "frontend" / ".env")
       if l.startswith("REACT_APP_BACKEND_URL")][0]
BASE = os.environ.get("FRONTEND_URL", "http://localhost:3000")
OUT = str(ROOT / "project" / "screenshots")
EMAIL, PASSWORD = "pro@localiq.in", "pro12345"

VIEWPORTS = {"web": (1440, 900), "mobile": (390, 844)}


def api(path, payload=None, token=None):
    req = urllib.request.Request(f"{API}/api{path}", method="POST" if payload is not None else "GET")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    body = json.dumps(payload).encode() if payload is not None else None
    with urllib.request.urlopen(req, body, timeout=60) as res:
        return json.loads(res.read())


async def shoot(page, path, name, bucket, theme, wait_for=None, action=None):
    target = f"{OUT}/{bucket}/{theme}"
    os.makedirs(target, exist_ok=True)
    try:
        await page.goto(f"{BASE}{path}", wait_until="domcontentloaded", timeout=45000)
        if wait_for:
            await page.wait_for_selector(wait_for, timeout=25000)
        await page.wait_for_timeout(1800)
        if action:
            await action(page)
        await page.screenshot(path=f"{target}/{name}.png", full_page=True)
        print(f"ok   {bucket}/{theme}/{name}")
    except Exception as exc:
        print(f"FAIL {bucket}/{theme}/{name}: {type(exc).__name__} {exc}")


async def open_chat(page):
    for sel in ["[data-testid='report-chat-open']", "[data-testid='chat-fab']"]:
        if await page.locator(sel).count():
            await page.locator(sel).first.click()
            break
    await page.wait_for_timeout(1500)


async def run_evals(page):
    await page.locator("[data-testid='run-evals']").click()
    await page.wait_for_selector("[data-testid='eval-results']", timeout=60000)
    await page.wait_for_timeout(1200)


def indiranagar_report(token):
    """The pro user's Indiranagar report - reused when it exists, generated otherwise."""
    job = api("/reports/generate", {"locality": "indiranagar", "persona_key": "family_kids"}, token)
    while not job.get("report_id"):
        time.sleep(3)
        job = api(f"/reports/job/{job['job_id']}", token=token)
        if job["status"] == "failed":
            raise RuntimeError(f"report generation failed: {job}")
    return job["report_id"]


async def main():
    token = api("/auth/login", {"email": EMAIL, "password": PASSWORD})["access_token"]
    REPORT_ID = indiranagar_report(token)
    CONTRIB_TOKEN = api("/contribute/links", {"locality_slug": "indiranagar",
                                              "report_id": REPORT_ID}, token)["token"]
    try:
        share = api(f"/reports/{REPORT_ID}/share", {}, token)
        share_token = share.get("token") or share.get("share_token")
    except Exception as exc:
        print("share mint failed:", exc)
        share_token = None

    screens = [
        ("/", "01-landing", None, None, False),
        ("/auth", "02-auth", "form", None, False),
        ("/onboarding", "03-onboarding", None, None, False),
        ("/app", "04-home", "[data-testid='locality-grid'], main", None, True),
        (f"/app/report/{REPORT_ID}", "05-report", "[data-testid='report-page'], main", None, True),
        (f"/app/report/{REPORT_ID}", "06-report-chat", "[data-testid='report-page'], main", open_chat, True),
        ("/app/compare", "07-compare", "main", None, True),
        ("/app/recommend", "08-recommend", "main", None, True),
        ("/app/community", "09-community", "main", None, True),
        ("/app/account", "10-account", "main", None, True),
        ("/app/trust", "11-trust", "main", None, True),
        ("/app/trust", "12-trust-evals", "[data-testid='run-evals']", run_evals, True),
        (f"/c/{CONTRIB_TOKEN}", "13-contribute", "[data-testid='contribute-page']", None, False),
    ]
    if share_token:
        screens.append((f"/r/{share_token}", "14-public-report", "[data-testid='public-report']", None, False))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--no-sandbox"])
        for bucket, (width, height) in VIEWPORTS.items():
            for theme in ("light", "dark"):
                ctx = await browser.new_context(viewport={"width": width, "height": height},
                                                device_scale_factor=2 if bucket == "mobile" else 1)
                await ctx.add_init_script(f"""
                    localStorage.setItem('lq_token', {json.dumps(token)});
                    localStorage.setItem('lq-theme', {json.dumps(theme)});
                """)
                page = await ctx.new_page()
                for path, name, wait_for, action, _auth in screens:
                    await shoot(page, path, name, bucket, theme, wait_for, action)
                await ctx.close()
        await browser.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
