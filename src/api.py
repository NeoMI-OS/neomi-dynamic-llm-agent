"""
FastAPI REST API a dinamikus LLM agent-hez
"""
import os
import sys

# Fix: hozzáadjuk a src mappát a path-hoz
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from agent import run_agent
from config import MODEL_CONFIG, ModelTier

app = FastAPI(
    title="Dynamic LLM Router Agent",
    description="Automatikusan választja ki a legjobb LLM-et a feladathoz",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str
    conversation_history: Optional[list] = []


class ChatResponse(BaseModel):
    response: str
    model_used: str
    detected_intent: str
    complexity_score: float
    routing_reason: str
    tokens_used: Optional[int] = None


class ModelInfo(BaseModel):
    tier: str
    provider: str
    model: str
    description: str


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "dynamic-llm-agent"}


@app.get("/models", response_model=list[ModelInfo])
async def list_models():
    return [
        ModelInfo(
            tier=tier.value,
            provider=config["provider"],
            model=config["model"],
            description=config["description"]
        )
        for tier, config in MODEL_CONFIG.items()
    ]


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        result = run_agent(
            query=request.query,
            conversation_history=request.conversation_history
        )

        return ChatResponse(
            response=result["response"],
            model_used=result["model_used"],
            detected_intent=result["detected_intent"],
            complexity_score=result["complexity_score"],
            routing_reason=result["routing_reason"],
            tokens_used=result.get("tokens_used")
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Agent hiba: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True)
