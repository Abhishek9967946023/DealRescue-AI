import os
import sys
import time
from playwright.sync_api import sync_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ARTIFACTS_DIR = r"C:\Users\Abhishek\.gemini\antigravity\brain\2d7782a0-7453-48ec-9dab-39392ad5e5c7"
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

def run():
    print("=== STARTING FULL 3-LAYER ACCEPTANCE TEST ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=CHROME_PATH,
            args=["--no-sandbox", "--disable-gpu"]
        )
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        
        console_logs = []
        page.on("console", lambda m: console_logs.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: console_logs.append(f"[pageerror] {e}"))

        print("1. Navigating to http://127.0.0.1:8000/ ...")
        page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        time.sleep(1)

        # 1. Health badge check
        badge_text = page.locator("#healthBadge").inner_text()
        print(f"Health Badge: '{badge_text}'")
        assert "LIVE" in badge_text or "ONLINE" in badge_text, f"Unexpected badge text: {badge_text}"

        page.screenshot(path=os.path.join(ARTIFACTS_DIR, "01_hero_and_badge.png"))
        print("✓ Hero & Health Badge verified.")

        # 2. Check all 9 sections
        sections = [
            ("Hero", ".hero"),
            ("How It Learns", "#story"),
            ("Learning Loop", "#loop"),
            ("Deal Workspace", "#decision"),
            ("Decision Room", "#decision-room"),
            ("Memory Evidence", "#memory"),
            ("Learning Experiment", "#experiment"),
            ("Deal Autopsy", ".autopsy"),
            ("Final Section", ".final")
        ]
        for name, sel in sections:
            el = page.locator(sel)
            assert el.count() > 0, f"Section '{name}' ({sel}) not found in DOM!"
            el.scroll_into_view_if_needed()
            time.sleep(0.3)
            print(f"✓ Section verified: {name}")

        page.screenshot(path=os.path.join(ARTIFACTS_DIR, "02_learning_loop.png"))

        # Check Loop Nodes
        loop_nodes = page.locator(".loop-node")
        print(f"Loop nodes count: {loop_nodes.count()}")
        assert loop_nodes.count() == 4, f"Expected 4 loop nodes, got {loop_nodes.count()}"

        # 3. Test New Deal creation via Modal
        print("\n3. Testing 'New Deal' modal flow...")
        page.locator("button.nav-cta").click()
        time.sleep(0.5)
        modal = page.locator("#modal")
        assert not ("hidden" in modal.get_attribute("class") or ""), "Modal failed to open"
        
        page.fill("#dName", "Enterprise Cloud Migration")
        page.fill("#dCompany", "Apex Fintech")
        page.fill("#dValue", "240000")
        page.select_option("#dStage", "Negotiation")
        page.fill("#dOwner", "Abhishek")
        page.fill("#dSummary", "Apex Fintech is evaluating migration costs against legacy hardware renewal.")
        
        page.screenshot(path=os.path.join(ARTIFACTS_DIR, "03_new_deal_modal.png"))
        page.locator("#modal .decision-btn").click()
        
        # Wait for modal to close and active deal to update
        page.wait_for_selector("#modal.hidden", timeout=10000)
        time.sleep(1)
        deal_name = page.locator("#dealName").inner_text()
        deal_company = page.locator("#dealCompany").inner_text()
        print(f"Active deal after creation: {deal_name} at {deal_company}")
        assert "Enterprise Cloud Migration" in deal_name
        assert "Apex Fintech" in deal_company
        print("✓ New Deal created and became active!")

        # 4. Load realistic experiences for this deal
        print("\n4. Seeding demo experiences...")
        page.locator("button:has-text('Load 12 demo experiences')").click()
        page.wait_for_timeout(3000) # give time for seed to initiate
        
        # Wait up to 35 seconds for seed to finish and toast to appear
        page.wait_for_selector(".toast.show", timeout=45000)
        toast_text = page.locator("#toast").inner_text()
        print(f"Toast: '{toast_text}'")
        assert "Loaded" in toast_text

        # 5. Test Decision Room (Generate next best action with Hindsight)
        print("\n5. Testing Decision Room with Hindsight Recall + Reflect...")
        page.locator("#decision-room").scroll_into_view_if_needed()
        page.fill("#situation", "The customer says our price is too high and Competitor X is cheaper.")
        page.screenshot(path=os.path.join(ARTIFACTS_DIR, "04_decision_room_prompt.png"))
        
        page.locator("button:has-text('Generate next best action')").click()
        
        # Wait for recommendation (Hindsight reflect can take 5-15s)
        page.wait_for_selector("#sourceBadge:has-text('HINDSIGHT')", timeout=45000)
        badge_src = page.locator("#sourceBadge").inner_text()
        rec_text = page.locator("#recommendation").inner_text()
        print(f"Source Badge: {badge_src}")
        print(f"Recommendation preview: {rec_text[:200]}...")
        assert "HINDSIGHT" in badge_src
        assert len(rec_text) > 50

        page.screenshot(path=os.path.join(ARTIFACTS_DIR, "05_hindsight_recommendation.png"))
        print("✓ Decision Room Hindsight Recall & Reflect successful!")

        # 6. Test Learning Experiment
        print("\n6. Testing Signature Learning Experiment...")
        page.locator("#experiment").scroll_into_view_if_needed()
        page.screenshot(path=os.path.join(ARTIFACTS_DIR, "06_experiment_before.png"))
        page.locator("button:has-text('Run learning experiment')").click()

        # Wait for experiment result
        page.wait_for_selector(".experiment-grid", timeout=45000)
        exp_delta = page.locator(".delta").inner_text()
        print(f"Learning Delta: {exp_delta}")
        assert "MEMORY CHANGED" in exp_delta or "changed" in exp_delta.lower()

        page.screenshot(path=os.path.join(ARTIFACTS_DIR, "07_experiment_complete.png"))
        print("✓ Signature Learning Experiment verified!")

        # 7. Test Deal Autopsy
        print("\n7. Testing Deal Autopsy...")
        page.locator(".autopsy").scroll_into_view_if_needed()
        page.fill("#autopsyTitle", "Discount-first failed on procurement review")
        page.fill("#autopsyContent", "Sales team offered a 15% discount upfront. Procurement asked for an additional 20% and stalled the decision.")
        page.select_option("#autopsyOutcome", "Failed / stalled")
        page.screenshot(path=os.path.join(ARTIFACTS_DIR, "08_autopsy_filled.png"))
        
        page.locator("button:has-text('Retain experience')").click()
        page.wait_for_selector(".toast.show", timeout=25000)
        autopsy_toast = page.locator("#toast").inner_text()
        print(f"Autopsy Toast: {autopsy_toast}")
        assert "retained" in autopsy_toast.lower()
        print("✓ Deal Autopsy retained successfully in Hindsight!")

        # 8. Check console errors
        print("\n8. Checking browser console logs...")
        critical_errors = [l for l in console_logs if "[error]" in l or "[pageerror]" in l]
        if critical_errors:
            print("Console errors detected:")
            for err in critical_errors:
                print(f"  {err}")
        else:
            print("✓ No browser console errors.")

        browser.close()
        print("\n=== ALL 3 LAYERS TESTED AND PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run()
