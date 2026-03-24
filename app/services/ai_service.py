from datetime import datetime
from typing import Dict, List, Optional
import os

from groq import Groq

from apis.db import db
from app.services.risk_engine import RiskEngine

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


def get_risk_rules(context: Dict) -> str:
    flow_type = str(context.get("flow_type", "NORMAL")).upper()
    goal = str(context.get("goal", "MONITORING")).upper()
    sensitivity = str(context.get("sensitivity", "MEDIUM")).upper()
    clustering = str(context.get("clustering", "ALLOWED")).upper()
    capacity = context.get("capacity", "the configured capacity")

    expected_speed = RiskEngine.EXPECTED_MAX_SPEED.get(
        flow_type,
        RiskEngine.EXPECTED_MAX_SPEED["NORMAL"],
    )
    goal_weights = RiskEngine.GOAL_WEIGHTS.get(
        goal,
        RiskEngine.GOAL_WEIGHTS["MONITORING"],
    )
    sensitivity_multiplier = RiskEngine.SENSITIVITY_MULTIPLIERS.get(sensitivity, 1.0)
    clustering_adjustment = RiskEngine.CLUSTERING_ADJUSTMENTS.get(clustering, 1.0)

    return (
        "Risk is calculated from crowd density, crowd movement, and sudden crowd change.\n\n"
        f"Density is judged against the configured capacity of {capacity} people.\n"
        f"Movement is judged against the expected pace for a {flow_type} environment. "
        f"The reference movement level for this type is {expected_speed}.\n"
        "Sudden change means the crowd grows or shifts quickly over a short period.\n\n"
        f"The system goal is {goal}, so the backend prioritizes density, movement, and surge "
        f"with the balance {goal_weights}.\n"
        f"Sensitivity is {sensitivity}, which applies a risk multiplier of {sensitivity_multiplier} "
        "and causes earlier escalation when conditions worsen.\n"
        f"Clustering is {clustering}, which adjusts how strongly density is treated using "
        f"the factor {clustering_adjustment}.\n\n"
        "Risk levels mean:\n"
        "NORMAL: behavior matches what is expected in this environment.\n"
        "BUSY: activity is increasing but still manageable.\n"
        "WARNING: movement or crowd buildup is becoming unsafe for this environment.\n"
        "CRITICAL: movement, crowd buildup, or sudden change strongly suggests serious danger, panic, or congestion."
    )


def _build_context_description(context: Dict) -> str:
    flow_type = str(context.get("flow_type", "NORMAL")).upper()
    goal = str(context.get("goal", "MONITORING")).upper()
    clustering = str(context.get("clustering", "ALLOWED")).upper()
    sensitivity = str(context.get("sensitivity", "MEDIUM")).upper()
    capacity = context.get("capacity", "Unknown")

    flow_descriptions = {
        "STATIC": "people are expected to stay mostly in place",
        "SLOW": "movement is expected to stay calm and controlled",
        "NORMAL": "steady movement is expected",
        "FAST_FLOW": "continuous brisk movement is expected",
        "TRANSIT_RUSH": "fast movement is expected because people are passing through quickly",
    }
    goal_descriptions = {
        "FLOW": "smooth movement is treated as normal, while disruption matters more",
        "STAY": "density matters more because people are expected to remain in the area",
        "QUEUE": "buildup and surges matter more because orderly waiting is expected",
        "SECURITY": "unusual movement matters more because security risk is the focus",
        "RESTRICTED": "movement itself is sensitive because access should be limited",
        "MONITORING": "the system balances crowd size, movement, and change evenly",
    }
    clustering_descriptions = {
        "ALLOWED": "grouping is acceptable in this area",
        "LIMITED": "small grouping is tolerated, but buildup is less acceptable",
        "DISCOURAGED": "grouping is not preferred and increases concern",
        "NOT_ALLOWED": "clustering is treated as a strong warning sign",
    }
    sensitivity_descriptions = {
        "LOW": "the system is tolerant and waits for stronger signs before escalating",
        "MEDIUM": "the system reacts at a balanced threshold",
        "HIGH": "the system escalates earlier when behavior starts to worsen",
        "PARANOID": "the system reacts very aggressively to early signs of risk",
    }

    return (
        "Context:\n"
        f"- Flow type: {flow_type} ({flow_descriptions.get(flow_type, 'movement expectations come from this environment')})\n"
        f"- Goal: {goal} ({goal_descriptions.get(goal, 'this goal shapes what the system treats as risky')})\n"
        f"- Clustering: {clustering} ({clustering_descriptions.get(clustering, 'clustering policy affects density interpretation')})\n"
        f"- Sensitivity: {sensitivity} ({sensitivity_descriptions.get(sensitivity, 'sensitivity changes how early alerts trigger')})\n"
        f"- Capacity: {capacity}\n"
    )


def _build_ai_prompt(
    *,
    risk_rules: str,
    context_description: str,
    session_data: str,
    question: str,
) -> str:
    return (
        "You are an AI crowd monitoring assistant.\n\n"
        "You MUST explain results based on the system rules and context.\n\n"
        f"System Rules:\n{risk_rules}\n\n"
        f"Environment Context:\n{context_description}\n\n"
        f"Session Data:\n{session_data}\n\n"
        f"User Question:\n{question}\n\n"
        "Explain clearly in simple terms.\n"
        "Do NOT use technical metrics or variable names.\n"
        "Do NOT give generic answers.\n"
        "Always connect the behavior to the environment and explain why the system treated it as safe or risky."
    )


def _build_timeline(windows: List[Dict]) -> str:
    if not windows:
        return "No aggregated windows available."

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

        if prev_avg_count is None:
            growth_value = 0
        else:
            growth_value = int(round(avg_count - prev_avg_count))

        growth_prefix = "+" if growth_value > 0 else ""
        ts = w.get("window_end") or w.get("timestamp") or datetime.utcnow()

        lines.append(
            f"Time: {_format_time(ts)} | Count: {max_count} | "
            f"State: {crowd_state} | Motion: {motion} | Growth: {growth_prefix}{growth_value}"
        )
        prev_avg_count = avg_count

    return "\n".join(lines)


def _build_abnormal_context(session_id: str) -> Optional[str]:
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

    details = (
        f"Latest elevated window:\n"
        f"Time window: {_format_time(abnormal.get('window_start'))} to {_format_time(abnormal.get('window_end'))}\n"
        f"State: {abnormal.get('crowd_state', 'UNKNOWN')}\n"
        f"Severity: {abnormal.get('severity', 'UNKNOWN')}\n"
        f"Remark: {abnormal.get('remark', '')}\n"
        f"Recent timeline:\n{timeline}"
    )
    return details


async def generate_llm_response(prompt: str, system_prompt: str = "", json_mode: bool = False) -> str:
    if os.getenv("LLM_PROVIDER") == "groq" and groq_client:
        print("AI provider: GROQ")
        try:
            kwargs = {
                "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
                "messages": [
                    {"role": "system", "content": system_prompt or "You are an AI crowd monitoring assistant."},
                    {"role": "user", "content": prompt},
                ],
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = groq_client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            print(f"Groq failed: {e}")
            raise RuntimeError(f"Groq API Error: {e}")

    raise RuntimeError("Groq client not initialized or LLM_PROVIDER is not 'groq'")


async def analyze_context(session_context: Dict, session_data: str, mode: str, question: Optional[str] = None) -> str:
    mode = mode.lower()
    risk_rules = get_risk_rules(session_context)
    context_description = _build_context_description(session_context)

    if mode == "summary":
        system_prompt = (
            "You are an AI crowd monitoring assistant. "
            "Write concise operational explanations grounded in the provided rules, environment, and session behavior. "
            "Do not use raw metric names, formulas, or generic language. "
            "Return exactly three labeled sections: Status, Reason, Action. "
            "CRITICAL: Keep each section to exactly 1 short sentence (maximum 10 words)."
        )
        user_prompt = _build_ai_prompt(
            risk_rules=risk_rules,
            context_description=context_description,
            session_data=session_data,
            question=(
                "Provide a very brief operational situation summary with exactly three labeled sections: "
                "Status, Reason, and Action. Keep each section to 1 short sentence."
            ),
        )
    elif mode == "qa":
        system_prompt = (
            "You are an AI crowd monitoring assistant. "
            "Answer strictly from the provided system rules, environment context, and session behavior. "
            "If the answer is unclear, say the available session data is insufficient. "
            "Keep the answer simple, direct, and context-aware."
        )
        user_prompt = _build_ai_prompt(
            risk_rules=risk_rules,
            context_description=context_description,
            session_data=session_data,
            question=question or "Provide a simple explanation of the current crowd situation.",
        )
    elif mode == "explain":
        system_prompt = (
            "You are an AI crowd monitoring assistant. "
            "Explain why the alert happened using the provided system rules and environment context. "
            "Do not use technical metric names, thresholds, or formula language. "
            "Keep the explanation brief, concrete, and operational."
        )
        user_prompt = _build_ai_prompt(
            risk_rules=risk_rules,
            context_description=context_description,
            session_data=session_data,
            question=(
                question
                or "Explain why the latest alert happened, why it mattered in this environment, and what operators should understand."
            ),
        )
    else:
        raise ValueError(f"Unsupported analysis mode: {mode}")

    return await generate_llm_response(prompt=user_prompt, system_prompt=system_prompt)


def _fetch_recent_windows(session_id: str, limit: int = 12) -> List[Dict]:
    cursor = (
        db.aggregate_frame_data.find(
            {"session_id": session_id},
            {"_id": 0},
        )
        .sort("timestamp", -1)
        .limit(limit)
    )
    return list(cursor)


def _fetch_session_context(session_id: str) -> Dict:
    session = db.get_session(session_id)
    if not session or "context" not in session:
        return {}
    return session["context"]


async def generate_summary(session_id: str, window_count: int = 12) -> Optional[str]:
    windows = _fetch_recent_windows(session_id, window_count)
    if not windows:
        return None

    timeline = _build_timeline(windows)
    scene_ctx = _fetch_session_context(session_id)
    return await analyze_context(scene_ctx, timeline, mode="summary")


async def answer_question(session_id: str, question: str, window_count: int = 12) -> Optional[str]:
    windows = _fetch_recent_windows(session_id, window_count)
    if not windows:
        return None

    timeline = _build_timeline(windows)
    scene_ctx = _fetch_session_context(session_id)
    return await analyze_context(scene_ctx, timeline, mode="qa", question=question)


async def explain_latest_alert(session_id: str) -> Optional[str]:
    context = _build_abnormal_context(session_id)
    if not context:
        return None

    return await analyze_context(
        _fetch_session_context(session_id),
        context,
        mode="explain",
    )


def generate_alert_insight(data: Dict) -> Dict:
    if not groq_client:
        return {
            "insight": "Crowd behavior indicates potential risk",
            "action": "Please check the area immediately",
        }

    risk_level = data.get("risk_level", "CRITICAL")
    people_count = data.get("people_count", "Unknown")
    timestamp = data.get("timestamp", "Unknown")

    prompt = f"""You are a crowd monitoring assistant.

Explain why a CRITICAL alert was triggered in simple terms.

Rules:
* Do NOT use numbers
* Do NOT mention technical metrics
* Keep explanation under 2 lines
* Use simple language for security staff

Also provide a short recommended action.

Output format:
Insight: <text>
Action: <text>

Data:
Risk Level: {risk_level}
People Count: {people_count}
Timestamp: {timestamp}
"""

    try:
        response = groq_client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            messages=[
                {"role": "system", "content": "You are a helpful security assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
        )
        content = response.choices[0].message.content.strip()

        insight = "Crowd behavior indicates potential risk"
        action = "Please check the area immediately"

        for line in content.split("\n"):
            if line.lower().startswith("insight:"):
                insight = line.split(":", 1)[1].strip()
            elif line.lower().startswith("action:"):
                action = line.split(":", 1)[1].strip()

        return {
            "insight": insight,
            "action": action,
        }
    except Exception as e:
        print(f"Groq alert insight generation failed: {e}")
        return {
            "insight": "Crowd behavior indicates potential risk",
            "action": "Please check the area immediately",
        }
