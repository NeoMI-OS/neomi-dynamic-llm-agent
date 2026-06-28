"""
FastAPI REST API a dinamikus LLM agent-hez és a kísérlet pipeline-hoz
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from agent import run_agent
from config import MODEL_CONFIG, ModelTier
from experiment_runner import run_experiment, run_experiment_series, load_all_experiments
from experiment_logger import ExperimentLogger
from meta_agent import run_meta_analysis

LOGS_DIR = Path(__file__).parent.parent / "experiment_logs"

app = FastAPI(
    title="NeoMI Dynamic LLM Agent",
    description="LLM router + 5-node oktatási pipeline + kísérlet-keretrendszer",
    version="2.0.0"
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
    model_evaluation: Optional[dict] = None


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
            tokens_used=result.get("tokens_used"),
            model_evaluation=result.get("model_evaluation")
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Agent hiba: {str(e)}"
        )


# ── Pipeline & Experiment endpoints ─────────────────────────────────────────

class PipelineRunRequest(BaseModel):
    input_document: str
    purpose: str
    experiment_id: str = "exp-001"
    auto_evaluate: bool = True


class ExperimentSeriesRequest(BaseModel):
    input_document: str
    purpose: str
    experiment_ids: Optional[list[str]] = None
    auto_evaluate: bool = True


class MetaAnalysisRequest(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-opus-4-8"


@app.get("/pipeline/experiments")
async def list_experiments():
    """Visszaadja az összes elérhető kísérlet-konfigurációt."""
    try:
        configs = load_all_experiments()
        return [
            {
                "id":       c.get("id"),
                "name":     c.get("name"),
                "status":   c.get("status", "planned"),
                "strategy": c.get("optimization_strategy"),
                "tags":     c.get("tags", []),
                "nodes":    {
                    node: f"{nc.get('provider', nc.get('primary', {}).get('provider', '?'))}/{nc.get('model', nc.get('primary', {}).get('model', '?'))}"
                    for node, nc in c.get("pipeline", {}).get("nodes", {}).items()
                },
            }
            for c in configs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/pipeline/run")
async def run_pipeline_experiment(request: PipelineRunRequest):
    """Futtat egyetlen kísérletet és visszaadja az eredményt."""
    try:
        record = run_experiment(
            experiment_id=request.experiment_id,
            input_document=request.input_document,
            purpose=request.purpose,
            auto_evaluate=request.auto_evaluate,
        )
        return {
            "run_id":          record["run_id"],
            "experiment_id":   record["experiment_id"],
            "experiment_name": record["experiment_name"],
            "metrics":         record["metrics"],
            "evaluation":      record.get("evaluation"),
            "outputs": {
                "content_preview": record["outputs"]["content"][:500] + "...",
                "critic":          record["outputs"]["critic"],
            },
            "errors": record.get("errors", []),
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/pipeline/series")
async def run_series(request: ExperimentSeriesRequest, background_tasks: BackgroundTasks):
    """
    Elindítja a teljes kísérlet-sorozatot háttérben.
    A /pipeline/logs endpointon lehet követni az eredményeket.
    """
    background_tasks.add_task(
        run_experiment_series,
        input_document=request.input_document,
        purpose=request.purpose,
        experiment_ids=request.experiment_ids,
        auto_evaluate=request.auto_evaluate,
    )
    return {
        "status": "started",
        "message": "A kísérlet-sorozat fut a háttérben. Kövesd a /pipeline/logs endpointon.",
    }


@app.get("/pipeline/logs")
async def get_logs(experiment_id: Optional[str] = None, limit: int = 20):
    """Visszaadja a kísérlet-log rekordokat."""
    logger = ExperimentLogger(LOGS_DIR)
    if experiment_id:
        runs = logger.load_runs_for_experiment(experiment_id)
    else:
        runs = logger.load_all_runs()

    # Legfrissebb futások elöl
    runs = sorted(runs, key=lambda r: r.get("started_at", ""), reverse=True)[:limit]

    return [
        {
            "run_id":          r.get("run_id"),
            "experiment_id":   r.get("experiment_id"),
            "experiment_name": r.get("experiment_name"),
            "started_at":      r.get("started_at"),
            "metrics":         r.get("metrics", {}),
            "composite_score": (r.get("evaluation") or {}).get("composite_score"),
            "errors":          len(r.get("errors", [])),
        }
        for r in runs
    ]


@app.get("/pipeline/leaderboard")
async def get_leaderboard():
    """Visszaadja a kísérlet-ranglistát composite score szerint."""
    logger = ExperimentLogger(LOGS_DIR)
    summary = logger.get_summary_table()
    return sorted(summary, key=lambda x: x.get("best_composite") or 0, reverse=True)


@app.post("/pipeline/meta-analyze")
async def meta_analyze(request: MetaAnalysisRequest):
    """
    Futtatja a Meta-Agentet: elemzi a logokat és új kísérleteket generál.
    """
    try:
        result = run_meta_analysis(
            provider=request.provider,
            model=request.model,
            save_proposals=True,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True)
