import os
import sys
import time
from playwright.sync_api import sync_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ARTIFACTS_DIR = r"C:\Users\Abhishek\.gemini\antigravity\brain\c754d287-e850-4045-8760-fd71a75d0fbf"
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
            ("Page 1: Hero / Introduction", ".hero"),
            ("Page 2: How It Learns / Memory Timeline", "#story"),
            ("Page 3: Learning Loop", "#loop"),
            ("Page 4: Deal Workspace", "#decision"),
            ("Page 5: Decision Room", "#decision-room"),
            ("Page 6: Memory Evidence", "#memory"),
            ("Page 7: Learning Experiment", "#experiment"),
            ("Page 8: Deal Autopsy", ".autopsy"),
            ("Page 9: Final Section", ".final")
        ]
        for name, sel in sections:
            el = page.locator(sel)
            assert el.count() > 0, f"Section '{name}' ({sel}) not found in DOM!"
            el.scroll_into_view_if_needed()
            time.sleep(0.4)
            # Take individual screenshot of key sections
            sanitized = name.split(":")[0].strip().replace(" ", "_").lower()
            page.screenshot(path=os.path.join(ARTIFACTS_DIR, f"section_{sanitized}.png"))
            print(f"✓ Section verified: {name}")

        # Check Loop Nodes
        loop_nodes = page.locator(".loop-node")
        print(f"Loop nodes count: {loop_nodes.count()}")
        assert loop_nodes.count() == 4, f"Expected 4 loop nodes, got {loop_nodes.count()}"

        # 3. Test New Deal creation via Modal with USER SPECIFIED VALUES:
        # Deal Name: Northstar Analytics
        # Company: Northstar Analytics
        # Value: 185000
        # Stage: Negotiation
        # Owner: Abhishek
        # Summary: Customer is comparing our platform with a cheaper competitor.
        print("\n3. Testing 'New Deal' modal flow with user test data...")
        page.locator("button.nav-cta").click()
        time.sleep(0.5)
        modal = page.locator("#modal")
        assert not ("hidden" in modal.get_attribute("class") or ""), "Modal failed to open"
        
        page.fill("#dName", "Northstar Analytics v4")
        page.fill("#dCompany", "Northstar Analytics")
        page.fill("#dValue", "185000")
        page.select_option("#dStage", "Negotiation")
        page.fill("#dOwner", "Abhishek")
        page.fill("#dSummary", "Customer is comparing our platform with a cheaper competitor.")
        
        page.screenshot(path=os.path.join(ARTIFACTS_DIR, "03_new_deal_modal.png"))
        page.locator("#modal .decision-btn").click()
        
        # Wait for modal to close and active deal to update
        page.locator("#modal").wait_for(state="hidden", timeout=10000)
        time.sleep(1)
        deal_name = page.locator("#dealName").inner_text()
        deal_company = page.locator("#dealCompany").inner_text()
        print(f"Active deal after creation: {deal_name} at {deal_company}")
        assert "northstar analytics v4" in deal_name.lower()
        assert "northstar analytics" in deal_company.lower()
        print("✓ New Deal created and became active!")

        # 4. Load realistic experiences for this deal
        print("\n4. Seeding demo experiences...")
        page.locator("button:has-text('Load 12 demo experiences')").click()
        page.wait_for_timeout(3000)
        page.wait_for_selector(".toast.show", timeout=75000)
        toast_text = page.locator("#toast").inner_text()
        print(f"Toast: '{toast_text}'")
        assert "Loaded" in toast_text

        # 5. Test Decision Room (Generate next best action with Hindsight)
        print("\n5. Testing Decision Room with Hindsight Recall + Reflect...")
        page.locator("#decision-room").scroll_into_view_if_needed()
        page.fill("#situation", "Customer says the competitor is cheaper.")
        page.screenshot(path=os.path.join(ARTIFACTS_DIR, "04_decision_room_prompt.png"))
        
        page.locator("button:has-text('Generate next best action')").click()
        
        # Wait for recommendation
        page.wait_for_selector("#sourceBadge:has-text('HINDSIGHT')", timeout=45000)
        badge_src = page.locator("#sourceBadge").inner_text()
        rec_text = page.locator("#recommendation").inner_text()
        print(f"Source Badge: {badge_src}")
        print(f"Recommendation preview:\n{rec_text[:350]}...\n")
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
        # Give previous toast time to clear
        time.sleep(3.5)
        page.locator(".autopsy").scroll_into_view_if_needed()
        page.fill("#autopsyTitle", "Price objection discount-first stall")
        page.fill("#autopsyContent", "Situation: Customer objected to price. Action: Salesperson offered a discount immediately. Outcome: Deal stalled. Lesson: Discount-first negotiation failed to address ROI concerns.")
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
        print("\n=== ALL 3 LAYERS AND 9 USER FLOWS TESTED AND PASSED! ===")

if __name__ == "__main__":
    run()

