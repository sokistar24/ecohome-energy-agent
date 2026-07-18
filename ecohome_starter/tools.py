"""
Tools for EcoHome Energy Advisor Agent
"""
import os
import json
import glob
import random
import requests
from datetime import datetime, timedelta
from typing import Dict, Any
from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from models.energy import DatabaseManager


from dotenv import load_dotenv
load_dotenv()
# Initialize database manager
db_manager = DatabaseManager()

# ---------------------------------------------------------------------------
# Helpers for the weather tool: real API (Open-Meteo) with a mock fallback.
# ---------------------------------------------------------------------------

# Small lookup so common demo locations resolve without a geocoding call.
# Anything not listed falls through to Open-Meteo's free geocoding endpoint.
_KNOWN_LOCATIONS = {
    "san francisco": (37.7749, -122.4194),
    "san francisco, ca": (37.7749, -122.4194),
    "new york": (40.7128, -74.0060),
    "new york, ny": (40.7128, -74.0060),
    "london": (51.5074, -0.1278),
    "los angeles": (34.0522, -118.2437),
    "seattle": (47.6062, -122.3321),
    "austin": (30.2672, -97.7431),
}


def _geocode_location(location: str):
    """
    Turn a location name into (latitude, longitude).
    Checks a small built-in table first, then Open-Meteo's free geocoding API.
    Returns None if the location can't be resolved.
    """
    key = location.strip().lower()
    if key in _KNOWN_LOCATIONS:
        return _KNOWN_LOCATIONS[key]
    try:
        # Open-Meteo geocoding: no API key required.
        resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": location, "count": 1},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results")
        if results:
            return results[0]["latitude"], results[0]["longitude"]
    except Exception:
        # Network down, bad name, or rate-limited: signal failure to caller.
        return None
    return None


def _cloudcover_to_condition(cloud_pct: float) -> str:
    """Map a cloud-cover percentage to one of our condition labels."""
    if cloud_pct < 25:
        return "sunny"
    elif cloud_pct < 60:
        return "partly_cloudy"
    elif cloud_pct < 90:
        return "cloudy"
    else:
        return "rainy"


def _mock_weather_forecast(location: str, days: int) -> Dict[str, Any]:
    """
    Fallback weather generator used when the live API is unreachable.
    Produces plausible, internally-consistent data: solar irradiance follows a
    daylight bell curve peaking at noon, temperatures peak mid-afternoon.
    """
    conditions = ["sunny", "partly_cloudy", "cloudy", "rainy"]
    condition_solar_factor = {
        "sunny": 1.0, "partly_cloudy": 0.6, "cloudy": 0.3, "rainy": 0.1,
    }

    def irradiance_for(hour: int, condition: str) -> float:
        if hour < 6 or hour > 18:
            return 0.0
        daylight_strength = 1 - abs(hour - 12) / 6
        return round(900 * daylight_strength * condition_solar_factor[condition], 1)

    current_condition = random.choice(conditions[:3])
    current = {
        "temperature_c": round(random.uniform(15, 28), 1),
        "condition": current_condition,
        "humidity": random.randint(40, 80),
        "wind_speed": round(random.uniform(2, 18), 1),
    }

    hourly = []
    for hour in range(24):
        condition = random.choice(conditions)
        temp_curve = 1 - abs(hour - 15) / 15
        temperature_c = round(12 + 14 * temp_curve + random.uniform(-1.5, 1.5), 1)
        hourly.append({
            "hour": hour,
            "temperature_c": temperature_c,
            "condition": condition,
            "solar_irradiance": irradiance_for(hour, condition),
            "humidity": random.randint(35, 85),
            "wind_speed": round(random.uniform(1, 20), 1),
        })

    return {
        "location": location,
        "forecast_days": days,
        "data_source": "mock",  # so callers/graders can see fallback was used
        "current": current,
        "hourly": hourly,
    }


@tool
def get_weather_forecast(location: str = None, days: int = 3) -> Dict[str, Any]:
    """
    Get weather forecast for a specific location and number of days.

    Args:
        location (str): Location to get weather for (e.g., "London"). If omitted,
            the customer's selected region is used automatically, so you normally
            do NOT need to pass this — just call get_weather_forecast(days=...).
        days (int): Number of days to forecast (1-7)

    Returns:
        Dict[str, Any]: Weather forecast data including temperature, conditions, and solar irradiance
        E.g:
        forecast = {
            "location": ...,
            "forecast_days": ...,
            "current": {
                "temperature_c": ...,
                "condition": random.choice(["sunny", "partly_cloudy", "cloudy"]),
                "humidity": ...,
                "wind_speed": ...
            },
            "hourly": [
                {
                    "hour": ..., # for hour in range(24)
                    "temperature_c": ...,
                    "condition": ...,
                    "solar_irradiance": ...,
                    "humidity": ...,
                    "wind_speed": ...
                },
            ]
        }
    """
    # Default to the customer's selected region's representative city.
    if not location or not str(location).strip():
        location = get_region_city()

    # Clamp days to the documented 1-7 range.
    days = max(1, min(days, 7))

    # --- Try the real Open-Meteo API first ---------------------------------
    coords = _geocode_location(location)
    if coords is not None:
        lat, lon = coords
        try:
            resp = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    # shortwave_radiation IS solar irradiance in W/m^2.
                    "hourly": "temperature_2m,relativehumidity_2m,"
                              "windspeed_10m,cloudcover,shortwave_radiation",
                    "forecast_days": days,
                    "timezone": "auto",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            h = data["hourly"]

            # Build the 24-hour view for the first forecast day.
            hourly = []
            for i in range(min(24, len(h["time"]))):
                cloud = h["cloudcover"][i]
                # Open-Meteo timestamps look like "2026-06-28T13:00"; take the hour.
                hour_of_day = int(h["time"][i][11:13])
                hourly.append({
                    "hour": hour_of_day,
                    "temperature_c": h["temperature_2m"][i],
                    "condition": _cloudcover_to_condition(cloud),
                    "solar_irradiance": h["shortwave_radiation"][i],
                    "humidity": h["relativehumidity_2m"][i],
                    "wind_speed": h["windspeed_10m"][i],
                })

            # Derive a "current" snapshot from the first available hour.
            first = hourly[0] if hourly else {}
            current = {
                "temperature_c": first.get("temperature_c"),
                "condition": first.get("condition"),
                "humidity": first.get("humidity"),
                "wind_speed": first.get("wind_speed"),
            }

            return {
                "location": location,
                "forecast_days": days,
                "data_source": "open-meteo",  # real data succeeded
                "current": current,
                "hourly": hourly,
            }
        except Exception:
            # Any failure (network, schema change, timeout) -> fall back to mock.
            pass

    # --- Fallback: realistic mock ------------------------------------------
    return _mock_weather_forecast(location, days)

# TODO: Implement get_electricity_prices tool
@tool
def get_electricity_prices(date: str = None) -> Dict[str, Any]:
    """
    Get electricity prices for a specific date or current day.
    
    Args:
        date (str): Date in YYYY-MM-DD format (defaults to today)
    
    Returns:
        Dict[str, Any]: Electricity pricing data with hourly rates 
        E.g: 
        prices = {
            "date": ...,
            "pricing_type": "time_of_use",
            "currency": "USD",
            "unit": "per_kWh",
            "hourly_rates": [
                {
                    "hour": .., # for hour in range(24)
                    "rate": ..,
                    "period": ..,
                    "demand_charge": ...
                }
            ]
        }
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # --- Try the real Octopus Agile API first ------------------------------
    # Agile gives genuine half-hourly UK consumer prices, no API key needed.
    agile_result = _fetch_agile_prices(date)
    if agile_result is not None:
        return agile_result

    # --- Fallback: realistic time-of-use mock ------------------------------
    return _mock_electricity_prices(date)


# ---------------------------------------------------------------------------
# Helpers for the pricing tool: real Octopus Agile API + mock fallback.
# ---------------------------------------------------------------------------

# Current Agile product. Public endpoints, no authentication needed.
_AGILE_PRODUCT = "AGILE-FLEX-22-11-25"

# The 14 UK GSP / DNO regions (A-P, the letter I is skipped). Each maps to a
# human label for the dropdown and a representative city used for the weather /
# solar forecast, since the weather tool geocodes by place name. Prices are
# exact per region; weather is representative for the region.
UK_REGIONS = {
    "A": {"label": "East England",                 "city": "Ipswich"},
    "B": {"label": "East Midlands",                "city": "Nottingham"},
    "C": {"label": "London",                       "city": "London"},
    "D": {"label": "North Wales & Merseyside",     "city": "Liverpool"},
    "E": {"label": "West Midlands",                "city": "Birmingham"},
    "F": {"label": "North East England",           "city": "Newcastle upon Tyne"},
    "G": {"label": "North West England",           "city": "Manchester"},
    "H": {"label": "Southern England",             "city": "Southampton"},
    "J": {"label": "South East England",           "city": "Maidstone"},
    "K": {"label": "South Wales",                  "city": "Cardiff"},
    "L": {"label": "South West England",           "city": "Bristol"},
    "M": {"label": "Yorkshire",                    "city": "Leeds"},
    "N": {"label": "Southern Scotland",            "city": "Glasgow"},
    "P": {"label": "Northern Scotland",            "city": "Inverness"},
}

# Default region if none is selected: London (C), matching the previous behaviour.
_DEFAULT_REGION = "C"

# Request-scoped active region. The API sets this per request from the user's
# dropdown choice; the pricing/weather tools read it. It is deliberately NOT a
# model-supplied tool argument — the region is a user setting, not something the
# LLM should reason about or pass around.
_active_region = _DEFAULT_REGION


def set_active_region(region: str) -> str:
    """
    Set the region used by the pricing and weather tools for the current request.
    Falls back to the default (London/C) if the code isn't a valid GSP region.
    Returns the region actually applied.
    """
    global _active_region
    region = (region or "").strip().upper()
    _active_region = region if region in UK_REGIONS else _DEFAULT_REGION
    return _active_region


def get_active_region() -> str:
    """Return the region code currently in effect for pricing/weather."""
    return _active_region


def get_region_city(region: str = None) -> str:
    """Representative city name for the given (or active) region, for weather."""
    code = (region or _active_region)
    return UK_REGIONS.get(code, UK_REGIONS[_DEFAULT_REGION])["city"]


def _classify_period_by_rate(rate: float, low: float, high: float) -> str:
    """
    Agile has no built-in peak labels (every half-hour is individually priced),
    so we synthesize one from where a rate falls in the day's price range.
    Bottom third = off_peak, middle = mid_peak, top third = on_peak.
    """
    span = high - low
    if span <= 0:
        return "mid_peak"
    position = (rate - low) / span
    if position < 0.33:
        return "off_peak"
    elif position < 0.66:
        return "mid_peak"
    else:
        return "on_peak"


def _fetch_agile_prices(date: str):
    """
    Fetch real half-hourly Agile prices for the given date and collapse them
    into 24 hourly slots matching our docstring contract.
    Returns a prices dict on success, or None on any failure (caller falls back).
    Uses the request's active region (set via set_active_region).
    """
    try:
        region = get_active_region()
        tariff = f"E-1R-{_AGILE_PRODUCT}-{region}"

        # Build a UTC day window [date 00:00, next day 00:00).
        day = datetime.strptime(date, "%Y-%m-%d")
        period_from = day.strftime("%Y-%m-%dT00:00:00Z")
        period_to = (day + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")

        url = (f"https://api.octopus.energy/v1/products/{_AGILE_PRODUCT}"
               f"/electricity-tariffs/{tariff}/standard-unit-rates/")
        resp = requests.get(
            url,
            params={"period_from": period_from, "period_to": period_to,
                    "page_size": 100},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None  # No data for that date (e.g. too far future) -> fallback

        # Each result is a half-hour slot with value_inc_vat in pence/kWh.
        # Group the (up to) 48 half-hours into 24 hourly buckets by averaging.
        hourly_pence = {}  # hour -> list of half-hour prices
        for r in results:
            hour = int(r["valid_from"][11:13])  # "...T13:30:00Z" -> 13
            hourly_pence.setdefault(hour, []).append(r["value_inc_vat"])

        # Convert pence to pounds and average each hour's half-hour slots.
        hourly_pounds = {
            h: round(sum(vals) / len(vals) / 100.0, 4)
            for h, vals in hourly_pence.items()
        }

        # Determine the day's price range to synthesize peak/off-peak labels.
        rates = list(hourly_pounds.values())
        low, high = min(rates), max(rates)

        hourly_rates = []
        for hour in range(24):
            if hour not in hourly_pounds:
                continue  # skip hours with no data rather than fabricate
            rate = hourly_pounds[hour]
            period = _classify_period_by_rate(rate, low, high)
            hourly_rates.append({
                "hour": hour,
                "rate": rate,
                "period": period,
                # Agile has no separate demand charge; it's all in the unit rate.
                "demand_charge": 0.0,
            })

        return {
            "date": date,
            "pricing_type": "agile_half_hourly",
            "currency": "GBP",          # Agile prices are in pounds, not USD
            "unit": "per_kWh",
            "data_source": "octopus-agile",
            "region": get_active_region(),
            "region_label": UK_REGIONS.get(get_active_region(), {}).get("label"),
            "hourly_rates": hourly_rates,
        }
    except Exception:
        # Network down, schema change, bad date, etc. -> signal fallback.
        return None


def _mock_electricity_prices(date: str) -> Dict[str, Any]:
    """
    Fallback time-of-use pricing used when the Agile API is unreachable.
    Models the real-world shape: cheap overnight, pricey evening peak.
    """
    base_rate = 0.12  # baseline GBP/kWh, comparable to Agile averages

    def classify_period(hour: int) -> str:
        if 16 <= hour <= 21:
            return "on_peak"
        elif 6 <= hour < 16 or 21 < hour <= 22:
            return "mid_peak"
        else:
            return "off_peak"

    period_multiplier = {"on_peak": 1.8, "mid_peak": 1.2, "off_peak": 0.7}
    period_demand_charge = {"on_peak": 5.0, "mid_peak": 2.0, "off_peak": 0.0}

    hourly_rates = []
    for hour in range(24):
        period = classify_period(hour)
        rate = base_rate * period_multiplier[period] * random.uniform(0.95, 1.05)
        hourly_rates.append({
            "hour": hour,
            "rate": round(rate, 4),
            "period": period,
            "demand_charge": period_demand_charge[period],
        })

    return {
        "date": date,
        "pricing_type": "time_of_use",
        "currency": "GBP",
        "unit": "per_kWh",
        "data_source": "mock",
        "hourly_rates": hourly_rates,
    }

@tool
def query_energy_usage(start_date: str, end_date: str, device_type: str = None) -> Dict[str, Any]:
    """
    Query energy usage data from the database for a specific date range.
    
    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        device_type (str): Optional device type filter (e.g., "EV", "HVAC", "appliance")
    
    Returns:
        Dict[str, Any]: Energy usage data with consumption details
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        
        records = db_manager.get_usage_by_date_range(start_dt, end_dt)
        
        if device_type:
            records = [r for r in records if r.device_type == device_type]
        
        usage_data = {
            "start_date": start_date,
            "end_date": end_date,
            "device_type": device_type,
            "total_records": len(records),
            "total_consumption_kwh": round(sum(r.consumption_kwh for r in records), 2),
            "total_cost_usd": round(sum(r.cost_usd or 0 for r in records), 2),
            "records": []
        }
        
        for record in records:
            usage_data["records"].append({
                "timestamp": record.timestamp.isoformat(),
                "consumption_kwh": record.consumption_kwh,
                "device_type": record.device_type,
                "device_name": record.device_name,
                "cost_usd": record.cost_usd
            })
        
        return usage_data
    except Exception as e:
        return {"error": f"Failed to query energy usage: {str(e)}"}

@tool
def query_solar_generation(start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Query solar generation data from the database for a specific date range.
    
    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
    
    Returns:
        Dict[str, Any]: Solar generation data with production details
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        
        records = db_manager.get_generation_by_date_range(start_dt, end_dt)
        
        generation_data = {
            "start_date": start_date,
            "end_date": end_date,
            "total_records": len(records),
            "total_generation_kwh": round(sum(r.generation_kwh for r in records), 2),
            "average_daily_generation": round(sum(r.generation_kwh for r in records) / max(1, (end_dt - start_dt).days), 2),
            "records": []
        }
        
        for record in records:
            generation_data["records"].append({
                "timestamp": record.timestamp.isoformat(),
                "generation_kwh": record.generation_kwh,
                "weather_condition": record.weather_condition,
                "temperature_c": record.temperature_c,
                "solar_irradiance": record.solar_irradiance
            })
        
        return generation_data
    except Exception as e:
        return {"error": f"Failed to query solar generation: {str(e)}"}

@tool
def get_recent_energy_summary(hours: int = 24) -> Dict[str, Any]:
    """
    Get a summary of recent energy usage and solar generation.
    
    Args:
        hours (int): Number of hours to look back (default 24)
    
    Returns:
        Dict[str, Any]: Summary of recent energy data
    """
    try:
        usage_records = db_manager.get_recent_usage(hours)
        generation_records = db_manager.get_recent_generation(hours)
        
        summary = {
            "time_period_hours": hours,
            "usage": {
                "total_consumption_kwh": round(sum(r.consumption_kwh for r in usage_records), 2),
                "total_cost_usd": round(sum(r.cost_usd or 0 for r in usage_records), 2),
                "device_breakdown": {}
            },
            "generation": {
                "total_generation_kwh": round(sum(r.generation_kwh for r in generation_records), 2),
                "average_weather": "sunny" if generation_records else "unknown"
            }
        }
        
        # Calculate device breakdown
        for record in usage_records:
            device = record.device_type or "unknown"
            if device not in summary["usage"]["device_breakdown"]:
                summary["usage"]["device_breakdown"][device] = {
                    "consumption_kwh": 0,
                    "cost_usd": 0,
                    "records": 0
                }
            summary["usage"]["device_breakdown"][device]["consumption_kwh"] += record.consumption_kwh
            summary["usage"]["device_breakdown"][device]["cost_usd"] += record.cost_usd or 0
            summary["usage"]["device_breakdown"][device]["records"] += 1
        
        # Round the breakdown values
        for device_data in summary["usage"]["device_breakdown"].values():
            device_data["consumption_kwh"] = round(device_data["consumption_kwh"], 2)
            device_data["cost_usd"] = round(device_data["cost_usd"], 2)
        
        return summary
    except Exception as e:
        return {"error": f"Failed to get recent energy summary: {str(e)}"}

@tool
def search_energy_tips(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search for energy-saving tips and best practices using RAG.
    
    Args:
        query (str): Search query for energy tips
        max_results (int): Maximum number of results to return
    
    Returns:
        Dict[str, Any]: Relevant energy tips and best practices
    """
    try:
        # Initialize vector store if it doesn't exist
        persist_directory = "data/vectorstore"
        if not os.path.exists(persist_directory):
            os.makedirs(persist_directory)
        
        # Load documents if vector store doesn't exist
        if not os.path.exists(os.path.join(persist_directory, "chroma.sqlite3")):
            # Load EVERY .txt document in the documents folder, so any new
            # knowledge-base file dropped in gets indexed automatically (no need
            # to edit this list when adding documents).
            documents = []
            for doc_path in sorted(glob.glob("data/documents/*.txt")):
                if os.path.exists(doc_path):
                    loader = TextLoader(doc_path)
                    docs = loader.load()
                    documents.extend(docs)
            
            # Split documents
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            splits = text_splitter.split_documents(documents)
            
            # Create vector store
            # Embeddings use your personal OpenAI key (OPENAI_API_KEY from .env)
            embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
            vectorstore = Chroma.from_documents(
                documents=splits,
                embedding=embeddings,
                persist_directory=persist_directory
            )
        else:
            # Load existing vector store
            # Embeddings use your personal OpenAI key (OPENAI_API_KEY from .env)
            embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
            vectorstore = Chroma(
                persist_directory=persist_directory,
                embedding_function=embeddings
            )
        
        # Search for relevant documents
        docs = vectorstore.similarity_search(query, k=max_results)
        
        results = {
            "query": query,
            "total_results": len(docs),
            "tips": []
        }
        
        for i, doc in enumerate(docs):
            results["tips"].append({
                "rank": i + 1,
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "relevance_score": "high" if i < 2 else "medium" if i < 4 else "low"
            })
        
        return results
    except Exception as e:
        return {"error": f"Failed to search energy tips: {str(e)}"}

@tool
def calculate_energy_savings(device_type: str, current_usage_kwh: float, 
                           optimized_usage_kwh: float, price_per_kwh: float = 0.12) -> Dict[str, Any]:
    """
    Calculate potential energy savings from optimization.
    
    Args:
        device_type (str): Type of device being optimized
        current_usage_kwh (float): Current energy usage in kWh
        optimized_usage_kwh (float): Optimized energy usage in kWh
        price_per_kwh (float): Price per kWh (default 0.12)
    
    Returns:
        Dict[str, Any]: Savings calculation results
    """
    savings_kwh = current_usage_kwh - optimized_usage_kwh
    savings_usd = savings_kwh * price_per_kwh
    savings_percentage = (savings_kwh / current_usage_kwh) * 100 if current_usage_kwh > 0 else 0
    
    return {
        "device_type": device_type,
        "current_usage_kwh": current_usage_kwh,
        "optimized_usage_kwh": optimized_usage_kwh,
        "savings_kwh": round(savings_kwh, 2),
        "savings_usd": round(savings_usd, 2),
        "savings_percentage": round(savings_percentage, 1),
        "price_per_kwh": price_per_kwh,
        "annual_savings_usd": round(savings_usd * 365, 2)
    }


TOOL_KIT = [
    get_weather_forecast,
    get_electricity_prices,
    query_energy_usage,
    query_solar_generation,
    get_recent_energy_summary,
    search_energy_tips,
    calculate_energy_savings
]
