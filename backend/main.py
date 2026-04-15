"""
Crisis Simulator — FastAPI Backend

Endpoints:
  POST /analyze   — Run full pipeline and return web_strategy_payload + routes
  GET  /health    — Health check
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Load .env from the backend/ directory regardless of where uvicorn is run from
load_dotenv(Path(__file__).parent / ".env")

from .agents.pipeline import run_pipeline, run_pipeline_stream  # noqa: E402 — after env load


# ──────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm prompt cache by loading all agent prompts at startup
    from .agents.pipeline import get_prompts
    get_prompts()
    yield


app = FastAPI(
    title="Crisis Simulator API",
    description=(
        "Pipeline político: dado un evento en lenguaje natural, devuelve las 3 rutas "
        "estratégicas (AMPLIFICACIÓN, ABSORCIÓN, INVERSIÓN) con reacciones de perfiles, "
        "cadena temporal y recomendaciones."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    situation: str = Field(
        ...,
        min_length=10,
        description="Descripción en lenguaje natural del evento político.",
        examples=["Javier Milei anunció que Argentina dolarizará su economía antes de fin de año."],
    )


class AnalyzeResponse(BaseModel):
    situation: str
    dispatch: dict
    orchestrator_report: dict
    web_strategy_payload: dict


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(body: AnalyzeRequest):
    """
    Run the full Crisis Simulator pipeline:
    1. Parse natural language → dispatch object
    2. Call historical-correlation-agent + opinion-analyst-agent in parallel
    3. Consolidate → orchestrator_report
    4. Call strategy-bot → web_strategy_payload with 3 routes
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY not set. Add it to backend/.env",
        )

    try:
        result = await run_pipeline(body.situation)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return result


@app.post("/analyze/stream")
async def analyze_stream(body: AnalyzeRequest):
    """
    Same pipeline as /analyze but streams progress via Server-Sent Events.
    Each event is: data: {step, total_steps, status, message, payload?}
    Last event is: data: [DONE]

    Use with: curl -N -X POST http://localhost:8000/analyze/stream ...
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY not set. Add it to backend/.env",
        )

    return StreamingResponse(
        run_pipeline_stream(body.situation),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
