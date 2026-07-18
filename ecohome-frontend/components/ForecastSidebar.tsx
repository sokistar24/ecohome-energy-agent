"use client";

/**
 * Sidebar showing tomorrow's (or today's) electricity price and solar
 * irradiance for the selected region. Reads /forecast, reacts to the region
 * prop, and is collapsible. Charts use Recharts, styled to match the EcoHome
 * palette (pine / ink / mist / solar). Data is honest: prices are the region's
 * real Agile rates; solar is the raw irradiance forecast (W/m²), no panel
 * assumptions.
 */

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  Area,
  AreaChart,
  XAxis,
  YAxis,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { fetchForecast, type Forecast, type ForecastDay } from "@/lib/api";

// EcoHome palette (hex mirrors the Tailwind tokens used across the app).
const C = {
  pine: "#2f6f4e",
  pineDeep: "#1f4d36",
  cheap: "#66bb6a",
  mid: "#9fb3ac",
  peak: "#e07a3f",
  solar: "#f2b705",
  ink: "#243027",
  mist: "#e4e9e5",
};

function periodColor(period: string | null): string {
  if (period === "off_peak") return C.cheap;
  if (period === "on_peak") return C.peak;
  return C.mid;
}

function formatHour(h: number): string {
  return `${String(h).padStart(2, "0")}:00`;
}

// ---- tooltips ------------------------------------------------------------

function PriceTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  if (d.price == null) return null;
  const label =
    d.period === "off_peak"
      ? "Off-peak"
      : d.period === "on_peak"
      ? "Peak"
      : "Mid-peak";
  return (
    <div className="rounded-lg border border-mist bg-white px-2.5 py-1.5 text-xs shadow-sm">
      <div className="font-medium text-ink">{formatHour(d.hour)}</div>
      <div className="text-ink/70">£{d.price.toFixed(4)}/kWh</div>
      <div className="text-ink/50">{label}</div>
    </div>
  );
}

function SolarTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg border border-mist bg-white px-2.5 py-1.5 text-xs shadow-sm">
      <div className="font-medium text-ink">{formatHour(d.hour)}</div>
      <div className="text-ink/70">
        {Math.round(d.solar_irradiance)} W/m²
      </div>
    </div>
  );
}

// ---- charts --------------------------------------------------------------

function PriceChart({ day }: { day: ForecastDay }) {
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <h3 className="font-display text-sm font-semibold text-pine-deep">
          Electricity price
        </h3>
        <span className="text-[11px] text-ink/45">£/kWh</span>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart
          data={day.hours}
          margin={{ top: 4, right: 4, bottom: 0, left: 4 }}
        >
          <XAxis
            dataKey="hour"
            ticks={[0, 3, 6, 9, 12, 15, 18, 21]}
            tickFormatter={(h) => formatHour(h)}
            tick={{ fontSize: 11, fill: C.ink }}
            tickLine={false}
            axisLine={{ stroke: C.mist }}
          />
          <YAxis
            tick={{ fontSize: 11, fill: C.ink }}
            tickLine={false}
            axisLine={false}
            width={52}
            tickFormatter={(v) => `£${v.toFixed(2)}`}
          />
          <Tooltip content={<PriceTooltip />} cursor={{ fill: "rgba(0,0,0,0.04)" }} />
          <Bar dataKey="price" radius={[2, 2, 0, 0]}>
            {day.hours.map((h) => (
              <Cell key={h.hour} fill={periodColor(h.period)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-ink/55">
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-sm" style={{ background: C.cheap }} />
          Off-peak
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-sm" style={{ background: C.mid }} />
          Mid
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-sm" style={{ background: C.peak }} />
          Peak
        </span>
      </div>
    </div>
  );
}

function SolarChart({ day }: { day: ForecastDay }) {
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <h3 className="font-display text-sm font-semibold text-pine-deep">
          Solar forecast
        </h3>
        <span className="text-[11px] text-ink/45">W/m²</span>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart
          data={day.hours}
          margin={{ top: 4, right: 4, bottom: 0, left: 4 }}
        >
          <defs>
            <linearGradient id="solarFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={C.solar} stopOpacity={0.5} />
              <stop offset="100%" stopColor={C.solar} stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="hour"
            ticks={[0, 3, 6, 9, 12, 15, 18, 21]}
            tickFormatter={(h) => formatHour(h)}
            tick={{ fontSize: 11, fill: C.ink }}
            tickLine={false}
            axisLine={{ stroke: C.mist }}
          />
          <YAxis
            tick={{ fontSize: 11, fill: C.ink }}
            tickLine={false}
            axisLine={false}
            width={40}
            tickFormatter={(v) => `${Math.round(v)}`}
          />
          <Tooltip content={<SolarTooltip />} cursor={{ stroke: C.mist }} />
          <Area
            type="monotone"
            dataKey="solar_irradiance"
            stroke={C.solar}
            strokeWidth={2}
            fill="url(#solarFill)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---- sidebar -------------------------------------------------------------

export default function ForecastSidebar({ region }: { region: string }) {
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [loading, setLoading] = useState(true);
  const [dayIndex, setDayIndex] = useState(1); // 0 = today, 1 = tomorrow
  const [open, setOpen] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchForecast(region).then((f) => {
      if (cancelled) return;
      setForecast(f);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [region]);

  const days = forecast?.days ?? [];
  const day = days[dayIndex] ?? days[0];

  return (
    <aside className="w-full lg:w-[26rem] lg:flex-shrink-0">
      <div className="rounded-2xl border border-mist bg-white/70 p-3 shadow-sm">
        {/* header row: title + collapse toggle */}
        <div className="flex items-center justify-between">
          <div className="flex items-baseline gap-2">
            <h2 className="font-display text-sm font-bold text-pine-deep">
              Forecast
            </h2>
            {forecast?.region_label && (
              <span className="text-[11px] text-ink/50">
                {forecast.region_label}
              </span>
            )}
          </div>
          <button
            onClick={() => setOpen((o) => !o)}
            className="rounded-md px-1.5 py-0.5 text-[11px] font-medium text-ink/55 hover:bg-pine/5 hover:text-pine"
            aria-expanded={open}
          >
            {open ? "Hide" : "Show"}
          </button>
        </div>

        {open && (
          <div className="mt-3">
            {/* Today / Tomorrow toggle */}
            {days.length > 1 && (
              <div className="mb-3 inline-flex rounded-lg border border-mist bg-paper/60 p-0.5 text-xs">
                {days.map((d, i) => (
                  <button
                    key={d.date}
                    onClick={() => setDayIndex(i)}
                    className={`rounded-md px-2.5 py-1 font-medium transition-colors ${
                      i === dayIndex
                        ? "bg-pine text-white shadow-sm"
                        : "text-ink/60 hover:text-pine"
                    }`}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            )}

            {loading ? (
              <div className="py-10 text-center text-xs text-ink/45">
                Loading forecast…
              </div>
            ) : !forecast || !day ? (
              <div className="py-8 text-center text-xs text-ink/50">
                Forecast unavailable right now. Prices and solar will appear
                here once the agent is reachable.
              </div>
            ) : (
              <div className="space-y-4">
                <PriceChart day={day} />
                <SolarChart day={day} />
                <p className="text-[10px] leading-relaxed text-ink/40">
                  Prices are live Octopus Agile rates for the selected region.
                  Solar shows forecast irradiance (W/m²), not system output.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
