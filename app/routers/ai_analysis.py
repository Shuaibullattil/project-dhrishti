from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.ai_service import (
    generate_summary,
    answer_question,
    explain_latest_alert,
    groq_client,
)

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
        return {"analysis": "Status: Pending\nReason: Waiting for enough frames to aggregate crowd data.\nRecommended Action: Please wait for the system to process the video."}
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
        return {"analysis": "Waiting for crowd data. Not enough context available yet to answer questions for this session."}
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
        return {"analysis": "No abnormal activity detected yet. The crowd is behaving normally."}
    return {"analysis": analysis}


@router.get("/health")
async def ai_health():
    """
    AI health check for the Groq-based interpretation layer.
    Checks if the client initialized successfully.
    """
    try:
        if groq_client is not None:
            status = "ready"
        else:
            status = "error"
    except Exception:
        status = "error"
    return {
        "ai_provider": "groq",
        "status": status,
    }

