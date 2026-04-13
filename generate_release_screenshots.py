import argparse
import os
import re
import subprocess
import time
import urllib.request
from contextlib import suppress
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


def wait_for_http_ready(url, timeout_s=90):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if 200 <= resp.status < 500:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def wait_visible(page, locator, timeout_ms=30000):
    locator.wait_for(state="visible", timeout=timeout_ms)


def save_shot(page, path):
    page.wait_for_timeout(800)
    page.screenshot(path=str(path), full_page=True)


def safe_click(locator):
    locator.click(timeout=15000)


def operator_login(page, base_url, username, password):
    page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
    wait_visible(page, page.get_by_role("textbox", name="Username").first)
    page.get_by_role("textbox", name="Username").first.fill(username)
    page.get_by_role("textbox", name="Password").first.fill(password)
    safe_click(page.get_by_role("button", name=re.compile(r"Sign In", re.I)))
    wait_visible(page, page.get_by_text("Welcome,", exact=False), timeout_ms=60000)


def admin_login(page, base_url, username, password):
    page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
    wait_visible(page, page.get_by_role("textbox", name="Username").first)
    page.get_by_role("textbox", name="Username").first.fill(username)
    page.get_by_role("textbox", name="Password").first.fill(password)
    safe_click(page.get_by_role("button", name=re.compile(r"Sign In", re.I)))
    wait_visible(page, page.get_by_text("Admin Review Panel", exact=False), timeout_ms=60000)


def capture_release_screenshots(args):
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    streamlit_cmd = [
        "python",
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.headless",
        "true",
        "--server.port",
        str(args.port),
    ]
    process = subprocess.Popen(
        streamlit_cmd,
        cwd=args.workdir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    base_url = f"http://127.0.0.1:{args.port}"

    try:
        if not wait_for_http_ready(base_url, timeout_s=120):
            raise RuntimeError("Streamlit did not become ready in time.")

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()

            page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
            wait_visible(page, page.get_by_role("textbox", name="Username").first)
            save_shot(page, out_dir / "01_login_page.png")

            operator_login(page, base_url, args.operator_user, args.operator_password)
            save_shot(page, out_dir / "02_operator_dashboard.png")

            safe_click(page.get_by_role("link", name=re.compile(r"Create New Estimate", re.I)))
            wait_visible(page, page.get_by_text("Start New Estimate", exact=False), timeout_ms=30000)
            save_shot(page, out_dir / "03_new_estimate_dialog.png")

            run_id = str(int(time.time()))
            page.get_by_role("textbox", name="Name of Project").first.fill(f"Release Project {run_id}")
            page.get_by_role("textbox", name="Estimate Number").first.fill(f"REL-{run_id}")
            save_shot(page, out_dir / "04_new_estimate_filled.png")

            safe_click(page.get_by_role("button", name=re.compile(r"Create Estimate", re.I)))
            wait_visible(page, page.get_by_role("tab").first, timeout_ms=60000)
            save_shot(page, out_dir / "05_module_form_overview.png")

            tab_targets = [
                ("Admin Financial Sanction", "06_tab_admin_financial_sanction.png"),
                ("Technical Sanction", "07_tab_technical_sanction.png"),
                ("Tender Award Contract", "08_tab_tender_award_contract.png"),
                ("Contract Master", "09_tab_contract_master.png"),
                ("Payments Recoveries", "10_tab_payments_recoveries.png"),
                ("Budget Summary", "11_tab_budget_summary.png"),
            ]
            for tab_label, fname in tab_targets:
                with suppress(Exception):
                    safe_click(page.get_by_role("tab", name=re.compile(tab_label, re.I)))
                    save_shot(page, out_dir / fname)

            safe_click(page.get_by_role("link", name=re.compile(r"Sign Out", re.I)))
            wait_visible(page, page.get_by_role("textbox", name="Username").first, timeout_ms=30000)
            save_shot(page, out_dir / "12_login_after_logout.png")

            admin_login(page, base_url, args.admin_user, args.admin_password)
            save_shot(page, out_dir / "13_admin_review_applications.png")

            with suppress(Exception):
                safe_click(page.get_by_role("tab", name=re.compile(r"Create User", re.I)))
                wait_visible(page, page.get_by_text("Create New User", exact=False), timeout_ms=30000)
                save_shot(page, out_dir / "14_admin_create_user.png")

            with suppress(Exception):
                safe_click(page.get_by_role("tab", name=re.compile(r"Manage Users", re.I)))
                wait_visible(page, page.get_by_text("Manage Existing Users", exact=False), timeout_ms=30000)
                save_shot(page, out_dir / "15_admin_manage_users.png")

            with suppress(Exception):
                safe_click(page.get_by_role("tab", name=re.compile(r"Review Applications", re.I)))
                combo = page.get_by_role("combobox").first
                combo.click()
                page.get_by_role("option", name=re.compile(r"All Users", re.I)).click()
                page.wait_for_timeout(1200)
                save_shot(page, out_dir / "16_admin_review_all_users.png")

            with suppress(Exception):
                page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
                admin_login(page, base_url, args.admin_user, args.admin_password)
                review_combo = page.get_by_role("combobox").first
                review_combo.click()
                page.get_by_role("option", name=re.compile(r"All Users", re.I)).click()
                page.wait_for_timeout(1200)
                estimate_btns = page.get_by_role("button").all()
                for btn in estimate_btns:
                    label = (btn.inner_text(timeout=1000) or "").strip().lower()
                    if label and "previous" not in label and "next" not in label and "create user" not in label:
                        with suppress(Exception):
                            btn.click(timeout=5000)
                            page.wait_for_timeout(1200)
                            save_shot(page, out_dir / "17_admin_estimate_dialog.png")
                            break

            browser.close()
    finally:
        with suppress(Exception):
            process.terminate()
        with suppress(Exception):
            process.wait(timeout=15)
        with suppress(Exception):
            process.kill()


def parse_args():
    parser = argparse.ArgumentParser(description="Generate screenshot set for release documentation.")
    parser.add_argument("--workdir", default=".", help="Project working directory.")
    parser.add_argument("--output-dir", default="release/screenshots", help="Output directory for screenshots.")
    parser.add_argument("--port", type=int, default=8511, help="Streamlit port to launch on.")
    parser.add_argument("--operator-user", default="qa_operator", help="Operator username.")
    parser.add_argument("--operator-password", default="QaOperator#2026", help="Operator password.")
    parser.add_argument("--admin-user", default="qa_admin", help="Admin username.")
    parser.add_argument("--admin-password", default="QaAdmin#2026", help="Admin password.")
    return parser.parse_args()


if __name__ == "__main__":
    capture_release_screenshots(parse_args())
