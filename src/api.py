"""
FastAPI REST API a dinamikus LLM agent-hez és a kísérlet pipeline-hoz
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: run_agent(
                query=request.query,
                conversation_history=request.conversation_history
            ),
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
    """Futtat egyetlen kísérletet és visszaadja az eredményt (szinkron)."""
    try:
        loop = asyncio.get_event_loop()
        record = await loop.run_in_executor(
            None,
            lambda: run_experiment(
                experiment_id=request.experiment_id,
                input_document=request.input_document,
                purpose=request.purpose,
                auto_evaluate=request.auto_evaluate,
            ),
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


@app.post("/pipeline/run/stream")
async def run_pipeline_stream(request: PipelineRunRequest):
    """
    Futtat egyetlen kísérletet SSE streaming-gel.
    Minden node befejezésekor azonnal küld egy eseményt.
    Használd curl --no-buffer vagy EventSource JS API-val.
    """
    import concurrent.futures
    from experiment_runner import load_experiment, _extract_node_configs
    from pipeline import (
        _get_llm, _call_node, _update_metrics,
        node_context_analyst, node_needs_analyzer, node_curriculum_designer,
        node_content_writer, node_critic, PipelineState
    )
    import uuid, time
    from datetime import datetime, timezone

    async def event_stream():
        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        run_id = f"run-{uuid.uuid4().hex[:8]}"
        yield sse("start", {
            "run_id": run_id,
            "experiment_id": request.experiment_id,
            "message": "Pipeline indítása..."
        })

        try:
            cfg = load_experiment(request.experiment_id)
            node_configs = _extract_node_configs(cfg)
        except FileNotFoundError as e:
            yield sse("error", {"message": str(e)})
            return

        state: PipelineState = {
            "input_document": request.input_document,
            "purpose": request.purpose,
            "experiment_id": request.experiment_id,
            "node_configs": node_configs,
            "context_output": "", "needs_output": "",
            "curriculum_output": "", "content_output": "", "critic_output": "",
            "node_timings": {}, "node_tokens": {}, "node_costs_usd": {},
            "errors": [],
        }

        nodes = [
            ("context_analyst",    node_context_analyst,    "Kontextus elemzés"),
            ("needs_analyzer",     node_needs_analyzer,     "Szükséglet elemzés"),
            ("curriculum_designer", node_curriculum_designer, "Tananyag tervezés"),
            ("content_writer",     node_content_writer,     "Tartalom írás"),
            ("critic",             node_critic,             "Kritikai értékelés"),
        ]

        loop = asyncio.get_event_loop()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        for i, (node_name, node_fn, label) in enumerate(nodes, 1):
            yield sse("node_start", {
                "node": node_name,
                "label": label,
                "step": f"{i}/5",
                "model": f"{node_configs.get(node_name, {}).get('provider','?')}/{node_configs.get(node_name, {}).get('model','?')}"
            })

            t0 = time.time()
            state = await loop.run_in_executor(executor, node_fn, state)
            elapsed = round(time.time() - t0, 2)

            tokens  = state["node_tokens"].get(node_name, 0)
            cost    = state["node_costs_usd"].get(node_name, 0)

            # Kimenet preview (első 300 karakter)
            output_key = {
                "context_analyst": "context_output",
                "needs_analyzer": "needs_output",
                "curriculum_designer": "curriculum_output",
                "content_writer": "content_output",
                "critic": "critic_output",
            }[node_name]
            preview = state[output_key][:300] + ("..." if len(state[output_key]) > 300 else "")

            yield sse("node_done", {
                "node": node_name,
                "label": label,
                "step": f"{i}/5",
                "latency_s": elapsed,
                "tokens": tokens,
                "cost_usd": round(cost, 5),
                "output_preview": preview,
                "errors": [e for e in state["errors"] if node_name in e],
            })

        # Összesített metrikák
        total_cost    = sum(state["node_costs_usd"].values())
        total_tokens  = sum(state["node_tokens"].values())
        total_latency = sum(state["node_timings"].values())

        yield sse("pipeline_done", {
            "run_id": run_id,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 5),
            "total_latency_seconds": round(total_latency, 2),
            "errors": state["errors"],
        })

        if request.auto_evaluate:
            yield sse("evaluating", {"message": "LLM Judge értékelés fut..."})
            from experiment_evaluator import evaluate_run
            from experiment_logger import ExperimentLogger

            record = {
                "run_id": run_id,
                "experiment_id": request.experiment_id,
                "experiment_name": cfg.get("name", ""),
                "optimization_strategy": cfg.get("optimization_strategy", ""),
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "purpose": request.purpose,
                "node_configs": node_configs,
                "outputs": {
                    "context": state["context_output"],
                    "needs": state["needs_output"],
                    "curriculum": state["curriculum_output"],
                    "content": state["content_output"],
                    "critic": state["critic_output"],
                },
                "metrics": {
                    "node_timings": state["node_timings"],
                    "node_tokens": state["node_tokens"],
                    "node_costs_usd": state["node_costs_usd"],
                    "total_tokens": total_tokens,
                    "total_cost_usd": round(total_cost, 5),
                    "total_latency_seconds": round(total_latency, 2),
                },
                "errors": state["errors"],
                "tags": cfg.get("tags", []),
            }

            judge_cfg = cfg.get("evaluation", {})
            evaluation = await loop.run_in_executor(executor, evaluate_run, record, judge_cfg)
            record["evaluation"] = evaluation
            ExperimentLogger(LOGS_DIR).log(record)

            yield sse("evaluation_done", {
                "composite_score": evaluation.get("composite_score"),
                "dimension_scores": evaluation.get("dimension_scores"),
                "critic_issues": evaluation.get("critic_issues_count"),
            })

        yield sse("done", {"run_id": run_id, "message": "Kísérlet befejezve."})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


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
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: run_meta_analysis(
                provider=request.provider,
                model=request.model,
                save_proposals=True,
            ),
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True)
