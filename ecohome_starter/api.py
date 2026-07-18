"""
EcoHome Energy Agent — FastAPI backend.

Wraps the LangGraph agent in a web API so a frontend (Next.js on Vercel)
can talk to it. Designed for deployment on Render's free tier.

Run locally:
    uvicorn api:app --reload --port 8000

Endpoints:
    GET  /health   — liveness check (used by Render + uptime pinger)
    POST /chat     — ask the agent a question
"""
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")  # Anaconda OpenMP guard

import time
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Data bootstrap — on a fresh server (Render) the SQLite DB and vector store
# don't exist yet. Build them once at startup if missing.
# ---------------------------------------------------------------------------
def bootstrap_data():
    """Create and seed the database + vector store if they don't exist."""
    from models.energy import DatabaseManager

    db = DatabaseManager("data/energy_data.db")

    # --- Database: create tables and seed sample data if empty -------------
    db.create_tables()
    if not db.get_recent_usage(24 * 30):  # nothing in the last 30 days
        print("[bootstrap] Seeding sample energy data...")
        import random
        from datetime import datetime, timedelta

        device_types = {
            "EV": {"base_kwh": 10, "variation": 5, "peak_hours": [18, 19, 20, 21]},
            "HVAC": {"base_kwh": 2, "variation": 1, "peak_hours": [12, 13, 14, 15, 16, 17]},
            "appliance": {"base_kwh": 1.5, "variation": 0.5, "peak_hours": [19, 20, 21, 22]},
        }
        device_names = {"EV": "Tesla Model 3", "HVAC": "Main AC Unit",
                        "appliance": "Dishwasher"}
        weather_conditions = {
            "sunny": 1.0, "partly_cloudy": 0.6, "cloudy": 0.3, "rainy": 0.1,
        }

        start = datetime.now() - timedelta(days=30)
        for day in range(30):
            date = start + timedelta(days=day)
            weather = random.choices(list(weather_conditions),
                                     weights=[0.4, 0.3, 0.2, 0.1])[0]
            wmult = weather_conditions[weather]
            for hour in range(24):
                ts = date.replace(hour=hour, minute=0, second=0, microsecond=0)
                # usage records
                for dtype, cfg in device_types.items():
                    mult = 1.5 if hour in cfg["peak_hours"] else 0.8
                    kwh = max(0, (cfg["base_kwh"] +
                                  random.uniform(-cfg["variation"], cfg["variation"])) * mult)
                    price = 0.15 if hour in cfg["peak_hours"] else 0.10
                    db.add_usage_record(ts, kwh, dtype, device_names[dtype], kwh * price)
                # solar records (daylight only)
                if 6 <= hour <= 18:
                    hf = 1 - abs(hour - 12) / 6
                    gen = max(0, 5.0 * hf * wmult * random.uniform(0.8, 1.2))
                    db.add_generation_record(ts, gen, weather,
                                             20 + random.uniform(-5, 5),
                                             800 * hf * wmult if gen > 0 else 0)
        print("[bootstrap] Database seeded.")
    else:
        print("[bootstrap] Database already populated.")

    # --- Vector store: search_energy_tips builds it on first call ----------
    # (its build-if-missing logic handles this; a warm-up call triggers it)
    vs_path = os.path.join("data/vectorstore", "chroma.sqlite3")
    if not os.path.exists(vs_path):
        print("[bootstrap] Building vector store (one-time embedding cost)...")
        from tools import search_energy_tips
        result = search_energy_tips.invoke({"query": "energy saving", "max_results": 1})
        if "error" in result:
            print(f"[bootstrap] WARNING: vector store build failed: {result['error']}")
        else:
            print("[bootstrap] Vector store built.")
    else:
        print("[bootstrap] Vector store already exists.")


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(title="EcoHome Energy Agent API", version="1.0")

# CORS: allow the frontend origins. Update ALLOWED_ORIGINS env var on Render
# to your real domains, comma-separated.
_default_origins = "http://localhost:3000,https://ecohomeagent.com,https://www.ecohomeagent.com"
origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# The agent is built once at startup (it's stateless per-request).
AGENT = None

ECOHOME_SYSTEM_PROMPT = None
try:
    from ecohome_system_prompt import ECOHOME_SYSTEM_PROMPT
except Exception:
    ECOHOME_SYSTEM_PROMPT = (
        "You are the EcoHome Energy Agent for a UK smart-home energy company. "
        "Use your tools to gather electricity prices, weather/solar forecasts, "
        "usage history, and energy-saving tips, then give a specific, time-based "
        "recommendation with costs in GBP. Always include a specific time window "
        "and a cost analysis; include solar and savings where relevant."
    )


@app.on_event("startup")
def startup():
    global AGENT
    bootstrap_data()
    from agent import Agent
    AGENT = Agent(instructions=ECOHOME_SYSTEM_PROMPT)
    print("[startup] Agent ready.")


# ---------------------------------------------------------------------------
# Guardrails — lightweight, in-memory rate limiting per client IP.
# (Resets on restart; fine for a demo. The OpenAI spending cap is the backstop.)
# ---------------------------------------------------------------------------
MAX_QUESTION_CHARS = 500          # cap prompt length
RATE_LIMIT_PER_HOUR = 20          # questions per IP per hour
MIN_SECONDS_BETWEEN = 5           # cooldown between messages per IP

_request_log = defaultdict(list)  # ip -> [timestamps]


def check_rate_limit(ip: str):
    now = time.time()
    window = [t for t in _request_log[ip] if now - t < 3600]
    _request_log[ip] = window
    if window and now - window[-1] < MIN_SECONDS_BETWEEN:
        raise HTTPException(429, "Please wait a few seconds between messages.")
    if len(window) >= RATE_LIMIT_PER_HOUR:
        raise HTTPException(429, "Hourly question limit reached for this demo. "
                                 "Please try again later.")
    _request_log[ip].append(now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_CHARS)
    context: str = Field(default="Location: London, UK", max_length=200)
    # UK GSP region code (A-P). Defaults to C (London) if omitted or invalid.
    region: str = Field(default="C", max_length=2)


class ChatResponse(BaseModel):
    answer: str
    tools_used: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "agent_ready": AGENT is not None}


@app.get("/regions")
def regions():
    """
    The list of selectable UK regions for the frontend dropdown.
    Single source of truth: derived from the backend's region table.
    """
    from tools import UK_REGIONS, _DEFAULT_REGION
    return {
        "default": _DEFAULT_REGION,
        "regions": [
            {"code": code, "label": info["label"]}
            for code, info in UK_REGIONS.items()
        ],
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request):
    if AGENT is None:
        raise HTTPException(503, "Agent is starting up, try again in a moment.")

    ip = request.client.host if request.client else "unknown"
    check_rate_limit(ip)

    # Apply the user's selected region for this request. The pricing and weather
    # tools read this; it falls back to London (C) if the code is missing/invalid.
    from tools import set_active_region, UK_REGIONS
    applied_region = set_active_region(req.region)
    region_label = UK_REGIONS.get(applied_region, {}).get("label", "London")

    # Stamp the real current date into the context so the agent never has to
    # guess it. "tomorrow", "tonight", "this week" etc. are resolved relative
    # to these actual dates instead of being invented by the model.
    from datetime import datetime, timedelta
    now = datetime.now()
    date_context = (
        f"Today's date is {now:%A, %Y-%m-%d}. "
        f"Tomorrow is {now + timedelta(days=1):%A, %Y-%m-%d}. "
        f"Resolve any relative dates against these actual dates, and pass the "
        f"correct YYYY-MM-DD to any tool that takes a date."
    )
    region_context = (
        f"The customer's region is {region_label} (GSP region {applied_region}). "
        f"Electricity prices and the solar/weather forecast are already set to "
        f"this region — you do not need to specify a location for weather."
    )
    base_context = req.context or ""
    full_context = f"{base_context}\n{date_context}\n{region_context}".strip()

    try:
        response = AGENT.invoke(question=req.question, context=full_context)
        msgs = response.get("messages", [])
        answer = msgs[-1].content if msgs else ""

        tools_used = []
        for m in msgs:
            try:
                obj = m.model_dump()
            except AttributeError:
                obj = {}
            if obj.get("tool_call_id"):
                name = obj.get("name") or getattr(m, "name", None)
                if name and name not in tools_used:
                    tools_used.append(name)

        return ChatResponse(answer=answer, tools_used=tools_used)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[chat] error: {type(e).__name__}: {e}")
        raise HTTPException(500, "The agent hit an error answering that. "
                                 "Please try rephrasing your question.")