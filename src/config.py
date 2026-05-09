"""
Konfiguráció és típusok a dinamikus LLM agent-hez
"""
from typing import TypedDict, Optional
from enum import Enum


class ModelTier(Enum):
    """Modell szintek költség/képesség alapján"""
    FAST = "fast"
    BALANCED = "balanced"
    POWERFUL = "powerful"
    CREATIVE = "creative"


MODEL_CONFIG = {
    ModelTier.FAST: {
        "provider": "google",
        "model": "gemini-2.5-flash-lite",
        "temperature": 0.3,
        "description": "Gyors válaszok egyszerű kérdésekre"
    },
    ModelTier.BALANCED: {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.5,
        "description": "Kiegyensúlyozott válaszok általános feladatokra"
    },
    ModelTier.POWERFUL: {
        "provider": "openai",
        "model": "gpt-4o",
        "temperature": 0.2,
        "description": "Mély elemzés, komplex reasoning"
    },
    ModelTier.CREATIVE: {
        "provider": "openai",
        "model": "gpt-4o",
        "temperature": 0.9,
        "description": "Kreatív írás, brainstorming"
    }
}


class AgentState(TypedDict):
    """A workflow állapota"""
    query: str
    conversation_history: list
    detected_intent: str
    complexity_score: float
    selected_tier: str
    routing_reason: str
    response: str
    model_used: str
    tokens_used: Optional[int]


INTENT_KEYWORDS = {
    "simple_qa": [
        "mi a", "mi az", "ki a", "ki az", "hány", "mennyi",
        "mikor", "hol", "melyik", "what is", "who is", "when"
    ],
    "creative": [
        "írj", "írjál", "alkoss", "találj ki", "képzelj", "mesélj",
        "write", "create", "imagine", "story", "poem", "vers"
    ],
    "analysis": [
        "elemezd", "hasonlítsd", "magyarázd", "miért", "hogyan működik",
        "analyze", "compare", "explain", "why", "how does"
    ],
    "coding": [
        "kód", "program", "script", "függvény", "debug", "hiba",
        "code", "function", "implement", "fix", "error", "bug"
    ],
    "translation": [
        "fordítsd", "fordítás", "translate", "angolul", "magyarul"
    ]
}

INTENT_TO_TIER = {
    "simple_qa": ModelTier.FAST,
    "creative": ModelTier.CREATIVE,
    "analysis": ModelTier.POWERFUL,
    "coding": ModelTier.POWERFUL,
    "translation": ModelTier.BALANCED,
    "general": ModelTier.BALANCED
}

COMPLEXITY_THRESHOLDS = {
    "upgrade_to_powerful": 0.7,
    "downgrade_to_fast": 0.2
}
