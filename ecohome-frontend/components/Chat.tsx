"use client";

/**
 * The full chat interface. "use client" marks this as a Client Component —
 * it runs in the browser, which is required because it holds state
 * (the conversation) and responds to user events. Everything else in the
 * app can stay as fast, static server-rendered code.
 */

import { useEffect, useRef, useState } from "react";
import { askAgent, checkHealth, ApiError } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types & constants
// ---------------------------------------------------------------------------

interface Message {
  role: "user" | "assistant";
  content: string;
  toolsUsed?: string[];
  isError?: boolean;
}

type AgentStatus = "checking" | "waking" | "online" | "offline";

const SUGGESTED_QUESTIONS = [
  "When should I charge my EV tomorrow to minimise cost and maximise solar?",
  "What thermostat setting saves the most during this week's price peaks?",
  "Suggest three ways to cut my energy use based on my usage history.",
  "How much can I save running the dishwasher off-peak?",
];

const MAX_QUESTION_LENGTH = 500;

// How long before we assume the delay is a Render cold start (ms)
const COLD_START_HINT_AFTER = 8000;

// ---------------------------------------------------------------------------
// Small presentational pieces
// ---------------------------------------------------------------------------

function StatusPill({ status }: { status: AgentStatus }) {
  const config = {
    checking: { dot: "bg-mist", label: "Checking agent…", pulse: true },
    waking: { dot: "bg-solar", label: "Agent waking up…", pulse: true },
    online: { dot: "bg-meter", label: "Agent online", pulse: false },
    offline: { dot: "bg-fault", label: "Agent offline", pulse: false },
  }[status];

  return (
    <span
      className="inline-flex items-center gap-2 rounded-full border border-mist bg-white px-3 py-1 text-xs font-medium text-ink/70"
      role="status"
    >
      <span
        className={`h-2 w-2 rounded-full ${config.dot} ${
          config.pulse ? "status-waking" : ""
        }`}
      />
      {config.label}
    </span>
  );
}

function ToolChips({ tools }: { tools: string[] }) {
  if (!tools.length) return null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-mist pt-2.5">
      <span className="text-[11px] font-medium uppercase tracking-wide text-ink/45">
        Data used
      </span>
      {tools.map((tool) => (
        <span
          key={tool}
          className="rounded-md bg-pine/8 px-2 py-0.5 font-mono text-[11px] text-pine"
        >
          {tool}
        </span>
      ))}
    </div>
  );
}

function TypingIndicator({ coldStart }: { coldStart: boolean }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-mist bg-white px-4 py-3 shadow-sm">
        <div className="flex items-center gap-2">
          <span className="flex gap-1">
            <span className="typing-dot h-1.5 w-1.5 rounded-full bg-pine" />
            <span className="typing-dot h-1.5 w-1.5 rounded-full bg-pine" />
            <span className="typing-dot h-1.5 w-1.5 rounded-full bg-pine" />
          </span>
          <span className="text-sm text-ink/60">
            {coldStart
              ? "Waking the agent up — the first answer can take up to a minute…"
              : "Checking prices, weather and your data…"}
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// The chat component
// ---------------------------------------------------------------------------

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [coldStartHint, setColdStartHint] = useState(false);
  const [status, setStatus] = useState<AgentStatus>("checking");

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // --- Health check on load ------------------------------------------------
  // First ping tells us the state; if the backend is asleep (Render free
  // tier), we keep pinging every 5s — which also actively wakes it up
  // before the visitor sends their first question.
  useEffect(() => {
    let cancelled = false;
    let attempts = 0;

    async function ping() {
      const ok = await checkHealth();
      if (cancelled) return;
      if (ok) {
        setStatus("online");
        return;
      }
      attempts += 1;
      setStatus(attempts >= 18 ? "offline" : "waking"); // ~90s of patience
      if (attempts < 18) setTimeout(ping, 5000);
    }

    ping();
    return () => {
      cancelled = true;
    };
  }, []);

  // --- Auto-scroll to the newest message -----------------------------------
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // --- Sending a question ---------------------------------------------------
  async function send(question: string) {
    const trimmed = question.trim();
    if (!trimmed || isLoading) return;

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setIsLoading(true);
    setColdStartHint(false);

    // If the reply takes long, explain the likely cold start honestly
    const hintTimer = setTimeout(
      () => setColdStartHint(true),
      COLD_START_HINT_AFTER
    );

    try {
      const reply = await askAgent(trimmed);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: reply.answer || "The agent returned an empty answer — try rephrasing.",
          toolsUsed: reply.toolsUsed,
        },
      ]);
      setStatus("online"); // a successful answer proves it's awake
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : "Something unexpected went wrong. Try again.";
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: message, isError: true },
      ]);
    } finally {
      clearTimeout(hintTimer);
      setIsLoading(false);
      setColdStartHint(false);
      inputRef.current?.focus();
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter makes a new line
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="flex min-h-dvh flex-col">
      {/* ------------------------------------------------ Header */}
      <header className="sticky top-0 z-10 border-b border-mist bg-paper/90 backdrop-blur">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-baseline gap-2">
            <span className="font-display text-lg font-bold tracking-tight text-pine-deep">
              EcoHome
            </span>
            <span className="hidden text-sm text-ink/55 sm:inline">
              Energy Advisor
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden rounded-full bg-solar/15 px-3 py-1 text-xs font-medium text-ink/70 sm:inline">
              Portfolio demo · sample household data
            </span>
            <StatusPill status={status} />
          </div>
        </div>
      </header>

      {/* ------------------------------------------------ Messages */}
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-6">
        {isEmpty && (
          <div className="my-auto flex flex-col items-center gap-6 py-10 text-center">
            <div>
              <h1 className="font-display text-3xl font-bold tracking-tight text-pine-deep sm:text-4xl">
                Ask the Energy Advisor
              </h1>
              <p className="mx-auto mt-3 max-w-md text-ink/60">
                An AI agent that checks electricity prices, weather forecasts
                and household usage data to answer questions about running a
                smart home cheaply.
              </p>
            </div>
            <div className="grid w-full gap-2 sm:grid-cols-2">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="rounded-xl border border-mist bg-white px-4 py-3 text-left text-sm text-ink/80 shadow-sm transition-colors hover:border-pine/40 hover:bg-pine/5"
                >
                  {q}
                </button>
              ))}
            </div>
            <p className="text-xs text-ink/40 sm:hidden">
              Portfolio demo — answers use sample household data.
            </p>
          </div>
        )}

        {messages.map((msg, i) =>
          msg.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-pine px-4 py-3 text-sm leading-relaxed text-white shadow-sm">
                {msg.content}
              </div>
            </div>
          ) : (
            <div key={i} className="flex justify-start">
              <div
                className={`max-w-[85%] rounded-2xl rounded-bl-sm border px-4 py-3 text-sm leading-relaxed shadow-sm ${
                  msg.isError
                    ? "border-fault/30 bg-fault/5 text-fault"
                    : "border-mist bg-white text-ink"
                }`}
              >
                <div className="whitespace-pre-wrap">{msg.content}</div>
                {msg.toolsUsed && <ToolChips tools={msg.toolsUsed} />}
              </div>
            </div>
          )
        )}

        {isLoading && <TypingIndicator coldStart={coldStartHint} />}
        <div ref={bottomRef} />
      </main>

      {/* ------------------------------------------------ Input */}
      <footer className="sticky bottom-0 border-t border-mist bg-paper/95 backdrop-blur">
        <div className="mx-auto w-full max-w-3xl px-4 py-3">
          <div className="flex items-end gap-2 rounded-2xl border border-mist bg-white p-2 shadow-sm focus-within:border-pine/40">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) =>
                setInput(e.target.value.slice(0, MAX_QUESTION_LENGTH))
              }
              onKeyDown={handleKeyDown}
              rows={1}
              placeholder="Ask about EV charging, thermostats, appliances, solar…"
              aria-label="Ask the Energy Advisor a question"
              className="max-h-32 min-h-[2.5rem] flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-ink placeholder:text-ink/40 focus:outline-none"
            />
            <button
              onClick={() => send(input)}
              disabled={isLoading || !input.trim()}
              className="rounded-xl bg-pine px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-pine-deep disabled:cursor-not-allowed disabled:opacity-40"
            >
              Ask
            </button>
          </div>
          <p className="mt-2 text-center text-[11px] text-ink/40">
            Answers are generated by an AI agent using sample data — a
            demonstration, not household advice.
          </p>
        </div>
      </footer>
    </div>
  );
}
