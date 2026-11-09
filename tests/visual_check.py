from pathlib import Path
import base64
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "tests" / "visual-report"
REPORT.mkdir(parents=True, exist_ok=True)

html = (ROOT / "frontend/index.html").read_text()
css = (ROOT / "frontend/styles.css").read_text()
js = (ROOT / "frontend/app.js").read_text()
for asset in ["memory-field.svg", "learning-loop.svg", "memory-evidence.svg"]:
    raw = (ROOT / "frontend/assets" / asset).read_bytes()
    data = "data:image/svg+xml;base64," + base64.b64encode(raw).decode()
    html = html.replace(f'assets/{asset}', data)
html = html.replace('<link rel="stylesheet" href="styles.css">', f'<style>{css}</style>')
html = html.replace('<script src="app.js"></script>', f'<script>{js}</script>')

mock_fetch = """
window.fetch = async (url, options={}) => {
  const path = String(url);
  let data = {};
  if (path.includes('/api/health')) data = {hindsight_configured:true};
  else if (path.endsWith('/api/deals') && (!options.method || options.method === 'GET')) data = [{id:'demo',name:'Enterprise Revenue Intelligence',company:'Northstar Analytics',value:185000,stage:'Negotiation',owner:'Sales Rep',summary:'Enterprise analytics deal.'}];
  else if (path.includes('/api/stats/')) data = {experiences:3,positive:2,negative:1,learning_ratio:.66};
  else if (path.includes('/api/learning/')) data = {timeline:[]};
  else if (path.includes('/api/playbook/')) data = {winning_patterns:[],failed_patterns:[]};
  return {ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data)};
};
"""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path="/usr/bin/chromium", args=["--no-sandbox"])
    page = browser.new_page(viewport={"width":1440,"height":900}, device_scale_factor=1)
    errors=[]
    page.on("console", lambda msg: errors.append(f"console {msg.type}: {msg.text}") if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    page.add_init_script(mock_fetch)
    page.set_content(html, wait_until="domcontentloaded")
    page.wait_for_timeout(800)
    page.screenshot(path=str(REPORT / "desktop-top.png"), full_page=False)

    assert page.locator(".hero h1").bounding_box() is not None
    assert page.locator(".loop-node").count() == 4
    assert page.locator(".memory-evidence").count() == 3
    assert page.locator(".brand-name").bounding_box()["width"] > 80
    body_width = page.locator("body").evaluate("el => el.scrollWidth")
    assert body_width <= 1442, f"desktop horizontal overflow: {body_width}"

    page.locator("#loop").scroll_into_view_if_needed()
    page.wait_for_timeout(700)
    page.screenshot(path=str(REPORT / "desktop-loop.png"), full_page=False)
    assert page.locator(".loop-node.active").count() >= 1
    loop_box = page.locator(".loop-visual").bounding_box()
    copy_box = page.locator(".loop-copy").bounding_box()
    assert loop_box and copy_box and loop_box["x"] > copy_box["x"] + copy_box["width"] * .75, "loop visual collides with copy"

    mobile = browser.new_page(viewport={"width":390,"height":844}, device_scale_factor=1)
    mobile.add_init_script(mock_fetch)
    mobile.set_content(html, wait_until="domcontentloaded")
    mobile.wait_for_timeout(500)
    mobile.screenshot(path=str(REPORT / "mobile-top.png"), full_page=False)
    mobile_width = mobile.locator("body").evaluate("el => el.scrollWidth")
    assert mobile_width <= 392, f"mobile horizontal overflow: {mobile_width}"
    mobile.locator("#loop").scroll_into_view_if_needed(); mobile.wait_for_timeout(400)
    mobile.screenshot(path=str(REPORT / "mobile-loop.png"), full_page=False)

    if errors:
        raise AssertionError("Browser errors:\n" + "\n".join(errors))

    print("PLAYWRIGHT VISUAL CHECK: PASS")
    print("Desktop: 1440x900")
    print("Mobile: 390x844")
    print("Horizontal overflow: none")
    print("Learning loop activation: PASS")
    print("Loop/copy collision gate: PASS")
    browser.close()
