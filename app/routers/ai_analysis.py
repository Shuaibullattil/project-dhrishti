from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.ai_service import (
    generate_summary,
    answer_question,
    explain_latest_alert,
)
from app.services.gemini_client import GeminiClient


router = APIRouter(prefix="/ai", tags=["ai-analysis"])


class QuestionRequest(BaseModel):
    question: str


@router.get("/{session_id}/summary")
async def get_ai_summary(session_id: str):
    """
    Return an AI-generated situation summary for the last N windows of a session.
    """
    try:
        analysis: Optional[str] = await generate_summary(session_id=session_id)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail="No aggregated window data found for this session.",
        )
    return {"analysis": analysis}


@router.post("/{session_id}/ask")
async def ask_ai(session_id: str, body: QuestionRequest):
    """
    Answer an operator question based strictly on stored crowd analytics.
    """
    try:
        analysis: Optional[str] = await answer_question(
            session_id=session_id,
            question=body.question,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail="No aggregated window data found for this session.",
        )
    return {"analysis": analysis}


@router.get("/{session_id}/explain")
async def explain_ai(session_id: str):
    """
    Explain why the latest alert was triggered for a session.
    """
    try:
        analysis: Optional[str] = await explain_latest_alert(session_id=session_id)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail="No abnormal aggregated window found for this session.",
        )
    return {"analysis": analysis}


@router.get("/health")
async def ai_health():
    """
    AI health check for the Gemini-based interpretation layer.
    Sends a simple "hello" prompt to verify the API and detects quota limits.
    Always returns valid JSON; never raises.
    """
    try:
        client = GeminiClient()
        ok, quota_limited = await client.health_check()
        status = "ready" if (ok and not quota_limited) else "quota_limited"
    except Exception:
        status = "quota_limited"
    return {
        "ai_provider": "gemini",
        "status": status,
    }

