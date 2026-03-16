from datetime import datetime
from typing import List, Dict, Optional
import os
from groq import Groq

from apis.db import db

try:
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY", "default"))
except Exception:
    groq_client = None

def _format_time(value: Optional[datetime]) -> str:
    if isinstance(value, datetime):
        return value.strftime("%H:%M:%S")
    return "Unknown"


def _motion_label(avg_fast_motion_ratio: float) -> str:
    if avg_fast_motion_ratio >= 0.6:
        return "FAST"
    if avg_fast_motion_ratio >= 0.25:
        return "MEDIUM"
    return "LOW"


def _build_timeline(windows: List[Dict]) -> str:
    """
    Build a compact human-readable timeline from aggregated windows.

    Example line:
    Time: 23:35:35 | Count: 22 | State: NORMAL | Motion: LOW | Growth: 0
    """
    if not windows:
        return "No aggregated windows available."

    # Sort chronologically so the growth calculation is intuitive
    ordered = sorted(
        windows,
        key=lambda w: w.get("timestamp") or w.get("window_end") or datetime.min,
    )

    lines: List[str] = []
    prev_avg_count: Optional[float] = None

    for w in ordered:
        avg_count = float(w.get("avg_human_count", 0.0))
        max_count = int(w.get("max_human_count", 0))
        crowd_state = str(w.get("crowd_state", "UNKNOWN"))
        motion = _motion_label(float(w.get("avg_fast_motion_ratio", 0.0)))

        # Growth based on average human count between consecutive windows
        if prev_avg_count is None:
            growth_value = 0
        else:
            growth_value = int(round(avg_count - prev_avg_count))

        growth_prefix = "+" if growth_value > 0 else ""

        ts = (
            w.get("window_end")
            or w.get("timestamp")
            or datetime.utcnow()
        )

        lines.append(
            f"Time: {_format_time(ts)} | Count: {max_count} | "
            f"State: {crowd_state} | Motion: {motion} | Growth: {growth_prefix}{growth_value}"
        )

        prev_avg_count = avg_count

    return "\n".join(lines)


def _build_abnormal_context(session_id: str) -> Optional[str]:
    """
    Build context focused on the latest abnormal window for a session.
    """
    # Find the latest non-normal / elevated severity window
    abnormal = db.aggregate_frame_data.find_one(
        {
            "session_id": session_id,
            "$or": [
                {"severity": {"$ne": "LOW"}},
                {"crowd_state": {"$ne": "NORMAL"}},
            ],
        },
        {"_id": 0},
        sort=[("timestamp", -1)],
    )

    if not abnormal:
        return None

    # Also include a few preceding windows for context if available
    surrounding = list(
        db.aggregate_frame_data.find(
            {
                "session_id": session_id,
                "timestamp": {"$lte": abnormal.get("timestamp")},
            },
            {"_id": 0},
        )
        .sort("timestamp", -1)
        .limit(4)
    )

    context_windows = list(reversed(surrounding))
    timeline = _build_timeline(context_windows)

    # Explicitly describe the rule thresholds used by the aggregator
    rules_description = (
        "Detection rules used by the system:\n"
        "- DENSE_FAST_MOVING when max_density_score > 18 and avg_fast_motion_ratio > 0.8\n"
        "- SUDDEN_SURGE when crowd_growth_rate > 0.25\n"
        "- SUSTAINED_ABNORMAL when avg_abnormal_score > 0.7\n"
    )

    details = (
        f"Session: {session_id}\n"
        f"Latest abnormal window:\n"
        f"  Time window: {_format_time(abnormal.get('window_start'))} to "
        f"{_format_time(abnormal.get('window_end'))}\n"
        f"  Avg human count: {abnormal.get('avg_human_count', 0)}\n"
        f"  Max human count: {abnormal.get('max_human_count', 0)}\n"
        f"  Max density score: {abnormal.get('max_density_score', 0.0)}\n"
        f"  Avg motion speed: {abnormal.get('avg_motion_speed', 0.0)}\n"
        f"  Avg fast motion ratio: {abnormal.get('avg_fast_motion_ratio', 0.0)}\n"
        f"  Crowd growth rate: {abnormal.get('crowd_growth_rate', 0.0)}\n"
        f"  Avg abnormal score: {abnormal.get('avg_abnormal_score', 0.0)}\n"
        f"  Crowd state: {abnormal.get('crowd_state', 'UNKNOWN')}\n"
        f"  Severity: {abnormal.get('severity', 'UNKNOWN')}\n"
        f"  Remark: {abnormal.get('remark', '')}\n"
    )

    return f"{rules_description}\nRecent timeline around alert:\n{timeline}\n\n{details}"


async def generate_llm_response(prompt: str, system_prompt: str = "", json_mode: bool = False) -> str:
    if os.getenv("LLM_PROVIDER") == "groq" and groq_client:
        print("AI provider: GROQ")
        try:
            kwargs = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt or "You are an AI crowd monitoring assistant."},
                    {"role": "user", "content": prompt}
                ]
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            
            response = groq_client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            print(f"Groq failed: {e}")
            raise RuntimeError(f"Groq API Error: {e}")
            
    raise RuntimeError("Groq client not initialized or LLM_PROVIDER is not 'groq'")


async def analyze_context(context: str, mode: str, question: Optional[str] = None) -> str:
    """
    Analyze provided context using LLMs. Modes: summary, qa, explain.
    User prompt is built as: CROWD DATA: {context}  QUESTION: {question if exists}
    """
    mode = mode.lower()

    if mode == "summary":
        system_prompt = (
            "You are an intelligent crowd safety monitoring system. "
            "You must respond with ONLY a valid JSON object. "
            "The JSON object must contain exactly three string keys: 'status', 'reason', and 'action'."
        )
        user_prompt = (
            f"CROWD DATA:\n{context}\n\n"
            "QUESTION:\nProvide a concise operational situation summary in JSON format."
        )
    elif mode == "qa":
        system_prompt = (
            "Answer strictly using provided crowd data. "
            "If unsure say insufficient data. Keep simple."
        )
        q = question or "Provide a simple explanation of the current crowd situation."
        user_prompt = f"CROWD DATA:\n{context}\n\nQUESTION:\n{q}"
    elif mode == "explain":
        system_prompt = (
            "Explain why the alert was triggered based on safety indicators."
        )
        user_prompt = f"CROWD DATA:\n{context}\n\nQUESTION:\nExplain clearly for security operators."
    else:
        raise ValueError(f"Unsupported analysis mode: {mode}")

    if mode == "summary":
        response_text = await generate_llm_response(prompt=user_prompt, system_prompt=system_prompt, json_mode=True)
        try:
            import json
            data = json.loads(response_text)
            status = data.get("status", "Not specified")
            reason = data.get("reason", "No specific reason provided.")
            action = data.get("action", "No action required at this time.")
            return f"Status: {status}\nReason: {reason}\nRecommended Action: {action}"
        except Exception as e:
            print(f"Failed to parse Groq summary JSON: {e}")
            return response_text
            
    return await generate_llm_response(prompt=user_prompt, system_prompt=system_prompt)


def _fetch_recent_windows(session_id: str, limit: int = 12) -> List[Dict]:
    """
    Fetch the last N aggregated windows for a session.
    """
    cursor = (
        db.aggregate_frame_data.find(
            {"session_id": session_id},
            {"_id": 0},
        )
        .sort("timestamp", -1)
        .limit(limit)
    )
    return list(cursor)


def _fetch_session_context(session_id: str) -> str:
    """
    Fetch the manual scene context defined by the user during video upload.
    """
    session = db.get_session(session_id)
    if not session or "context" not in session:
        return ""
        
    ctx = session["context"]
    context_str = "USER DEFINED SCENE CONTEXT:\n"
    if ctx.get("flow_type"): context_str += f"- Flow Type: {ctx.get('flow_type')}\n"
    if ctx.get("capacity"): context_str += f"- Expected Capacity: {ctx.get('capacity')}\n"
    if ctx.get("sensitivity"): context_str += f"- Sensitivity: {ctx.get('sensitivity')}\n"
    if ctx.get("goal"): context_str += f"- Goal: {ctx.get('goal')}\n"
    
    return context_str + "\n"


async def generate_summary(session_id: str, window_count: int = 12) -> Optional[str]:
    """
    Generate an AI-driven situation summary for the last N windows.
    """
    windows = _fetch_recent_windows(session_id, window_count)
    if not windows:
        return None

    timeline = _build_timeline(windows)
    scene_ctx = _fetch_session_context(session_id)
    return await analyze_context(scene_ctx + timeline, mode="summary")


async def answer_question(session_id: str, question: str, window_count: int = 12) -> Optional[str]:
    """
    Answer an operator question based only on recent analytics.
    """
    windows = _fetch_recent_windows(session_id, window_count)
    if not windows:
        return None

    timeline = _build_timeline(windows)
    scene_ctx = _fetch_session_context(session_id)
    return await analyze_context(scene_ctx + timeline, mode="qa", question=question)


async def explain_latest_alert(session_id: str) -> Optional[str]:
    """
    Explain the latest abnormal window for a session.
    """
    context = _build_abnormal_context(session_id)
    if not context:
        return None

    return await analyze_context(_fetch_session_context(session_id) + context, mode="explain")

