import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "About · EcoHome Energy Advisor",
  description:
    "What the EcoHome Energy Advisor does today, where it's heading, and the research behind it.",
};

export default function About() {
  return (
    <div className="flex min-h-dvh flex-col">
      {/* Header — mirrors the chat header, with a link back to the app */}
      <header className="sticky top-0 z-10 border-b border-mist bg-paper/90 backdrop-blur">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-3 px-4 py-3">
          <Link href="/" className="flex items-baseline gap-2">
            <span className="font-display text-lg font-bold tracking-tight text-pine-deep">
              EcoHome
            </span>
            <span className="hidden text-sm text-ink/55 sm:inline">
              Energy Advisor
            </span>
          </Link>
          <Link
            href="/"
            className="rounded-full border border-mist bg-white px-3 py-1 text-xs font-medium text-ink/70 transition-colors hover:border-pine/40 hover:text-pine"
          >
            ← Back to the advisor
          </Link>
        </div>
      </header>

      {/* Body */}
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-10">
        <h1 className="font-display text-3xl font-bold tracking-tight text-pine-deep sm:text-4xl">
          About EcoHome
        </h1>
        <p className="mt-3 max-w-2xl text-ink/70">
          EcoHome is an AI agent that helps you run a smart home more cheaply and
          with a lower carbon footprint. Ask it when to charge your EV, run an
          appliance, or make the most of solar, and it gives a specific,
          time-based recommendation backed by live data.
        </p>

        {/* What it does today */}
        <section className="mt-10">
          <h2 className="font-display text-xl font-bold text-pine-deep">
            What it does today
          </h2>
          <div className="mt-4 space-y-4 text-ink/80">
            <p>
              The advisor reasons over two live data sources for your selected UK
              region: half-hourly electricity prices from the Octopus Agile
              tariff, and hourly solar irradiance from a weather forecast. From
              these it works out the cheapest and greenest hours and turns them
              into plain-language advice, for example the best window to charge
              an EV tomorrow to line up with low prices and peak sun.
            </p>
            <p>
              It runs as an LLM agent with a small set of tools: live pricing, a
              solar and weather forecast, a knowledge base of energy-saving best
              practice, and a savings calculator. It picks the right tools for
              each question, then synthesises a recommendation with the numbers
              to back it up.
            </p>
            <p className="rounded-xl border border-mist bg-white/60 px-4 py-3 text-sm text-ink/70">
              This is a demonstration. It runs on a{" "}
              <span className="font-semibold text-ink">sample household</span>{" "}
              dataset, not real smart-meter readings, so its usage figures are
              illustrative. Prices and solar forecasts, however, are live and
              region-accurate.
            </p>
          </div>
        </section>

        {/* Roadmap */}
        <section className="mt-10">
          <div className="flex items-center gap-3">
            <h2 className="font-display text-xl font-bold text-pine-deep">
              Where it's heading
            </h2>
            <span className="rounded-full bg-solar/15 px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wide text-ink/60">
              Roadmap
            </span>
          </div>
          <p className="mt-3 text-sm text-ink/60">
            These are planned and exploratory directions, not current features.
          </p>
          <ul className="mt-4 space-y-3 text-ink/80">
            <li className="flex gap-3">
              <span className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-pine" />
              <span>
                <span className="font-semibold text-ink">
                  Real smart-meter integration.
                </span>{" "}
                Connecting to a household&apos;s actual consumption data (for
                example via the Octopus consumption API), with the user&apos;s
                consent, so advice can be grounded in how the home really uses
                energy rather than a sample profile.
              </span>
            </li>
            <li className="flex gap-3">
              <span className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-pine" />
              <span>
                <span className="font-semibold text-ink">
                  Personalised usage insights.
                </span>{" "}
                Once real usage is available, spotting a household&apos;s own
                patterns and suggesting specific, measurable ways to shift load
                to cheaper, greener hours.
              </span>
            </li>
            <li className="flex gap-3">
              <span className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-pine" />
              <span>
                <span className="font-semibold text-ink">
                  Automated scheduling.
                </span>{" "}
                Moving from advice to action, letting the agent schedule
                compatible devices (EV chargers, batteries, appliances) directly
                around price and solar forecasts.
              </span>
            </li>
            <li className="flex gap-3">
              <span className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-pine" />
              <span>
                <span className="font-semibold text-ink">
                  Wider tariff and region coverage.
                </span>{" "}
                Supporting more energy tariffs and markets beyond UK Agile
                pricing.
              </span>
            </li>
          </ul>
        </section>

        {/* Research & code */}
        <section className="mt-10">
          <h2 className="font-display text-xl font-bold text-pine-deep">
            Research &amp; code
          </h2>
          <div className="mt-4 space-y-4">
            <div className="rounded-xl border border-mist bg-white/60 px-4 py-4">
              <p className="text-ink/80">
                This work is described in an accompanying paper:
              </p>
              <p className="mt-2 text-ink">
                S. Jonah (2026).{" "}
                <span className="font-semibold">
                  LLMs for Agentic Home Energy Management.
                </span>{" "}
                arXiv preprint{" "}
                <a
                  href="https://arxiv.org/abs/2607.04569"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-pine underline hover:text-pine-deep"
                >
                  arXiv:2607.04569
                </a>
                .
              </p>
              <p className="mt-2 text-xs text-ink/50">
                Preprint — the peer-reviewed version will replace this link once
                published.
              </p>
            </div>

            <a
              href="https://github.com/sokistar24/ecohome-energy-agent"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-xl border border-mist bg-white px-4 py-2.5 text-sm font-medium text-ink/80 shadow-sm transition-colors hover:border-pine/40 hover:text-pine"
            >
              <span>View the source on GitHub</span>
              <span aria-hidden>→</span>
            </a>
          </div>
        </section>

        <p className="mt-12 text-xs text-ink/40">
          EcoHome is a portfolio and research demonstration. Its recommendations
          use sample data and are not a substitute for professional energy
          advice.
        </p>
      </main>
    </div>
  );
}
