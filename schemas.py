"""
Database Schemas for Tee & Seele

Each Pydantic model corresponds to a MongoDB collection (lowercased class name).
- Session -> "session"
- InteractionEvent -> "interactionevent"
- Tea -> "tea"
- Recommendation -> "recommendation"
- JournalEntry -> "journalentry"

These schemas are used for validation and for the /schema endpoint.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict
from datetime import datetime


class Session(BaseModel):
    """Anonymous user session"""
    session_id: str = Field(..., description="Opaque, anonymous session id (UUIDv4)")
    consent_given: bool = Field(False, description="User accepted disclaimer")
    consent_timestamp: Optional[datetime] = Field(None, description="When consent was given")
    locale: Optional[str] = Field(None, description="UI locale, e.g. de, en")
    device: Optional[str] = Field(None, description="Device type info")


class InteractionEvent(BaseModel):
    """Captured interactions in the 3D world to infer emotional profile"""
    session_id: str = Field(..., description="Related session id")
    type: Literal[
        "cloud_touch",      # Wolken der Schwere berühren
        "light_collect",    # Lichtfunken sammeln
        "maze_time",        # Zeit im Labyrinth (Sekunden)
        "breath_pace",      # Atemübung: Pace/Tempo
        "scroll_depth",     # Tiefe des Scrollens
        "companion_tap"      # Interaktion mit Reiseführer
    ]
    intensity: Optional[float] = Field(1.0, ge=0, le=10, description="How strong the interaction felt")
    value: Optional[float] = Field(None, description="Numeric value when applicable, e.g. seconds")
    meta: Optional[Dict[str, str]] = Field(None, description="Arbitrary metadata")
    timestamp: Optional[datetime] = Field(None, description="Event time; server fills if missing")


class EmotionalProfile(BaseModel):
    """Computed profile along core wellness axes"""
    calmness: float = Field(..., ge=0, le=100)
    clarity: float = Field(..., ge=0, le=100)
    energy: float = Field(..., ge=0, le=100)
    grounding: float = Field(..., ge=0, le=100)


class Tea(BaseModel):
    """Herbal tea knowledge base"""
    slug: str = Field(..., description="URL-friendly id, e.g. kamille")
    name: str = Field(..., description="Common name")
    latin: Optional[str] = Field(None, description="Latin binomial")
    tags: List[str] = Field(default_factory=list, description="Properties, e.g. beruhigend, magen, klarheit")
    axes: Dict[str, float] = Field(default_factory=dict, description="Contribution to axes: calmness, clarity, energy, grounding (0..1)")
    description: Optional[str] = Field(None, description="Short narrative description")
    preparation: Optional[str] = Field(None, description="How to prepare")
    contraindications: List[str] = Field(default_factory=list, description="Prominent warnings/contraindications")
    interactions: List[str] = Field(default_factory=list, description="Possible interactions with meds")


class Recommendation(BaseModel):
    """Recommendation result for a session"""
    session_id: str
    profile: EmotionalProfile
    teas: List[str] = Field(..., description="Ordered tea slugs best matching the profile")
    rationale: Optional[str] = Field(None, description="Narrative explanation for the match")


class JournalEntry(BaseModel):
    """Optional mood journaling entry"""
    session_id: str
    mood: Literal["low", "neutral", "uplifted"]
    notes: Optional[str] = None


# The /schema endpoint uses this registry to expose structures for tooling
SCHEMA_REGISTRY = {
    "Session": Session.model_json_schema(),
    "InteractionEvent": InteractionEvent.model_json_schema(),
    "EmotionalProfile": EmotionalProfile.model_json_schema(),
    "Tea": Tea.model_json_schema(),
    "Recommendation": Recommendation.model_json_schema(),
    "JournalEntry": JournalEntry.model_json_schema(),
}
