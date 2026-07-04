"""
Visualization helpers for the EcoHome Energy Advisor.

Each function returns a matplotlib Figure, so it can be:
  - displayed live in the Streamlit app  (st.pyplot(fig))
  - saved to a PNG for the report          (fig.savefig(path))

All functions pull from the real tools / database, so the charts reflect
the same data the agent reasons over.
"""
import os
from datetime import datetime, timedelta
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")  # non-interactive backend; works headless and saves PNGs
import matplotlib.pyplot as plt

# A small, consistent colour palette so all charts look like one family.
COLORS = {
    "primary": "#2E7D32",    # green
    "accent": "#1565C0",     # blue
    "warn": "#E65100",       # orange (peak / expensive)
    "muted": "#90A4AE",      # grey
    "cheap": "#66BB6A",      # light green (cheap hours)
}


def _style_axes(ax, title, xlabel, ylabel):
    """Apply a clean, consistent look to an axis."""
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def price_curve_figure(prices: dict):
    """
    Bar chart of hourly electricity price, with cheap hours highlighted green
    and peak hours orange. Takes the dict returned by get_electricity_prices.
    """
    rates = prices.get("hourly_rates", [])
    hours = [r["hour"] for r in rates]
    values = [r["rate"] for r in rates]
    periods = [r.get("period", "mid_peak") for r in rates]

    # Colour each bar by its period.
    bar_colors = []
    for p in periods:
        if p == "off_peak":
            bar_colors.append(COLORS["cheap"])
        elif p == "on_peak":
            bar_colors.append(COLORS["warn"])
        else:
            bar_colors.append(COLORS["muted"])

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(hours, values, color=bar_colors, edgecolor="white", linewidth=0.5)
    currency = prices.get("currency", "GBP")
    _style_axes(ax, f"Electricity Price by Hour ({currency}/kWh)",
                "Hour of day", f"Price ({currency}/kWh)")
    ax.set_xticks(range(0, 24, 2))

    # Legend explaining the colours.
    from matplotlib.patches import Patch
    legend = [
        Patch(facecolor=COLORS["cheap"], label="Off-peak (cheap)"),
        Patch(facecolor=COLORS["muted"], label="Mid-peak"),
        Patch(facecolor=COLORS["warn"], label="On-peak (expensive)"),
    ]
    ax.legend(handles=legend, fontsize=8, loc="upper left", framealpha=0.9)
    fig.tight_layout()
    return fig


def usage_by_hour_figure(db_manager, days: int = 7):
    """
    Line chart of average energy consumption by hour of day over the last N days,
    showing the daily usage pattern. Pulls from the database.
    """
    end = datetime.now()
    start = end - timedelta(days=days)
    records = db_manager.get_usage_by_date_range(start, end)

    # Average consumption per hour-of-day across the period.
    hour_totals = defaultdict(float)
    hour_counts = defaultdict(int)
    for r in records:
        h = r.timestamp.hour
        hour_totals[h] += r.consumption_kwh
        hour_counts[h] += 1

    hours = list(range(24))
    avg = [hour_totals[h] / hour_counts[h] if hour_counts[h] else 0 for h in hours]

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(hours, avg, color=COLORS["accent"], linewidth=2.2, marker="o",
            markersize=4)
    ax.fill_between(hours, avg, alpha=0.12, color=COLORS["accent"])
    _style_axes(ax, f"Average Consumption by Hour (last {days} days)",
                "Hour of day", "Avg consumption (kWh)")
    ax.set_xticks(range(0, 24, 2))
    fig.tight_layout()
    return fig


def device_breakdown_figure(db_manager, days: int = 7):
    """
    Horizontal bar chart of total consumption by device type over the last N days.
    Shows which devices dominate usage. Pulls from the database.
    """
    end = datetime.now()
    start = end - timedelta(days=days)
    records = db_manager.get_usage_by_date_range(start, end)

    device_totals = defaultdict(float)
    for r in records:
        device_totals[r.device_type or "unknown"] += r.consumption_kwh

    devices = sorted(device_totals, key=device_totals.get, reverse=True)
    totals = [device_totals[d] for d in devices]

    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.barh(devices, totals, color=COLORS["primary"], edgecolor="white")
    _style_axes(ax, f"Total Consumption by Device (last {days} days)",
                "Total consumption (kWh)", "")
    ax.invert_yaxis()  # biggest at top
    # Label each bar with its value.
    for i, v in enumerate(totals):
        ax.text(v, i, f" {v:.0f} kWh", va="center", fontsize=9)
    fig.tight_layout()
    return fig


def solar_generation_figure(db_manager, days: int = 7):
    """
    Line chart of average solar generation by hour of day over the last N days,
    showing the solar production curve. Pulls from the database.
    """
    end = datetime.now()
    start = end - timedelta(days=days)
    records = db_manager.get_generation_by_date_range(start, end)

    hour_totals = defaultdict(float)
    hour_counts = defaultdict(int)
    for r in records:
        h = r.timestamp.hour
        hour_totals[h] += r.generation_kwh
        hour_counts[h] += 1

    hours = list(range(24))
    avg = [hour_totals[h] / hour_counts[h] if hour_counts[h] else 0 for h in hours]

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(hours, avg, color=COLORS["warn"], linewidth=2.2, marker="o",
            markersize=4)
    ax.fill_between(hours, avg, alpha=0.15, color=COLORS["warn"])
    _style_axes(ax, f"Average Solar Generation by Hour (last {days} days)",
                "Hour of day", "Avg generation (kWh)")
    ax.set_xticks(range(0, 24, 2))
    fig.tight_layout()
    return fig


def savings_comparison_figure(peak_cost: float, optimized_cost: float,
                              currency: str = "GBP",
                              label_a: str = "Charge at peak",
                              label_b: str = "Charge off-peak"):
    """
    Simple two-bar comparison of an un-optimised vs optimised cost, visualising
    the savings the agent recommends. Caller supplies the two numbers.
    """
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar([label_a, label_b], [peak_cost, optimized_cost],
                  color=[COLORS["warn"], COLORS["cheap"]], edgecolor="white",
                  width=0.5)
    _style_axes(ax, "Cost Comparison: Peak vs Optimised",
                "", f"Cost ({currency})")
    # Annotate bars and the saving.
    for b, val in zip(bars, [peak_cost, optimized_cost]):
        ax.text(b.get_x() + b.get_width() / 2, val,
                f"{currency} {val:.2f}", ha="center", va="bottom", fontsize=10,
                fontweight="bold")
    saving = peak_cost - optimized_cost
    if peak_cost > 0:
        pct = saving / peak_cost * 100
        ax.text(0.5, 0.92, f"Saves {currency} {saving:.2f} ({pct:.0f}%)",
                transform=ax.transAxes, ha="center", fontsize=11,
                color=COLORS["primary"], fontweight="bold")
    fig.tight_layout()
    return fig


def save_all_report_charts(db_manager, prices: dict, output_dir: str = "report_charts"):
    """
    Generate every chart and save as PNG for inclusion in the report.
    Returns a dict of {chart_name: filepath}. Run this once to produce the
    images for your results section.
    """
    os.makedirs(output_dir, exist_ok=True)
    saved = {}

    charts = {
        "price_curve": price_curve_figure(prices),
        "usage_by_hour": usage_by_hour_figure(db_manager),
        "device_breakdown": device_breakdown_figure(db_manager),
        "solar_generation": solar_generation_figure(db_manager),
    }
    for name, fig in charts.items():
        path = os.path.join(output_dir, f"{name}.png")
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        saved[name] = path

    return saved
