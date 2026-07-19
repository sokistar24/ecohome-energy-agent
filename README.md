# ⚡ EcoHome Energy Agent

**Live at [ecohomeagent.com](https://www.ecohomeagent.com)** · **Paper: [arXiv:2607.04569](https://arxiv.org/abs/2607.04569)**

An AI agent that tells you **when to run your home devices** — your EV, dishwasher,
heating, pool pump — to **minimise electricity costs** and **make the most of your
solar power**. Ask it a question in plain English and it reasons over electricity
prices, weather/solar forecasts, usage history, and a knowledge base of energy-saving
best practices, then gives a specific, data-backed recommendation.

Built with **LangChain + LangGraph**, wrapped in a **FastAPI** service, and served
through a **Next.js** chat interface — deployed end to end as a real product.

> **Note:** This is a portfolio project. It runs on **sample household data**, so
> recommendations illustrate the capability rather than reflecting a real home.

---

## What it does

Ask *"When should I charge my EV tomorrow to minimise cost and maximise solar
power?"* and the agent will:

1. Work out which devices, timeframe, and goal are involved.
2. Gather the data it needs — electricity prices, the weather/solar forecast, and
   past usage — by calling its tools.
3. Retrieve relevant energy-saving tips from a knowledge base (RAG).
4. Calculate the potential savings.
5. Return a clear recommendation: a **specific time window**, a **cost analysis**,
   a **solar consideration**, and a **savings estimate**.

Every answer in the web app shows a **"Data used"** line listing the tools the agent
called — you can see it grounding its advice in real data rather than just chatting.

![Demo — dishwasher scheduling with cost analysis and visible tool call](dishwasher_demo.JPG)

---

## Architecture

Two independently deployed services talking over HTTPS — the same
frontend/backend separation used by production AI products:

```
ecohomeagent.com
      │
      ▼
┌─────────────────────┐         ┌──────────────────────────────┐
│  Next.js frontend   │  HTTPS  │  FastAPI backend (Render)    │
│  (Vercel)           │ ──────► │  /chat  /health              │
│  chat UI, status    │         │  CORS, rate limiting         │
│  pill, tool badges  │         │        │                     │
└─────────────────────┘         │        ▼                     │
                                │  LangGraph ReAct agent       │
                                │  ├── 7 tools                 │
                                │  ├── SQLite (usage + solar)  │
                                │  └── Chroma vector store     │
                                │        │                     │
                                └────────┼─────────────────────┘
                                         ▼
                                   OpenAI API (gpt-4o-mini)
```

The agent is a **LangGraph ReAct loop**: the LLM reasons about what it needs, calls
a tool, reads the result, and repeats until it can answer.

![Agent architecture — LangGraph ReAct loop with tools, database, and vector store](architecture_diagram.png)

| Layer | What it is |
|-------|------------|
| **Frontend** (`ecohome-frontend/`) | Next.js + Tailwind chat app: suggestion chips, live agent-status pill, tool-call transparency, graceful cold-start handling |
| **API** (`ecohome_starter/api.py`) | FastAPI wrapper: `/chat` + `/health`, CORS via environment config, per-IP rate limiting, startup bootstrap that builds the DB and vector store on the server |
| **Agent** (`ecohome_starter/agent.py`) | LangGraph `create_react_agent`, GPT-4o-mini, temperature 0 |
| **Tools** (`ecohome_starter/tools.py`) | 7 tools: 2 external-API (weather, pricing), 3 database, 1 RAG search, 1 savings calculator |
| **External APIs** | Real **Open-Meteo** (weather + solar irradiance) and **Octopus Agile** (UK electricity prices), each with a mock fallback |
| **Database** | SQLite with energy-usage and solar-generation tables (SQLAlchemy) |
| **Knowledge base** | Chroma vector store over 7 energy-saving documents |

---

## Deployment

Both services deploy automatically from this repo on every push to `main`:

- **Backend → Render**: root directory `ecohome_starter`, started with
  `uvicorn api:app --host 0.0.0.0 --port $PORT`. At startup, a bootstrap
  rebuilds the SQLite database and Chroma vector store, so the server is fully
  self-provisioning — no data files live in the repo.
- **Frontend → Vercel**: root directory `ecohome-frontend`, with
  `NEXT_PUBLIC_API_URL` pointing at the Render service. The custom domain is
  connected through Namecheap DNS.

**Secrets and configuration never touch the repo.** The OpenAI key and allowed
CORS origins live in Render's environment vault; the frontend holds no secrets at
all — the browser only ever sees the API's address. Cost guardrails are layered:
per-IP rate limiting in the API, a spend alert on the OpenAI project, and prepaid
credits with auto-recharge off as the hard stop.

One honest free-tier trade-off: the backend sleeps when idle and takes ~30–60s to
wake. The frontend handles this visibly — the status pill pings `/health` on page
load (which starts waking the server before you've typed anything) and long waits
show a "waking the agent up…" message instead of a silent stall.

---

## Repository structure

```
├── ecohome_starter/            # Python backend
│   ├── models/energy.py        #   SQLAlchemy models + DatabaseManager
│   ├── data/documents/         #   7 knowledge-base docs (DB + vectorstore are built, not committed)
│   ├── agent.py                #   the LangGraph agent
│   ├── tools.py                #   the 7 agent tools
│   ├── api.py                  #   FastAPI service (deployed to Render)
│   ├── app.py                  #   Streamlit demo app (local dev tool)
│   ├── visualizations.py       #   chart helpers
│   ├── smoke_test.py           #   end-to-end check script
│   ├── requirements.txt        #   pinned, deployment-verified dependencies
│   ├── 01_db_setup.ipynb       #   build + populate the database
│   ├── 02_rag_setup.ipynb      #   build the RAG vector store
│   └── 03_run_and_evaluate.ipynb  # run the agent + full evaluation
└── ecohome-frontend/           # Next.js frontend (deployed to Vercel)
    ├── app/                    #   layout, page, design tokens
    ├── components/Chat.tsx     #   the chat interface
    └── lib/api.ts              #   the only file that talks to the backend
```

---

## Run it locally

**Requirements:** Python 3.11 and Node 18+.

### Backend

```bash
cd ecohome_starter
pip install -r requirements.txt
```

Create a `.env` file next to `agent.py`:

```
OPENAI_API_KEY=sk-your-key-here
```

Build the data stores once: run **`01_db_setup.ipynb`** then **`02_rag_setup.ipynb`**.
Verify every layer with:

```bash
python smoke_test.py
```

Then start the API:

```bash
uvicorn api:app --reload --port 8000
```

### Frontend

```bash
cd ecohome-frontend
npm install
npm run dev
```

Open `http://localhost:3000` — the status pill goes green when it finds the local
API. (The frontend's `.env.local` defaults to `http://localhost:8000`.)

### Streamlit demo (optional)

A local-only alternative UI with data charts in the sidebar:

```bash
cd ecohome_starter
streamlit run app.py
```

---

## How it's evaluated

`03_run_and_evaluate.ipynb` runs the agent across 12 test cases and scores it on
two axes:

- **Response quality** — accuracy, relevance, completeness, usefulness, scored by
  an LLM-as-judge (with a rule-based fallback if no API is available).
- **Tool usage** — whether the agent called the *right* tools (appropriateness) and
  *all* the needed tools (completeness), scored with set comparisons against the
  expected tools per test case.

A report aggregates these into overall scores, identifies strengths and weaknesses
(including catching inconsistent metrics a simple average would hide), and generates
improvement recommendations.

---

## Troubleshooting (local setup)

Real issues encountered setting up on **Windows + Anaconda**, with fixes:

| Symptom | Cause & fix |
|---------|-------------|
| `ModuleNotFoundError: No module named 'langchain.text_splitter'` | Modern LangChain split this out. Use `from langchain_text_splitters import RecursiveCharacterTextSplitter`. |
| RAG step **crashes silently** when loading the vector store | `chromadb` needs **`onnxruntime`** on Windows. `pip install onnxruntime`. |
| `OMP: Error #15: ...libiomp5md.dll already initialized` | Duplicate OpenMP runtime (common in Anaconda). Set `os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"` at the very top, before other imports. (Already handled in `app.py` and `api.py`.) |
| `Missing credentials ... OPENAI_API_KEY` even though `.env` exists | The code that runs must call `load_dotenv()`. Run from the project root so `.env` is found. |
| `no such table: energy_usage` | Run `01_db_setup.ipynb` first to create the database. |
| `splits: 0` / empty embeddings when building the store | The `.txt` documents must be in `data/documents/` — the loader globs that folder. |
| Notebook can't find installed packages | VS Code may be on a different kernel than your terminal. Point the notebook at the environment where you installed the packages. |
| Can't delete `data/vectorstore/` ("file in use") | A notebook kernel is holding it open. Close the notebooks, then delete. |
| Frontend can't reach a deployed backend (CORS error in console) | The backend allows origins from the `ALLOWED_ORIGINS` env var — add the frontend's exact origin (scheme + host, no trailing slash). |

> **Tip:** if you rebuild the knowledge base after adding documents, delete
> `data/vectorstore/` first — the store is cached and won't rebuild if it exists.

---

## Roadmap

- **Live data charts** in the web app — price curve, usage by device, solar
  generation — served as JSON by the API and rendered interactively in the browser
- Streaming responses (answers type out as the agent writes them)
- Conversation memory within a session
- System-prompt refinements from evaluation findings (e.g. device-type mapping for
  appliance queries)

---

## Key technologies

**LangChain** · **LangGraph** (ReAct agent) · **ChromaDB** (RAG) · **OpenAI**
(LLM + embeddings) · **FastAPI** · **Next.js** + **Tailwind** · **SQLAlchemy** +
**SQLite** · **Render** + **Vercel** + **Namecheap** (deployment) · **Streamlit** ·
**matplotlib**

---

## Further reading

The design of this project — a tool-calling ReAct agent over live Octopus Agile
prices, weather/solar forecasts, household usage, and a RAG knowledge base — closely
mirrors the setup studied in the following paper, which benchmarks GPT-4o-mini,
Gemini 2.5 Flash, and Claude Sonnet 4.6 on multi-appliance home energy scheduling:

- Jonah, S. (2026). *LLMs for Agentic Home Energy Management.* arXiv preprint [arXiv:2607.04569](https://arxiv.org/abs/2607.04569).

---

## License

Educational / portfolio project.
