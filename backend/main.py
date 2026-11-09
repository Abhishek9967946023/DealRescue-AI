
import os, json, uuid, re
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from hindsight_client import Hindsight
except Exception:
    Hindsight = None

APP_DIR = os.path.dirname(__file__)
DATA_FILE = os.getenv("DATA_FILE", os.path.join(APP_DIR, "..", "data", "deals.json"))
os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

HINDSIGHT_URL = os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
HINDSIGHT_KEY = os.getenv("HINDSIGHT_API_KEY", "")
BANK_PREFIX = os.getenv("HINDSIGHT_BANK_PREFIX", "dealrescue")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

app = FastAPI(title="DealRescue AI", version="3.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"deals": [], "interactions": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("deals", [])
    data.setdefault("interactions", [])
    return data

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def hindsight_client():
    key = os.getenv("HINDSIGHT_API_KEY", "") or HINDSIGHT_KEY
    url = os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io") or HINDSIGHT_URL
    if not Hindsight or not key:
        return None
    try:
        return Hindsight(base_url=url, api_key=key, timeout=45.0)
    except Exception:
        return None

def bank_id(deal_id):
    return f"{BANK_PREFIX}-{deal_id}".replace("_", "-")[:60]

def ensure_bank(hc, deal_id):
    try:
        hc.create_bank(
            bank_id=bank_id(deal_id),
            name=f"DealRescue {deal_id}",
            disposition={"skepticism": 4, "literalism": 3, "empathy": 3}
        )
    except Exception:
        # Bank may already exist.
        pass

def token_set(text):
    return set(re.findall(r"\w+", (text or "").lower()))

def local_memories(deal_id, query=""):
    data = load_data()
    rows = [x for x in data["interactions"] if x.get("deal_id") == deal_id]
    q = token_set(query)
    if q:
        rows.sort(
            key=lambda x: len(q & token_set(
                x.get("title", "") + " " + x.get("content", "") + " " + x.get("outcome", "")
            )),
            reverse=True
        )
    return rows[:12]

def outcome_signal(row):
    text = (row.get("outcome", "") + " " + row.get("content", "")).lower()
    if any(k in text for k in ["worked", "won", "successful", "accepted", "progressed", "reduced"]):
        return "positive"
    if any(k in text for k in ["failed", "lost", "rejected", "stalled", "dropped", "poorly"]):
        return "negative"
    return "neutral"

class Deal(BaseModel):
    name: str
    company: str
    value: float = 0
    stage: str = "Discovery"
    owner: str = "Sales Rep"
    summary: str = ""

class DealUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    value: Optional[float] = None
    stage: Optional[str] = None
    owner: Optional[str] = None
    summary: Optional[str] = None

class Interaction(BaseModel):
    deal_id: str
    title: str = "Sales interaction"
    content: str
    outcome: str = ""
    occurred_at: Optional[str] = None

class RecommendationRequest(BaseModel):
    deal_id: str
    situation: str = ""

class SeedRequest(BaseModel):
    deal_id: str
    count: int = Field(default=10, ge=1, le=30)

@app.get("/api/health")
def health():
    hc = hindsight_client()
    return {
        "ok": True,
        "hindsight_configured": bool(hc),
        "llm_configured": bool(GROQ_API_KEY),
        "version": "3.1.0"
    }

@app.get("/api/deals")
def deals():
    return load_data()["deals"]

@app.post("/api/deals")
def create_deal(deal: Deal):
    data = load_data()
    item = deal.model_dump()
    item["id"] = uuid.uuid4().hex[:8]
    item["created_at"] = datetime.utcnow().isoformat()
    data["deals"].append(item)
    save_data(data)
    return item

@app.get("/api/deals/{deal_id}")
def get_deal(deal_id: str):
    data = load_data()
    deal = next((x for x in data["deals"] if x.get("id") == deal_id), None)
    if not deal:
        raise HTTPException(404, "Deal not found")
    return deal

@app.put("/api/deals/{deal_id}")
def update_deal(deal_id: str, update: DealUpdate):
    data = load_data()
    for item in data["deals"]:
        if item.get("id") == deal_id:
            item.update({k: v for k, v in update.model_dump(exclude_unset=True).items() if v is not None})
            save_data(data)
            return item
    raise HTTPException(404, "Deal not found")

@app.delete("/api/deals/{deal_id}")
def delete_deal(deal_id: str):
    data = load_data()
    before = len(data["deals"])
    data["deals"] = [x for x in data["deals"] if x.get("id") != deal_id]
    data["interactions"] = [x for x in data["interactions"] if x.get("deal_id") != deal_id]
    if len(data["deals"]) == before:
        raise HTTPException(404, "Deal not found")
    save_data(data)
    return {"deleted": True}

@app.get("/api/deals/{deal_id}/memories")
def memories(deal_id: str, q: str = ""):
    hc = hindsight_client()
    if hc:
        try:
            ensure_bank(hc, deal_id)
            query = q or "pricing objections competitors stakeholders outcomes successful failed sales actions"
            result = hc.recall(bank_id=bank_id(deal_id), query=query, max_tokens=4000)
            rows = []
            for x in getattr(result, "results", []) or []:
                text = getattr(x, "text", None) or getattr(x, "content", None) or str(x)
                rows.append({
                    "text": text,
                    "type": getattr(x, "type", "memory"),
                    "source": "hindsight"
                })
            if rows:
                return {"memories": rows[:8], "source": "hindsight"}
        except Exception:
            pass

    rows = []
    for x in local_memories(deal_id, q):
        rows.append({
            "text": f"{x.get('title','Experience')}: {x.get('content','')} | Outcome: {x.get('outcome','')}",
            "type": "experience",
            "source": "local-evidence"
        })
    return {"memories": rows[:8], "source": "local-evidence"}

@app.post("/api/interactions")
def add_interaction(item: Interaction):
    data = load_data()
    obj = item.model_dump()
    obj["id"] = uuid.uuid4().hex[:10]
    obj["occurred_at"] = obj["occurred_at"] or datetime.utcnow().isoformat()
    data["interactions"].append(obj)
    save_data(data)

    hc = hindsight_client()
    hs_status = "local-only"
    if hc:
        try:
            ensure_bank(hc, item.deal_id)
            content = (
                f"Deal ID: {item.deal_id}\n"
                f"Experience: {item.title}\n"
                f"Details: {item.content}\n"
                f"Outcome: {item.outcome or 'Outcome not yet recorded'}\n"
                "Learn the action, objection, context, and outcome for future sales decisions."
            )
            hc.retain(
                bank_id=bank_id(item.deal_id),
                content=content,
                context="DealRescue sales experience"
            )
            hs_status = "retained-in-hindsight"
        except Exception:
            hs_status = "hindsight-error"
    return {"saved": obj, "hindsight": hs_status}

def seed_templates():
    return [
        ("Price objection", "Customer said the proposal was expensive and asked for a discount.",
         "Discount-first response did not move the deal forward."),
        ("ROI discussion", "Buyer asked how the solution would pay for itself.",
         "ROI walkthrough increased interest and they requested a technical follow-up."),
        ("Competitor X", "CTO said Competitor X is already on the shortlist.",
         "Feature-by-feature attack was poorly received."),
        ("Deployment concern", "Customer requires deployment within 30 days.",
         "A milestone-based deployment plan was well received."),
        ("Security concern", "Security team requested architecture and data-handling details.",
         "Security architecture session reduced risk concerns."),
        ("Stakeholder change", "Procurement joined and focused on commercial terms.",
         "Reframing around total cost of ownership kept the conversation moving."),
        ("Missed follow-up", "A promised integration document was sent two days late.",
         "Customer confidence dropped; future follow-ups should be tracked."),
        ("Successful proof", "A short proof-of-value using the customer workflow was completed.",
         "Champion agreed to introduce the solution to the VP."),
        ("Budget freeze", "Customer paused purchase due to quarterly budget constraints.",
         "A smaller phased rollout kept the opportunity alive."),
        ("Executive priority", "VP emphasized time-to-value over feature breadth.",
         "Executive summary focused on time saved generated a positive response."),
        ("Legal delay", "Legal requested a new data-processing clause.",
         "A prepared redline package reduced turnaround time."),
        ("Champion risk", "Internal champion moved roles and sponsorship weakened.",
         "Multi-threading with the VP and procurement protected deal momentum.")
    ]

@app.post("/api/seed")
def seed(req: SeedRequest):
    deal = get_deal(req.deal_id)
    data = load_data()
    hc = hindsight_client()
    if hc:
        try:
            ensure_bank(hc, req.deal_id)
        except Exception:
            pass

    templates = seed_templates()
    chosen = templates[:req.count]
    statuses = []

    # Avoid duplicate seeding of the same titles for this deal.
    existing_titles = {x.get("title") for x in data["interactions"] if x.get("deal_id") == req.deal_id}
    for title, content, outcome in chosen:
        if title in existing_titles:
            continue

        obj = {
            "id": uuid.uuid4().hex[:10],
            "deal_id": req.deal_id,
            "title": title,
            "content": content,
            "outcome": outcome,
            "occurred_at": datetime.utcnow().isoformat()
        }
        data["interactions"].append(obj)
        status = "local"
        if hc:
            try:
                hc.retain(
                    bank_id=bank_id(req.deal_id),
                    content=(
                        f"Deal: {deal['name']} at {deal['company']}\n"
                        f"Experience: {title}\nDetails: {content}\nOutcome: {outcome}"
                    ),
                    context="DealRescue synthetic historical sales experience"
                )
                status = "hindsight"
            except Exception:
                status = "hindsight-error"
        statuses.append(status)

    save_data(data)
    return {"seeded": len(statuses), "statuses": statuses, "hindsight_configured": bool(hc)}

def deterministic_recommendation(deal, mems, situation):
    all_text = " ".join(
        (m.get("content", "") + " " + m.get("outcome", "")) for m in mems
    ).lower()
    wins = [m for m in mems if outcome_signal(m) == "positive"]
    fails = [m for m in mems if outcome_signal(m) == "negative"]

    text = (all_text + " " + situation.lower())
    risk = "Medium"
    if any(k in text for k in ["competitor", "budget", "price", "security", "legal", "urgent"]):
        risk = "High"
    if len(mems) >= 5 and len(wins) > len(fails):
        risk = "Medium"

    if "price" in text or "expensive" in text or "budget" in text:
        if not mems:
            action = "Explore a targeted commercial concession if needed, but first confirm the buyer's budget and decision criteria."
            why = "Cold-start guidance: there is no accumulated deal experience yet, so the agent has no outcome evidence about which pricing tactic worked."
        else:
            action = "Do not lead with a discount. Lead with measurable ROI, total cost of ownership, and the buyer's business outcome."
            why = f"{len(mems)} relevant experiences: {len(wins)} positive and {len(fails)} negative. Pricing pressure has a stronger value-led pattern than discount-first."
    elif "competitor" in text:
        action = "Do not attack the competitor. Compare the buyer's success criteria and show where your solution reduces risk or time-to-value."
        why = f"{len(mems)} relevant experiences were found; competitor attacks were weaker than evidence-led differentiation."
    elif "security" in text:
        action = "Run a focused security evidence session. Map each concern to a concrete control, owner, and deadline."
        why = "Security concerns are best handled with verifiable evidence and a named follow-up owner."
    elif "budget" in text:
        action = "Protect deal momentum with a phased scope or measurable business case before discussing concessions."
        why = "Past budget pressure is better handled by preserving value and reducing initial scope."
    else:
        action = "Ask one diagnostic question, choose one measurable action, and schedule a specific follow-up."
        why = f"{len(mems)} experiences were found; use the strongest outcome-backed pattern rather than generic advice."

    return {
        "risk": risk,
        "action": action,
        "why": why,
        "wins": len(wins),
        "fails": len(fails),
        "talk_track": "Before we discuss terms, can we confirm the single outcome that matters most to your team at this stage?",
        "avoid": "Do not invent customer facts, repeat a failed tactic, or give away value before understanding the decision criterion."
    }

@app.post("/api/recommend")
def recommend(req: RecommendationRequest):
    deal = get_deal(req.deal_id)
    hc = hindsight_client()
    hindsight_memories = []
    source = "local-evidence"

    if hc:
        try:
            ensure_bank(hc, req.deal_id)
            query = req.situation or "Relevant sales experiences, objections, actions, outcomes, successes and failures"
            result = hc.recall(bank_id=bank_id(req.deal_id), query=query, max_tokens=5000)
            for x in getattr(result, "results", []) or []:
                text = getattr(x, "text", None) or getattr(x, "content", None) or str(x)
                hindsight_memories.append(text)

            if hindsight_memories:
                source = "hindsight-recall"

                # Reflect is deliberately invoked after recall: memory is the reasoning input.
                try:
                    reflection = hc.reflect(
                        bank_id=bank_id(req.deal_id),
                        query=(
                            f"{req.situation or 'Prepare for the next customer meeting.'}\n"
                            "Using the remembered experiences, identify the best next action, "
                            "what to avoid, and the evidence behind the recommendation."
                        ),
                        context="DealRescue: use stored sales experiences as decision evidence."
                    )
                    answer = getattr(reflection, "text", None) or str(reflection)
                    return {
                        "answer": answer,
                        "memories": hindsight_memories[:8],
                        "source": "hindsight-reflect",
                        "memory_count": len(hindsight_memories),
                        "risk": deterministic_recommendation(deal, local_memories(req.deal_id, req.situation), req.situation)["risk"]
                    }
                except Exception:
                    pass
        except Exception:
            source = "hindsight-unavailable"

    local = local_memories(req.deal_id, req.situation)
    result = deterministic_recommendation(deal, local, req.situation)

    answer = (
        f"DEAL RISK\n{result['risk']}\n\n"
        f"WHAT MEMORY SAYS\n{len(local)} relevant experiences were found; "
        f"{result['wins']} positive and {result['fails']} negative outcome signals.\n\n"
        f"RECOMMENDED NEXT ACTION\n{result['action']}\n\n"
        f"WHY\n{result['why']}\n\n"
        f"DO NOT DO\n{result['avoid']}\n\n"
        f"TALK TRACK\n{result['talk_track']}"
    )

    return {
        "answer": answer,
        "memories": [
            f"{x.get('title','Experience')}: {x.get('content','')} | Outcome: {x.get('outcome','')}"
            for x in local[:8]
        ],
        "source": source,
        "memory_count": len(local),
        "risk": result["risk"]
    }


class LearningExperimentRequest(BaseModel):
    deal_id: str
    situation: str
    action_taken: str = "Offered a discount immediately"
    outcome: str = "Failed / stalled"
    outcome_notes: str = "The customer still wanted stronger ROI evidence and the deal stalled."

@app.post("/api/learning-experiment")
def learning_experiment(req: LearningExperimentRequest):
    """Demonstrate the real Hindsight learning loop.

    The experiment intentionally starts from a cold-start baseline, retains a new outcome,
    recalls the updated memory bank, and asks Hindsight to reflect on that memory before
    producing the after-decision. Local evidence remains an explicit fallback when Hindsight
    is not configured or temporarily unavailable.
    """
    deal = get_deal(req.deal_id)
    before = deterministic_recommendation(deal, [], req.situation)

    interaction = Interaction(
        deal_id=req.deal_id,
        title="Learning experiment — failed discount-first tactic",
        content=(
            f"Situation: {req.situation}\n"
            f"Action tried: {req.action_taken}\n"
            f"Outcome notes: {req.outcome_notes}"
        ),
        outcome=req.outcome,
    )
    retained = add_interaction(interaction)

    hindsight_used = False
    hindsight_recalled = []
    reflection_text = ""
    after_source = "local-evidence"

    hc = hindsight_client()
    if hc:
        try:
            ensure_bank(hc, req.deal_id)
            recall_result = hc.recall(
                bank_id=bank_id(req.deal_id),
                query=req.situation,
                max_tokens=5000,
            )
            for x in getattr(recall_result, "results", []) or []:
                txt = getattr(x, "text", None) or getattr(x, "content", None) or str(x)
                if txt.strip():
                    hindsight_recalled.append(txt.strip())

            if hindsight_recalled:
                hindsight_used = True
                try:
                    reflection = hc.reflect(
                        bank_id=bank_id(req.deal_id),
                        query=(
                            f"Current sales situation: {req.situation}\n\n"
                            "Use the recalled experiences as evidence. Compare what worked and failed. "
                            "Recommend the safest next action, explicitly avoid repeating failed tactics, "
                            "and explain which remembered outcomes support the decision."
                        ),
                        context="DealRescue learning experiment: demonstrate retain -> recall -> reflect.",
                    )
                    reflection_text = getattr(reflection, "text", None) or str(reflection)
                    after_source = "hindsight-recall-reflect"
                except Exception:
                    after_source = "hindsight-recall"
        except Exception:
            hindsight_used = False

    after_local = local_memories(req.deal_id, req.situation)
    after = deterministic_recommendation(deal, after_local, req.situation)

    if reflection_text:
        after_action = reflection_text
        after_why = "Hindsight recalled the updated experience bank and reflected on the remembered outcomes before producing this decision."
    else:
        after_action = after["action"]
        after_why = after["why"]

    changed = before["action"] != after_action
    return {
        "before": {
            "label": "Cold-start — no experience memory",
            "action": before["action"],
            "why": before["why"],
            "risk": before["risk"],
        },
        "retained": {
            "status": retained.get("hindsight", "local-only"),
            "title": interaction.title,
            "outcome": interaction.outcome,
            "lesson": req.outcome_notes,
        },
        "after": {
            "label": "Hindsight recall + reflection",
            "action": after_action,
            "why": after_why,
            "risk": after["risk"],
            "wins": after["wins"],
            "fails": after["fails"],
            "memory_count": len(hindsight_recalled) or len(after_local),
            "source": after_source,
            "recalled": hindsight_recalled[:6],
        },
        "changed": changed,
        "hindsight": {
            "configured": bool(hc),
            "used": hindsight_used,
            "retained": retained.get("hindsight", "local-only"),
            "recall_count": len(hindsight_recalled),
            "reflect_used": bool(reflection_text),
        },
        "message": "Cold-start baseline -> retain outcome -> Hindsight recall -> Hindsight reflect -> updated decision.",
    }

@app.get("/api/memory-proof/{deal_id}")
def memory_proof(deal_id: str, q: str = ""):
    """Return judge-visible evidence about the memory layer without exposing secrets."""
    get_deal(deal_id)
    hc = hindsight_client()
    local = local_memories(deal_id, q)
    proof = {
        "hindsight_configured": bool(hc),
        "bank_id": bank_id(deal_id),
        "local_experiences": len(local),
        "positive": sum(outcome_signal(x) == "positive" for x in local),
        "negative": sum(outcome_signal(x) == "negative" for x in local),
        "recall": {"status": "not-run", "count": 0, "source": "none"},
        "reflect": {"status": "not-run"},
    }
    if hc:
        try:
            ensure_bank(hc, deal_id)
            result = hc.recall(
                bank_id=bank_id(deal_id),
                query=q or "pricing objections competitor ROI successful failed sales experiences",
                max_tokens=3000,
            )
            items = []
            for x in getattr(result, "results", []) or []:
                txt = getattr(x, "text", None) or getattr(x, "content", None) or str(x)
                if txt.strip():
                    items.append(txt.strip())
            proof["recall"] = {"status": "live", "count": len(items), "source": "hindsight", "evidence": items[:4]}
        except Exception as exc:
            proof["recall"] = {"status": "error", "count": 0, "source": "hindsight", "error": type(exc).__name__}
    return proof

@app.get("/api/stats/{deal_id}")
def stats(deal_id: str):
    rows = local_memories(deal_id)
    positive = sum(outcome_signal(x) == "positive" for x in rows)
    negative = sum(outcome_signal(x) == "negative" for x in rows)
    neutral = len(rows) - positive - negative
    return {
        "experiences": len(rows),
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "learning_ratio": round(positive / max(1, positive + negative), 2)
    }

@app.get("/api/learning/{deal_id}")
def learning(deal_id: str):
    rows = local_memories(deal_id)
    return {
        "timeline": [
            {
                "title": x.get("title"),
                "outcome": x.get("outcome"),
                "signal": outcome_signal(x),
                "date": x.get("occurred_at")
            }
            for x in rows[:12]
        ]
    }

@app.get("/api/playbook/{deal_id}")
def playbook(deal_id: str):
    rows = local_memories(deal_id)
    successful = [x for x in rows if outcome_signal(x) == "positive"]
    failed = [x for x in rows if outcome_signal(x) == "negative"]
    return {
        "winning_patterns": [x.get("title") + ": " + x.get("outcome", "") for x in successful[:5]],
        "failed_patterns": [x.get("title") + ": " + x.get("outcome", "") for x in failed[:5]],
        "recommendation": "Prefer tactics with repeated positive outcomes; explicitly avoid tactics associated with stalled or lost momentum."
    }

@app.post("/api/autopsy")
def autopsy(item: Interaction):
    # A "deal autopsy" is intentionally retained as an experience.
    item.title = item.title or "Deal autopsy"
    return add_interaction(item)

app.mount("/", StaticFiles(directory=os.path.join(APP_DIR, "..", "frontend"), html=True), name="frontend")
