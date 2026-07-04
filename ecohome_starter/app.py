"""
EcoHome Energy Advisor — local Streamlit demo app.

Run it with:   streamlit run app.py

This wraps the SAME agent from agent.py in a chat UI, and shows live charts
of the underlying energy data in the sidebar. It is a proof-of-concept / demo:
the energy data is sample data, so recommendations illustrate the capability
rather than reflecting a real household.

Requirements: streamlit, matplotlib (plus the project's existing deps).
"""
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import streamlit as st
from dotenv import load_dotenv

# Project modules — the real agent, tools, database, and our chart helpers.
from agent import Agent
from tools import get_electricity_prices
from models.energy import DatabaseManager
import visualizations as viz

# The system prompt. Import it if it's a module; otherwise paste your prompt here.
try:
    from ecohome_system_prompt import ECOHOME_SYSTEM_PROMPT
except Exception:
    ECOHOME_SYSTEM_PROMPT = (
        "You are the EcoHome Energy Advisor for a UK smart-home energy company. "
        "Use your tools to gather electricity prices, weather/solar forecasts, the "
        "customer's usage history, and energy-saving tips, then give a specific, "
        "time-based recommendation with costs in GBP and a clear reason. Always "
        "include a specific time window, a cost analysis, and where relevant a "
        "solar consideration and a savings estimate."
    )

load_dotenv()

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="EcoHome Energy Agent",
    page_icon="⚡",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Cached resources — built once, reused across reruns (Streamlit reruns the
# whole script on every interaction, so caching avoids rebuilding the agent
# and reconnecting to the DB each time).
# ---------------------------------------------------------------------------
@st.cache_resource
def get_agent():
    return Agent(instructions=ECOHOME_SYSTEM_PROMPT)


@st.cache_resource
def get_db():
    return DatabaseManager()


@st.cache_data(ttl=300)
def get_prices():
    """Cache prices for 5 min so the sidebar charts don't refetch every rerun."""
    return get_electricity_prices.invoke({})


def extract_final_and_tools(response):
    """Pull the final answer text and the list of tools called from a response."""
    msgs = response.get("messages", [])
    final = msgs[-1].content if msgs else ""
    tools = []
    for m in msgs:
        try:
            obj = m.model_dump()
        except AttributeError:
            obj = {}
        if obj.get("tool_call_id"):
            name = obj.get("name") or getattr(m, "name", None)
            if name:
                tools.append(name)
    return final, tools


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("⚡ EcoHome Energy Agent")
st.caption(
    "Ask when to run your devices to save money and use more solar power. "
    "**Demo using sample data** — recommendations illustrate the capability "
    "and are not based on a real household's usage."
)


# ---------------------------------------------------------------------------
# Sidebar — data dashboard
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("📊 Energy Data")
    st.caption("Charts from the sample database the advisor reasons over.")

    db = get_db()

    try:
        prices = get_prices()
        src = prices.get("data_source", "?")
        st.markdown(f"**Electricity prices** &nbsp; `source: {src}`")
        st.pyplot(viz.price_curve_figure(prices))
    except Exception as e:
        st.warning(f"Could not load price chart: {e}")

    with st.expander("Usage & solar patterns", expanded=False):
        try:
            st.pyplot(viz.usage_by_hour_figure(db))
            st.pyplot(viz.solar_generation_figure(db))
            st.pyplot(viz.device_breakdown_figure(db))
        except Exception as e:
            st.warning(f"Could not load data charts: {e}. "
                       "Has 01_db_setup.ipynb been run?")

    st.divider()
    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = []
        st.rerun()

    with st.expander("ℹ️ About this demo"):
        st.markdown(
            "**EcoHome Energy Agent** is an AI agent that recommends when to run "
            "home devices to cut electricity costs and use more solar power.\n\n"
            "It uses **LangChain + LangGraph** to reason over electricity prices, "
            "weather/solar forecasts, usage history, and a knowledge base of "
            "energy-saving tips (via RAG).\n\n"
            "_This is a proof-of-concept on sample data — it does not reflect a "
            "real household._"
        )


# ---------------------------------------------------------------------------
# Chat — main area
# ---------------------------------------------------------------------------

# Seed some example questions to guide first-time users.
EXAMPLES = [
    "When should I charge my EV tomorrow to minimise cost?",
    "What's the cheapest time to run my dishwasher?",
    "How can I maximise my solar power use tomorrow?",
    "Suggest three ways to cut my heating costs.",
]

if "messages" not in st.session_state:
    st.session_state.messages = []

# Show example chips only before the first message.
if not st.session_state.messages:
    st.markdown("**Try asking:**")
    cols = st.columns(2)
    for i, ex in enumerate(EXAMPLES):
        if cols[i % 2].button(ex, key=f"ex_{i}"):
            st.session_state.pending = ex
            st.rerun()

# Replay the conversation so far.
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("tools"):
            st.caption("🔧 Tools used: " + ", ".join(msg["tools"]))

# Take input either from the chat box or a clicked example chip.
prompt = st.chat_input("Ask about saving energy...")
if "pending" in st.session_state:
    prompt = st.session_state.pop("pending")

if prompt:
    # Show and store the user's message.
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get the agent's answer.
    with st.chat_message("assistant"):
        with st.spinner("Analysing prices, weather, and your usage..."):
            try:
                agent = get_agent()
                response = agent.invoke(question=prompt, context="Location: London, UK")
                answer, tools = extract_final_and_tools(response)
            except Exception as e:
                answer, tools = f"Sorry, something went wrong: {e}", []

        st.markdown(answer)
        if tools:
            st.caption("🔧 Tools used: " + ", ".join(tools))

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "tools": tools}
    )