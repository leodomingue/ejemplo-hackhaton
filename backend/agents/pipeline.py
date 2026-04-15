"""
Full orchestrator pipeline.

Flow:
  1. Parse situation (natural language) → { subject, action, date, context }
  2. Call historical-correlation-agent + opinion-analyst-agent IN PARALLEL
  3. Consolidate → orchestrator_report
  4. Call strategy-bot (PoliticalEchoAgent) IN SERIES
  5. Return web_strategy_payload
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from .base_agent import call_agent, extract_json, MODEL_FAST, MODEL_MID, MODEL_FULL
from ..utils.prompt_loader import load_agent_prompt, load_raw_json


# ──────────────────────────────────────────────
# Prompt loaders (cached at import time)
# ──────────────────────────────────────────────

def _load_prompts() -> dict[str, str]:
    profiles_json = load_raw_json("profiles.json")
    activation_json = load_raw_json("activation_tables.json")

    enriched_strategy = (
        load_agent_prompt("strategy-bot.md")
        + "\n\n---\n## PROFILES LIBRARY\n```json\n"
        + profiles_json
        + "\n```\n\n## ACTIVATION TABLES\n```json\n"
        + activation_json
        + "\n```"
    )

    return {
        "orchestrator": load_agent_prompt("orchestrator.md"),
        "historical": load_agent_prompt("historical-correlation-agent.md"),
        "opinion": load_agent_prompt("opinion-analyst-agent.md"),
        "strategy": enriched_strategy,
    }


_PROMPTS: dict[str, str] | None = None


def get_prompts() -> dict[str, str]:
    global _PROMPTS
    if _PROMPTS is None:
        _PROMPTS = _load_prompts()
    return _PROMPTS


# ──────────────────────────────────────────────
# Step 1 — Parse natural language input
# ──────────────────────────────────────────────

async def parse_situation(situation: str) -> dict[str, Any]:
    """
    Use the orchestrator prompt to extract { subject, action, date, context }
    from a natural language situation description.
    """
    prompts = get_prompts()
    system = prompts["orchestrator"]

    user_msg = (
        f"Extraé el objeto de dispatch del siguiente evento en lenguaje natural. "
        f"Devolvé ÚNICAMENTE el JSON con los campos subject, action, date, context. "
        f"Nada más.\n\nEvento: {situation}"
    )

    response = await call_agent(system, user_msg, max_tokens=1000, model=MODEL_FAST)
    parsed = extract_json(response)

    # Ensure required fields exist
    return {
        "subject": parsed.get("subject", situation),
        "action": parsed.get("action", ""),
        "date": parsed.get("date", None),
        "context": parsed.get("context", None),
    }


# ──────────────────────────────────────────────
# Step 2 — Parallel subagent calls
# ──────────────────────────────────────────────

async def call_historical_agent(dispatch: dict[str, Any]) -> dict[str, Any]:
    prompts = get_prompts()
    subject = dispatch["subject"]
    action = dispatch["action"]
    user_msg = (
        f"Evento: {subject} — {action}.\n\n"
        "Respondé SOLO con este JSON, sin texto extra:\n"
        "{\n"
        '  "confidence_score": <0-100>,\n'
        '  "dominant_direction": "<UP|DOWN|NEUTRAL|MIXED>",\n'
        '  "pattern_consistency": "<CONSISTENT|ERRATIC|INSUFFICIENT_DATA>",\n'
        '  "avg_impact_percentage": <número o null>,\n'
        '  "key_instances": ["instancia 1", "instancia 2", "instancia 3"],\n'
        '  "warnings": ["advertencia 1"],\n'
        '  "sources": ["fuente 1", "fuente 2"]\n'
        "}"
    )
    response = await call_agent(prompts["historical"], user_msg, max_tokens=2000, model=MODEL_MID)
    result = extract_json(response)
    if "raw_response" in result or not result:
        # Build a minimal fallback from the raw text
        return {
            "confidence_score": 50,
            "dominant_direction": "NEUTRAL",
            "pattern_consistency": "INSUFFICIENT_DATA",
            "avg_impact_percentage": None,
            "key_instances": [result.get("raw_response", "Sin datos disponibles")[:200]],
            "warnings": [],
            "sources": [],
        }
    return result


async def call_opinion_agent(dispatch: dict[str, Any]) -> dict[str, Any]:
    prompts = get_prompts()
    subject = dispatch["subject"]
    action = dispatch["action"]
    user_msg = (
        f"Evento: {subject} — {action}.\n\n"
        "Analizá el impacto reputacional. Respondé SOLO con este JSON, sin texto extra:\n"
        "{\n"
        '  "risk_level": "<none|watch|alert|critical>",\n'
        '  "overall_situation": "<1 párrafo>",\n'
        '  "dominant_narratives": ["narrativa 1", "narrativa 2", "narrativa 3"],\n'
        '  "perspective_tension_score": <0.0-5.0>,\n'
        '  "most_alarming_insight": "<string>",\n'
        '  "most_hopeful_insight": "<string>",\n'
        '  "immediate_actions_suggested": ["acción 1", "acción 2"]\n'
        "}"
    )
    response = await call_agent(prompts["opinion"], user_msg, max_tokens=2000, model=MODEL_MID)
    result = extract_json(response)
    if "raw_response" in result or not result:
        return {
            "risk_level": "watch",
            "overall_situation": result.get("raw_response", "Análisis no disponible")[:300],
            "dominant_narratives": [],
            "perspective_tension_score": 2.5,
            "most_alarming_insight": "",
            "most_hopeful_insight": "",
            "immediate_actions_suggested": [],
        }
    return result


# ──────────────────────────────────────────────
# Step 3 — Consolidate into orchestrator_report
# ──────────────────────────────────────────────

def build_orchestrator_report(
    dispatch: dict[str, Any],
    historical: dict[str, Any],
    opinion: dict[str, Any],
) -> dict[str, Any]:
    """
    Merge outputs from both subagents into orchestrator_report.
    If a subagent returned partial/error data, mark its section accordingly.
    """
    report_id = str(uuid.uuid4())
    generated_at = datetime.now(timezone.utc).isoformat()

    # Flatten historical_analysis
    hist_section: dict[str, Any]
    if historical.get("status") == "partial":
        hist_section = {"status": "unavailable", "raw": historical.get("raw", "")}
    else:
        # Accept either event_analysis wrapper or flat object
        inner = historical.get("event_analysis", historical)
        hist_section = {
            "confidence_score": inner.get("confidence_score", 0),
            "dominant_direction": inner.get("dominant_direction", "NEUTRAL"),
            "pattern_consistency": inner.get("pattern_consistency", "INSUFFICIENT_DATA"),
            "avg_impact_percentage": inner.get("avg_impact_percentage", None),
            "key_instances": inner.get("key_instances", []),
            "warnings": inner.get("warnings", []),
            "sources": inner.get("sources", []),
        }

    # Flatten reputation_analysis
    rep_section: dict[str, Any]
    if opinion.get("status") == "partial":
        rep_section = {"status": "unavailable", "raw": opinion.get("raw", "")}
    else:
        inner = opinion.get("FinalPackage", opinion)
        rep_section = {
            "risk_level": inner.get("risk_level", "watch"),
            "overall_situation": inner.get("overall_situation", ""),
            "dominant_narratives": inner.get("dominant_narratives", []),
            "perspective_tension_score": inner.get("perspective_tension_score", 0.0),
            "most_alarming_insight": inner.get("most_alarming_insight", ""),
            "most_hopeful_insight": inner.get("most_hopeful_insight", ""),
            "immediate_actions_suggested": inner.get("immediate_actions_suggested", []),
        }

    # Simple cross-analysis heuristic — let strategy-bot do the deep work
    unified_risk = rep_section.get("risk_level", "watch") if isinstance(rep_section, dict) else "watch"

    return {
        "orchestrator_report": {
            "report_id": report_id,
            "generated_at": generated_at,
            "subject": dispatch["subject"],
            "action_analyzed": dispatch["action"],
            "historical_analysis": hist_section,
            "reputation_analysis": rep_section,
            "cross_analysis": {
                "convergence_points": [],
                "divergence_points": [],
                "unified_risk_level": unified_risk,
                "key_insight": (
                    f"Evento: {dispatch['subject']} — {dispatch['action']}. "
                    "Ver análisis histórico y de reputación para detalle."
                ),
            },
        }
    }


# ──────────────────────────────────────────────
# Step 4 — Strategy bot
# ──────────────────────────────────────────────

_ACTIVE_PROFILES = [
    "01 - Defensor Industrial",
    "02 - Kirchnerista Industrialista",
    "03 - Liberal Clásico",
    "04 - Libertario Mileísta",
    "06A - La Nación",
    "06C - Página 12",
    "06E - Cenital/Chequeado",
    "07 - Trabajador Afectado",
    "08 - Sindicalista",
    "09 - Troll Anónimo",
    "10 - Político Oportunista",
]

_STRATEGY_INSTRUCTION = """
Generá las 3 rutas estratégicas (AMPLIFICACIÓN, ABSORCIÓN, INVERSIÓN) para el evento recibido.

PERFILES ACTIVOS (solo estos, ignorá los demás):
""" + "\n".join(f"- {p}" for p in _ACTIVE_PROFILES) + """

Para cada ruta devolvé:
- id: "AMPLIFICACION" | "ABSORCION" | "INVERSION"
- probability: 0-100
- description: 1 oración
- profiles: lista de objetos con {profile_id, profile_name, reaction, platform, timing, intensity}
  → máximo 4 perfiles por ruta, solo los más relevantes
- timeline: 3 momentos clave (T+1h, T+6h, T+24h) con "event" string
- strategy: {recommended_action, key_message, profiles_to_engage}

Devolvé SOLO este JSON sin texto extra:
{
  "web_strategy_payload": {
    "report_id": "<del orchestrator_report>",
    "subject": "<string>",
    "action": "<string>",
    "crisis_type": "<string>",
    "routes": [
      {
        "id": "AMPLIFICACION",
        "probability": <0-100>,
        "description": "<string>",
        "profiles": [...],
        "timeline": [
          {"moment": "T+1h", "event": "<string>"},
          {"moment": "T+6h", "event": "<string>"},
          {"moment": "T+24h", "event": "<string>"}
        ],
        "strategy": {
          "recommended_action": "<string>",
          "key_message": "<string>",
          "profiles_to_engage": ["<profile_name>"]
        }
      },
      { "id": "ABSORCION", ... },
      { "id": "INVERSION", ... }
    ],
    "master_verdict": {
      "dominant_route": "<AMPLIFICACION|ABSORCION|INVERSION>",
      "confidence": <0-100>,
      "pivot_profile": "<nombre del perfil más decisivo>",
      "executive_summary": "<2 oraciones>"
    }
  }
}
"""


async def call_strategy_bot(orchestrator_report: dict[str, Any]) -> dict[str, Any]:
    prompts = get_prompts()
    report_json = json.dumps(orchestrator_report, ensure_ascii=False, indent=2)
    user_msg = _STRATEGY_INSTRUCTION + f"\n\nORCHESTRATOR REPORT:\n```json\n{report_json}\n```"

    response = await call_agent(prompts["strategy"], user_msg, max_tokens=8000, model=MODEL_FULL)
    result = extract_json(response)
    if "raw_response" in result:
        return {
            "web_strategy_payload": {
                "status": "partial",
                "raw_analysis": result["raw_response"],
                "report_id": orchestrator_report.get("orchestrator_report", {}).get("report_id", ""),
            }
        }
    return result


# ──────────────────────────────────────────────
# Full pipeline entry point
# ──────────────────────────────────────────────

async def run_pipeline(situation: str) -> dict[str, Any]:
    """
    End-to-end pipeline:
      situation (str) → web_strategy_payload (dict)
    """
    # Step 1 — parse
    dispatch = await parse_situation(situation)

    # Step 2 — parallel subagents
    historical_result, opinion_result = await asyncio.gather(
        call_historical_agent(dispatch),
        call_opinion_agent(dispatch),
        return_exceptions=False,
    )

    # Step 3 — consolidate
    orchestrator_report = build_orchestrator_report(dispatch, historical_result, opinion_result)

    # Step 4 — strategy bot (serial, depends on consolidated report)
    strategy_output = await call_strategy_bot(orchestrator_report)

    # Build final response
    return {
        "situation": situation,
        "dispatch": dispatch,
        "orchestrator_report": orchestrator_report["orchestrator_report"],
        "web_strategy_payload": strategy_output.get(
            "web_strategy_payload", strategy_output
        ),
    }


# ──────────────────────────────────────────────
# Streaming pipeline — yields SSE events
# ──────────────────────────────────────────────

async def run_pipeline_stream(situation: str):
    """
    Same pipeline as run_pipeline but yields Server-Sent Events (SSE)
    after each step completes so the client can see progress in real time.

    Yields strings formatted as SSE: "data: {json}\\n\\n"
    """

    def event(step: int, total: int, status: str, message: str, payload: Any = None) -> str:
        data: dict[str, Any] = {
            "step": step,
            "total_steps": total,
            "status": status,   # "running" | "done" | "error"
            "message": message,
        }
        if payload is not None:
            data["payload"] = payload
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    TOTAL = 4

    # ── Step 1: parse ──
    yield event(1, TOTAL, "running", "Parseando la situación en lenguaje natural...")
    try:
        dispatch = await parse_situation(situation)
    except Exception as exc:
        yield event(1, TOTAL, "error", f"Error parseando: {exc}")
        return
    yield event(1, TOTAL, "done", "Situación parseada.", payload=dispatch)

    # ── Step 2: parallel agents ──
    yield event(2, TOTAL, "running",
                "Llamando a historical-correlation-agent y opinion-analyst-agent en paralelo... "
                "(esto puede tardar 60-120 segundos)")
    try:
        historical_result, opinion_result = await asyncio.gather(
            call_historical_agent(dispatch),
            call_opinion_agent(dispatch),
        )
    except Exception as exc:
        yield event(2, TOTAL, "error", f"Error en subagentes: {exc}")
        return
    yield event(2, TOTAL, "done", "Ambos subagentes respondieron.")

    # ── Step 3: consolidate ──
    yield event(3, TOTAL, "running", "Consolidando orchestrator_report...")
    orchestrator_report = build_orchestrator_report(dispatch, historical_result, opinion_result)
    yield event(3, TOTAL, "done", "Reporte consolidado.",
                payload=orchestrator_report["orchestrator_report"])

    # ── Step 4: strategy bot ──
    yield event(4, TOTAL, "running",
                "Llamando a strategy-bot (PoliticalEchoAgent)... "
                "(esto puede tardar 90-180 segundos — genera las 3 rutas completas)")
    try:
        strategy_output = await call_strategy_bot(orchestrator_report)
    except Exception as exc:
        yield event(4, TOTAL, "error", f"Error en strategy-bot: {exc}")
        return

    final = {
        "situation": situation,
        "dispatch": dispatch,
        "orchestrator_report": orchestrator_report["orchestrator_report"],
        "web_strategy_payload": strategy_output.get("web_strategy_payload", strategy_output),
    }
    yield event(4, TOTAL, "done", "Pipeline completo.", payload=final)

    # SSE: signal end of stream
    yield "data: [DONE]\n\n"
