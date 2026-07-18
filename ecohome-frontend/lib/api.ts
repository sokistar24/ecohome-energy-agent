/**
 * API client — the ONLY file that knows how to talk to the backend.
 *
 * The backend URL comes from an environment variable so the same code works
 * locally (http://localhost:8000) and in production (your Render URL) without
 * any code change — you just set NEXT_PUBLIC_API_URL per environment.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface AgentReply {
  answer: string;
  toolsUsed: string[];
}

export interface Region {
  code: string;
  label: string;
}

export interface ForecastHour {
  hour: number;
  price: number | null;
  period: string | null;
  solar_irradiance: number;
}

export interface ForecastDay {
  date: string;
  label: string; // "Today" | "Tomorrow"
  hours: ForecastHour[];
}

export interface Forecast {
  region: string;
  region_label: string;
  days: ForecastDay[];
}

/** Thrown for known, user-explainable failures (rate limit, server error). */
export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Ask the agent a question. POSTs to /chat and normalises the response.
 * Tolerant to field naming: accepts `answer` or `response`, and
 * `tools_used` or `tools`, so it survives small backend changes.
 * `region` is the UK GSP region code (A-P); defaults to "C" (London).
 */
export async function askAgent(
  question: string,
  region: string = "C"
): Promise<AgentReply> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, region }),
    });
  } catch {
    // Network-level failure: backend unreachable (down, CORS, wrong URL)
    throw new ApiError(
      "Couldn't reach the agent. It may still be waking up — try again in a few seconds."
    );
  }

  if (res.status === 429) {
    throw new ApiError(
      "You're sending questions a little too fast. Wait a few seconds and try again.",
      429
    );
  }
  if (!res.ok) {
    throw new ApiError(
      "The agent hit a problem answering that. Try again, or rephrase the question.",
      res.status
    );
  }

  const data = await res.json();
  return {
    answer: data.answer ?? data.response ?? "",
    toolsUsed: data.tools_used ?? data.tools ?? [],
  };
}

/**
 * Liveness check against /health. Returns true if the backend is awake.
 * Used by the header status pill (and it doubles as a warm-up ping:
 * calling it on page load starts waking a sleeping Render service
 * before the visitor even types).
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Fetch the list of selectable UK regions for the dropdown. Returns the
 * regions and the default code. Falls back to just London if the backend
 * is unreachable, so the UI always has at least one valid option.
 */
export async function fetchRegions(): Promise<{
  regions: Region[];
  default: string;
}> {
  try {
    const res = await fetch(`${API_URL}/regions`, { cache: "no-store" });
    if (!res.ok) throw new Error("bad status");
    const data = await res.json();
    return {
      regions: data.regions ?? [{ code: "C", label: "London" }],
      default: data.default ?? "C",
    };
  } catch {
    return { regions: [{ code: "C", label: "London" }], default: "C" };
  }
}

/**
 * Fetch chart data (hourly price + solar for today and tomorrow) for a region.
 * Returns null on failure so the sidebar can show an unobtrusive fallback
 * rather than breaking the page.
 */
export async function fetchForecast(
  region: string = "C"
): Promise<Forecast | null> {
  try {
    const res = await fetch(`${API_URL}/forecast?region=${encodeURIComponent(region)}`, {
      cache: "no-store",
    });
    if (!res.ok) throw new Error("bad status");
    return (await res.json()) as Forecast;
  } catch {
    return null;
  }
}
