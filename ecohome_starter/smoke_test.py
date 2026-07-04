"""
EcoHome Energy Advisor — end-to-end smoke test.

Run this from your ecohome_solution/ folder AFTER:
  1. pip install -r requirements.txt
  2. creating a .env file with OPENAI_API_KEY=sk-...
  3. running 01_db_setup.ipynb and 02_rag_setup.ipynb at least once

It checks each layer in order and stops at the first failure with a clear
message, so you know exactly what to fix. Paste the output back if anything fails.

Usage:  python smoke_test.py
"""
import os
import sys
import traceback

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"


def step(n, label):
    print(f"\n{INFO} Step {n}: {label}")


def ok(msg):
    print(f"  {PASS} {msg}")


def die(msg, err=None):
    print(f"  {FAIL} {msg}")
    if err:
        print("  ---- error detail ----")
        traceback.print_exc()
        print("  ----------------------")
    print("\nSmoke test stopped. Fix the above and re-run.")
    sys.exit(1)


def main():
    print("=" * 60)
    print("   EcoHome Energy Advisor — Smoke Test")
    print("=" * 60)

    # --- Step 1: environment / API key ---
    step(1, "Load .env and check OPENAI_API_KEY")
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception as e:
        die("Could not import/load python-dotenv. Is it installed?", e)
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        die("OPENAI_API_KEY not found. Create a .env file with OPENAI_API_KEY=sk-...")
    if not key.startswith("sk-"):
        print(f"  {INFO} Key found but doesn't start with 'sk-' — double-check it's correct.")
    ok(f"OPENAI_API_KEY loaded (starts with {key[:6]}...).")

    # --- Step 2: imports ---
    step(2, "Import project modules")
    try:
        import requests  # noqa
        from tools import (TOOL_KIT, get_weather_forecast, get_electricity_prices,
                           search_energy_tips)
        from agent import Agent
        ok(f"Imported agent + tools. Toolkit has {len(TOOL_KIT)} tools.")
    except Exception as e:
        die("Failed to import project modules. Check tools.py / agent.py are present "
            "and dependencies installed.", e)

    # --- Step 3: weather tool (real API + fallback) ---
    step(3, "Call get_weather_forecast (Open-Meteo, falls back to mock)")
    try:
        wx = get_weather_forecast.invoke({"location": "London, UK", "days": 1})
        src = wx.get("data_source", "?")
        n_hours = len(wx.get("hourly", []))
        ok(f"Weather returned {n_hours} hourly entries, data_source='{src}'.")
        if src == "mock":
            print(f"  {INFO} Used MOCK (live API unreachable). Fine, but check internet "
                  "if you wanted real data.")
        else:
            # spot-check that irradiance peaks in daylight
            midday = [h for h in wx["hourly"] if h["hour"] == 12]
            if midday:
                print(f"  {INFO} Real data: midday irradiance = "
                      f"{midday[0].get('solar_irradiance')} W/m².")
    except Exception as e:
        die("get_weather_forecast raised an exception.", e)

    # --- Step 4: pricing tool (real API + fallback) ---
    step(4, "Call get_electricity_prices (Octopus Agile, falls back to mock)")
    try:
        pr = get_electricity_prices.invoke({})
        src = pr.get("data_source", "?")
        n_rates = len(pr.get("hourly_rates", []))
        ok(f"Pricing returned {n_rates} hourly rates, data_source='{src}', "
           f"currency={pr.get('currency')}.")
        if src == "mock":
            print(f"  {INFO} Used MOCK (live API unreachable). Fine for the project.")
    except Exception as e:
        die("get_electricity_prices raised an exception.", e)

    # --- Step 5: database tools (need 01_db_setup to have run) ---
    step(5, "Query the database (needs 01_db_setup.ipynb to have run)")
    try:
        from tools import get_recent_energy_summary
        summ = get_recent_energy_summary.invoke({"hours": 168})
        if "error" in summ:
            die(f"DB query returned an error: {summ['error']}. "
                "Did you run 01_db_setup.ipynb to create + populate the database?")
        used = summ.get("usage", {}).get("total_consumption_kwh", 0)
        ok(f"Database reachable. Last-week consumption total = {used} kWh.")
        if used == 0:
            print(f"  {INFO} 0 kWh — the DB may be empty. Re-run 01_db_setup.ipynb.")
    except Exception as e:
        die("Database tool raised an exception.", e)

    # --- Step 6: RAG search (needs 02_rag_setup + the doc-loading glob fix) ---
    step(6, "Search energy tips (RAG — needs 02_rag_setup.ipynb to have run)")
    try:
        tips = search_energy_tips.invoke({"query": "home battery storage off-peak",
                                          "max_results": 3})
        if "error" in tips:
            die(f"RAG returned an error: {tips['error']}. "
                "Did you run 02_rag_setup.ipynb? Is OPENAI_API_KEY valid for embeddings?")
        n = tips.get("total_results", 0)
        ok(f"RAG returned {n} tip(s).")
        if n == 0:
            print(f"  {INFO} 0 results — vector store may be empty. Re-run 02_rag_setup.ipynb.")
        else:
            sources = {t.get("source", "?").split("/")[-1] for t in tips["tips"]}
            print(f"  {INFO} Retrieved from: {sources}")
            # The whole point of the glob fix: new docs should be retrievable
            if any("storage" in s for s in sources):
                ok("New knowledge-base doc (energy_storage) is being retrieved — glob fix works.")
    except Exception as e:
        die("search_energy_tips raised an exception.", e)

    # --- Step 7: full agent invoke (the real end-to-end test) ---
    step(7, "Run the full agent on one question (end-to-end)")
    try:
        from ecohome_system_prompt import ECOHOME_SYSTEM_PROMPT
    except Exception:
        # If the prompt isn't a separate module, define a minimal one for the test.
        ECOHOME_SYSTEM_PROMPT = ("You are the EcoHome Energy Advisor. Use your tools "
                                 "to gather price, weather, and tip data, then give a "
                                 "specific, time-based recommendation with costs.")
        print(f"  {INFO} Using a minimal inline prompt (ecohome_system_prompt.py not found).")
    try:
        agent = Agent(instructions=ECOHOME_SYSTEM_PROMPT)
        resp = agent.invoke(
            question="When should I charge my EV tomorrow to minimise cost?",
            context="Location: London, UK",
        )
        msgs = resp["messages"]
        final = msgs[-1].content
        tools_called = [m.name for m in msgs
                        if getattr(m, "name", None) and
                        getattr(m, "tool_call_id", None) is not None or
                        (hasattr(m, "model_dump") and m.model_dump().get("tool_call_id"))]
        ok(f"Agent answered. Final message length = {len(final)} chars.")
        print(f"  {INFO} Tools the agent called: {tools_called or '(none — check prompt pushes tool use)'}")
        print(f"\n  ---- Agent's answer (first 400 chars) ----")
        print("  " + final[:400].replace("\n", "\n  "))
        print("  ------------------------------------------")
    except Exception as e:
        die("Full agent invoke failed. This is the key integration point — check the "
            "error detail below (often an API key or model-access issue).", e)

    # --- Step 8: evaluation functions ---
    step(8, "Run the evaluation functions on that response")
    try:
        # These live in the notebook; for the script, import from the snippet files
        # if present, else skip with a note.
        import importlib.util

        def load(modfile, names):
            spec = importlib.util.spec_from_file_location("m", modfile)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return [getattr(m, n) for n in names]

        have_evals = all(os.path.exists(f) for f in
                         ["eval_response.py", "eval_tool_usage.py", "eval_report.py"])
        if not have_evals:
            print(f"  {INFO} eval_*.py snippet files not in this folder — the functions "
                  "live in 03_run_and_evaluate.ipynb. Skipping (run them in the notebook).")
        else:
            (evaluate_response,) = load("eval_response.py", ["evaluate_response"])
            (evaluate_tool_usage,) = load("eval_tool_usage.py", ["evaluate_tool_usage"])
            re_ = evaluate_response(
                "When should I charge my EV tomorrow to minimise cost?",
                final, "Should give a specific time window and cost detail in GBP.")
            te_ = evaluate_tool_usage(msgs, ["get_electricity_prices"])
            ok(f"evaluate_response overall = {re_['overall_score']} (method: {re_['method']})")
            ok(f"evaluate_tool_usage overall = {te_['overall_tool_score']}")
    except Exception as e:
        die("Evaluation functions raised an exception.", e)

    print("\n" + "=" * 60)
    print(f"   {PASS} ALL STEPS PASSED — the project runs end-to-end.")
    print("=" * 60)


if __name__ == "__main__":
    main()
