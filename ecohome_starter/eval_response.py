import os
import re
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


# The judge rubric, defined once so both the prompt and humans share one definition.
_METRIC_DEFINITIONS = """
- accuracy: Are the facts, figures, times and prices correct and internally
  consistent with energy/cost reasoning? Penalise wrong or contradictory numbers.
- relevance: Does the answer actually address the specific question asked,
  rather than giving generic or off-topic advice?
- completeness: Does it cover the elements a good answer needs, typically a
  specific time/window, a cost analysis, a solar consideration where relevant,
  and a savings estimate? Penalise missing pieces.
- usefulness: Is the advice concrete and actionable, something a real customer
  could follow to save money or energy? Penalise vague or impractical advice.
"""


def _llm_judge_response(question, final_response, expected_response):
    """
    Use an LLM as an impartial judge to score the agent's answer 0.0-1.0 on each
    metric. Returns a parsed dict, or raises on any failure so the caller can
    fall back to heuristics.
    """
    judge = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.0,  # deterministic judging
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    system = SystemMessage(content=(
        "You are a strict but fair evaluator of an energy-advisor AI's responses. "
        "Score the response on each metric from 0.0 (poor) to 1.0 (excellent) "
        "based on these definitions:\n" + _METRIC_DEFINITIONS +
        "\nReturn ONLY a JSON object, no markdown, no backticks, in exactly this "
        "form:\n"
        '{"accuracy": 0.0, "relevance": 0.0, "completeness": 0.0, '
        '"usefulness": 0.0, "feedback": "2-4 sentences explaining the scores, '
        'noting strengths and what would improve the answer."}'
    ))

    user = HumanMessage(content=(
        f"QUESTION:\n{question}\n\n"
        f"AGENT'S RESPONSE:\n{final_response}\n\n"
        f"WHAT A GOOD RESPONSE SHOULD CONTAIN:\n{expected_response}\n\n"
        "Score the agent's response now."
    ))

    raw = judge.invoke([system, user]).content.strip()

    # The model may wrap JSON in ```json fences despite instructions; strip them.
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    data = json.loads(raw)

    # Coerce/validate scores into floats clamped to [0, 1].
    result = {}
    for metric in ("accuracy", "relevance", "completeness", "usefulness"):
        val = float(data.get(metric, 0.0))
        result[metric] = round(max(0.0, min(1.0, val)), 2)
    result["feedback"] = str(data.get("feedback", "")).strip()
    result["method"] = "llm_judge"
    return result


def _heuristic_judge_response(question, final_response, expected_response):
    """
    Rule-based fallback used when the LLM judge is unavailable (no API key /
    network) or fails. Checks for the concrete elements a good answer should
    contain. Measures FORM, not correctness, so it is cruder than the LLM judge
    but still discriminates strong answers from weak ones.
    """
    text = (final_response or "").lower()

    # Signal 1: contains a specific time or time window (e.g. "02:00", "11am-2pm").
    has_time = bool(re.search(r"\b\d{1,2}\s*[:.]\s*\d{2}\b", text)) or \
        bool(re.search(r"\b\d{1,2}\s*(?:am|pm)\b", text)) or \
        bool(re.search(r"\b(off-peak|overnight|midday|peak hours?)\b", text))

    # Signal 2: contains cost/price information (£, pence, p/kWh, "cost", "save").
    has_cost = bool(re.search(r"£\s*\d|\bp/kwh\b|\bpence\b|\bcost\b|\bsav(e|ing)\b", text))

    # Signal 3: considers solar where relevant.
    has_solar = "solar" in text or "irradiance" in text or "generation" in text

    # Signal 4: substantive length (a real recommendation, not a one-liner).
    word_count = len((final_response or "").split())
    is_substantive = word_count >= 40

    # Signal 5: actually mentions the device/topic from the question (relevance).
    q_words = set(re.findall(r"[a-z]+", (question or "").lower()))
    topic_words = q_words & {
        "ev", "car", "charge", "thermostat", "heating", "temperature",
        "dishwasher", "washing", "dryer", "pool", "pump", "battery",
        "solar", "appliance",
    }
    addresses_topic = any(w in text for w in topic_words) if topic_words else True

    # Map signals onto the four metrics.
    completeness = round(sum([has_time, has_cost, has_solar, is_substantive]) / 4, 2)
    relevance = round((0.6 if addresses_topic else 0.0) + (0.4 if is_substantive else 0.0), 2)
    usefulness = round((0.5 if has_time else 0.0) + (0.3 if has_cost else 0.0) +
                       (0.2 if is_substantive else 0.0), 2)
    # Accuracy can't be verified without understanding; give a neutral-to-good
    # score gated on the answer being substantive (an empty answer is inaccurate).
    accuracy = round(0.7 if is_substantive else 0.2, 2)

    missing = []
    if not has_time:
        missing.append("a specific time/window")
    if not has_cost:
        missing.append("cost or savings detail")
    if not has_solar:
        missing.append("a solar consideration")
    if not is_substantive:
        missing.append("more substantive detail")

    feedback = (
        "Heuristic evaluation (LLM judge unavailable). "
        + (f"Answer is missing: {', '.join(missing)}. " if missing
           else "Answer contains the key expected elements. ")
        + f"Word count: {word_count}."
    )

    return {
        "accuracy": accuracy,
        "relevance": relevance,
        "completeness": completeness,
        "usefulness": usefulness,
        "feedback": feedback,
        "method": "heuristic_fallback",
    }


def evaluate_response(question, final_response, expected_response):
    """
    Evaluate a single agent response against what a good response should contain.

    Tries the LLM judge first (meaningful, understands content); falls back to
    rule-based heuristics if the LLM is unavailable or errors. Both paths return
    the same dict shape so callers don't need to know which ran.

    Metrics (each 0.0 - 1.0): accuracy, relevance, completeness, usefulness.

    Args:
        question (str): the question that was asked.
        final_response (str): the agent's final answer text.
        expected_response (str): description of what a good answer should contain.

    Returns:
        dict with the four metric scores, an overall_score, feedback, and the
        method used ("llm_judge" or "heuristic_fallback").
    """
    try:
        result = _llm_judge_response(question, final_response, expected_response)
    except Exception as e:
        result = _heuristic_judge_response(question, final_response, expected_response)
        result["feedback"] += f" (Judge fallback reason: {type(e).__name__})"

    result["overall_score"] = round(
        (result["accuracy"] + result["relevance"] +
         result["completeness"] + result["usefulness"]) / 4, 2
    )
    return result
