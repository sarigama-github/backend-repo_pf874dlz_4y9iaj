import os
from datetime import datetime, timezone
from typing import List, Dict, Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import (
    Session as SessionModel,
    InteractionEvent as InteractionEventModel,
    EmotionalProfile,
    Tea as TeaModel,
    Recommendation as RecommendationModel,
    JournalEntry as JournalEntryModel,
    SCHEMA_REGISTRY,
)

app = FastAPI(title="Tee & Seele API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Tee & Seele Backend Running"}


@app.get("/schema")
def get_schema():
    return SCHEMA_REGISTRY


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# --------- Core Models for requests ---------
class CreateSessionRequest(BaseModel):
    locale: str | None = None
    device: str | None = None


class ConsentRequest(BaseModel):
    session_id: str
    accepted: bool


class InteractionIn(BaseModel):
    session_id: str
    type: str
    intensity: float | None = 1.0
    value: float | None = None
    meta: Dict[str, Any] | None = None


class JournalIn(BaseModel):
    session_id: str
    mood: str
    notes: str | None = None


# --------- Helper: seed initial teas ---------
DEFAULT_TEAS: List[Dict[str, Any]] = [
    {
        "slug": "kamille",
        "name": "Kamille",
        "latin": "Matricaria chamomilla",
        "tags": ["beruhigend", "magen", "sanft"],
        "axes": {"calmness": 0.9, "clarity": 0.4, "energy": 0.1, "grounding": 0.6},
        "description": "Sanfte Blüten, die beruhigen und entspannen.",
        "preparation": "1-2 TL Blüten mit 200ml heißem Wasser, 5-7 Minuten ziehen lassen.",
        "contraindications": ["Asteraceae-Allergie"],
        "interactions": []
    },
    {
        "slug": "melisse",
        "name": "Zitronenmelisse",
        "latin": "Melissa officinalis",
        "tags": ["beruhigend", "klarheit", "stimmung"],
        "axes": {"calmness": 0.8, "clarity": 0.6, "energy": 0.2, "grounding": 0.5},
        "description": "Hellt die Stimmung auf und bringt Ruhe in den Geist.",
        "preparation": "1-2 TL Blätter mit 200ml heißem Wasser, 6-8 Minuten ziehen lassen.",
        "contraindications": [],
        "interactions": []
    },
    {
        "slug": "ingwer",
        "name": "Ingwer",
        "latin": "Zingiber officinale",
        "tags": ["energie", "wärme", "fokus"],
        "axes": {"calmness": 0.2, "clarity": 0.5, "energy": 0.9, "grounding": 0.7},
        "description": "Wärmend, anregend, fördert Fokus und Antrieb.",
        "preparation": "Frische Scheiben 8-10 Minuten köcheln lassen.",
        "contraindications": ["Magenreizungen", "Blutverdünner"],
        "interactions": ["Antikoagulanzien"]
    },
    {
        "slug": "baldrian",
        "name": "Baldrian",
        "latin": "Valeriana officinalis",
        "tags": ["schlaf", "beruhigend", "boden"],
        "axes": {"calmness": 0.95, "clarity": 0.3, "energy": 0.05, "grounding": 0.9},
        "description": "Tiefe Erdung und Schlafunterstützung.",
        "preparation": "Wurzel 10-12 Minuten ziehen lassen.",
        "contraindications": ["Müdigkeit am Tag"],
        "interactions": ["Sedativa"]
    }
]


def seed_teas_if_empty():
    if db is None:
        return
    count = db["tea"].count_documents({})
    if count == 0:
        db["tea"].insert_many(DEFAULT_TEAS)


@app.on_event("startup")
async def startup_event():
    seed_teas_if_empty()


# --------- Endpoints ---------
@app.post("/session", response_model=dict)
def create_session(payload: CreateSessionRequest):
    sid = str(uuid4())
    doc = SessionModel(session_id=sid, consent_given=False, locale=payload.locale, device=payload.device)
    create_document("session", doc)
    return {"session_id": sid}


@app.post("/consent", response_model=dict)
def give_consent(payload: ConsentRequest):
    if not payload.accepted:
        raise HTTPException(status_code=400, detail="Consent must be accepted")
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    db["session"].update_one(
        {"session_id": payload.session_id},
        {"$set": {"consent_given": True, "consent_timestamp": datetime.now(timezone.utc)}}
    )
    return {"ok": True}


@app.post("/interaction", response_model=dict)
def track_interaction(event: InteractionIn):
    doc = InteractionEventModel(
        session_id=event.session_id,
        type=event.type,  # validated by schema in db layer later if needed
        intensity=event.intensity,
        value=event.value,
        meta=event.meta,
        timestamp=datetime.now(timezone.utc)
    )
    create_document("interactionevent", doc)
    return {"ok": True}


@app.get("/teas", response_model=List[TeaModel])
def list_teas():
    if db is None:
        return []
    return list(db["tea"].find({}, {"_id": 0}))


def compute_profile(events: List[Dict[str, Any]]) -> EmotionalProfile:
    # Simple heuristic baseline for MVP. Later can be replaced by advanced model.
    calm = 50.0
    clarity = 50.0
    energy = 50.0
    grounding = 50.0

    for e in events:
        et = e.get("type")
        inten = float(e.get("intensity", 1.0) or 1.0)
        val = float(e.get("value", 0) or 0)
        if et == "cloud_touch":
            calm = max(0, calm - 3 * inten)
            grounding = min(100, grounding + 2 * inten)
        elif et == "light_collect":
            energy = min(100, energy + 4 * inten)
            clarity = min(100, clarity + 2 * inten)
        elif et == "maze_time":
            clarity = max(0, clarity - min(20, val / 2))
            grounding = max(0, grounding - min(15, val / 3))
        elif et == "breath_pace":
            # lower pace (value) increases calmness up to a point
            calm = min(100, calm + max(0, 5 - min(val, 5)) * 2)
        elif et == "scroll_depth":
            energy = min(100, energy + min(20, val / 5))
        elif et == "companion_tap":
            grounding = min(100, grounding + 5 * inten)

    return EmotionalProfile(calmness=calm, clarity=clarity, energy=energy, grounding=grounding)


def match_teas(profile: EmotionalProfile, teas: List[Dict[str, Any]]) -> List[str]:
    # Cosine-like similarity on normalized axes
    import math

    target = {
        "calmness": profile.calmness / 100.0,
        "clarity": profile.clarity / 100.0,
        "energy": profile.energy / 100.0,
        "grounding": profile.grounding / 100.0,
    }

    def score(t):
        axes = t.get("axes", {})
        dot = sum(target[a] * axes.get(a, 0) for a in target)
        norm_t = math.sqrt(sum((axes.get(a, 0)) ** 2 for a in target)) + 1e-8
        norm_p = math.sqrt(sum((target[a]) ** 2 for a in target)) + 1e-8
        return dot / (norm_t * norm_p)

    ordered = sorted(teas, key=score, reverse=True)
    return [t["slug"] for t in ordered[:3]]


@app.post("/analyze", response_model=RecommendationModel)
def analyze(session_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    events = list(db["interactionevent"].find({"session_id": session_id}, {"_id": 0}))
    profile = compute_profile(events)

    teas = list(db["tea"].find({}, {"_id": 0}))
    top = match_teas(profile, teas)

    rec = RecommendationModel(session_id=session_id, profile=profile, teas=top, rationale="Basierend auf deinen Interaktionen in der Welt.")
    create_document("recommendation", rec)
    return rec


@app.get("/tea/{slug}", response_model=TeaModel)
def tea_detail(slug: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    t = db["tea"].find_one({"slug": slug}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Tea not found")
    return t


@app.post("/journal", response_model=dict)
def add_journal(entry: JournalIn):
    doc = JournalEntryModel(session_id=entry.session_id, mood=entry.mood, notes=entry.notes)
    create_document("journalentry", doc)
    return {"ok": True}


DISCLAIMER_TEXT = (
    "Diese Anwendung ist kein medizinisches Gerät und ersetzt keine professionelle medizinische Beratung, "
    "Diagnose oder Behandlung. Die empfohlenen Tees dienen nur als ergänzendes Wohlbefinden und sind nicht "
    "zur Behandlung von Krankheiten gedacht. Wende dich bei anhaltenden Beschwerden oder Krisen an eine*n "
    "Ärzt*in oder Therapeut*in."
)


@app.get("/disclaimer")
def disclaimer():
    return {"disclaimer": DISCLAIMER_TEXT,
            "expert_note": "Bitte suche professionelle Hilfe, wenn du starke, anhaltende Niedergeschlagenheit, Suizidgedanken, Panikattacken oder körperliche Symptome erlebst."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
