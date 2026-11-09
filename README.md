# DealRescue AI Winning Build v4

**Sales & Revenue → Deal Intelligence Agent**

DealRescue is an experience-learning sales agent. It does not merely retrieve conversation history: it uses Hindsight to retain sales experiences, recall relevant outcomes, and reflect on those experiences before recommending the next action.

## The differentiator

> **DealRescue learns which sales interventions actually rescue deals.**

### Core loop

Current situation → Hindsight Recall → Hindsight Reflect → Next Best Action → Sales Outcome → Hindsight Retain → Better future recommendation

## Judge-facing features

- Hindsight retain / recall / reflect
- 12 realistic sales experiences
- Deal Rescue Score
- Positive vs negative outcome signals
- Before/after learning experiment that actually retains a new outcome and re-evaluates the same situation
- Before/after learning panel
- Winning Playbook
- Deal Autopsy that turns failures into retained experiences
- Transparent memory evidence
- Deal CRUD
- Realistic enterprise scenario
- Deterministic fallback if external AI is unavailable

## Windows quick start

```powershell
cd "DealRescue_AI_WINNING_BUILD_v4"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
copy .env.example .env
notepad .env
uvicorn backend.main:app --reload
```

Open `http://localhost:8000`.

Set `HINDSIGHT_API_KEY` in `.env`. Do not commit `.env`.

## 60-second demo

1. Open Northstar Analytics.
2. Click **Load 12 realistic experiences**.
3. Say: “The customer says our price is too high and Competitor X is cheaper.”
4. Click **Generate Next Best Action**.
5. Show the memory evidence: a discount-first tactic stalled, while ROI/value conversations progressed.
6. Click **Run learning experiment** and show the cold-start recommendation vs the experience-backed recommendation.
7. Point out the retained outcome and the explicit “recommendation changed because of memory” message.
8. Use **Deal Autopsy** to record another outcome and show it in the memory journey/playbook.

## Hackathon positioning

Do not call it a chatbot with memory.

Say:

> “Most sales AI gives advice from a model. DealRescue gives advice from accumulated sales experience — including failures — and learns which interventions actually move a deal forward.”

## Submission checklist

- [ ] Hindsight LIVE visible
- [ ] Real API key in `.env`
- [ ] Seed experiences retained successfully
- [ ] Recommendation shows Hindsight evidence
- [ ] Before/after learning story demonstrated
- [ ] Deal autopsy demonstrated
- [ ] GitHub repository cleaned of `.env` and `.venv`
- [ ] 60-second demo recorded
- [ ] README explains Hindsight usage
- [ ] Band AI desktop workflow/content requirements completed if required by the event


## Important: run the UI through FastAPI

Do not open `frontend/index.html` by double-clicking it. The UI calls `/api/...` routes and must be served by FastAPI.

From this project folder:

```powershell
.\START_DEALRESCUE.ps1
```

Then open:

```text
http://127.0.0.1:8000/
```

The frontend asset URLs are relative (`styles.css`, `app.js`) so the visual shell also loads correctly when the frontend is served from its own directory.

### If the page shows `BACKEND OFFLINE`

1. Make sure the PowerShell window running Uvicorn is still open.
2. Open `http://127.0.0.1:8000/`.
3. Hard refresh with `Ctrl + Shift + R`.
4. Do not use the VS Code Live Server URL for the final demo.

### What was fixed in this version

- Removed startup failures caused by missing optional dashboard DOM nodes.
- Fixed risk badge handling when the badge is not rendered.
- Made memory evidence visible in the learning section.
- Added live experience/positive/negative/learning counters.
- Made parallax use a CSS transform variable so it does not overwrite other transforms.
- Added a reliable startup path for Windows.
- Kept Hindsight, FastAPI, recommendation, learning experiment and deal autopsy APIs intact.

## Visual design + verification

The frontend is governed by `DESIGN.md`. It defines typography, spacing, grid, color, motion and responsive gates so future changes do not drift into arbitrary styling.

The visual layer uses SVG assets under `frontend/assets/` and a scroll-driven Learning Loop. The loop path is an SVG path whose stroke progress is controlled by scroll position; the four stages activate progressively.

### Playwright verification

Install development tooling:

```powershell
python -m pip install -r requirements-dev.txt
playwright install chromium
```

Run the visual gates:

```powershell
python tests/visual_check.py
```

The check covers:
- 1440x900 desktop layout
- 390x844 mobile layout
- horizontal overflow
- hero rendering
- four Learning Loop nodes
- live memory evidence cards
- scroll activation of the Learning Loop
- collision between loop copy and loop visual
- browser console/page errors

For the production browser test, start the app with `START_DEALRESCUE.ps1` and use the same Playwright checks against `http://127.0.0.1:8000/`.


## v3 reliability + demo upgrades

This version keeps the existing FastAPI/Hindsight architecture and adds:

- Page 2 is content-driven instead of leaving a large empty visual gap.
- The Learning Loop is a true closed Recall → Reflect → Decide → Retain path.
- Desktop loop is an SVG closed path; mobile becomes a readable vertical sequence.
- Reveal animation now fails open: sections remain visible even if the observer cannot initialize.
- Backend health is isolated from dashboard-widget failures, so a healthy API is not incorrectly shown as offline.
- New Deal uses the actual modal field IDs and has validation, loading state, success feedback, workspace refresh and focus handling.
- Added a visible “Load 12 demo experiences” action for the judge/demo flow.
- Added a correct navigation target for the Decision Room.
- `file://` usage can still reach the FastAPI API at `127.0.0.1:8000`, although the recommended demo path remains the FastAPI root URL.

This submission package is aligned to the hackathon requirements documented for DealRescue. Verify any event-specific portal fields, file-size limits, deadlines, and required Band AI deliverables before final upload.
