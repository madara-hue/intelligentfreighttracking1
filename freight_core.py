"""
freight_core.py

Data sources, calculations and the plain-English summary for the
Intelligent Freight Forecasting app.

Nothing in this file imports Streamlit, so every function can be tested
on its own. The formulas for distance, voyage cost, weather risk and the
freight forecast are unchanged from the original web_app.py.
"""

from datetime import datetime, timezone
from math import radians, sin, cos, sqrt, atan2

import pandas as pd
import requests


# ============================================================
# STORED PORT DATA
# ============================================================

PORTS = {
    "Chennai": {"country": "India", "latitude": 13.0827, "longitude": 80.2707},
    "Kamarajar": {"country": "India", "latitude": 13.2475, "longitude": 80.3440},
    "Mumbai": {"country": "India", "latitude": 19.0760, "longitude": 72.8777},
    "Kandla": {"country": "India", "latitude": 23.0333, "longitude": 70.2167},
    "Singapore": {"country": "Singapore", "latitude": 1.2903, "longitude": 103.8519},
    "Colombo": {"country": "Sri Lanka", "latitude": 6.9271, "longitude": 79.8612},
    "Dubai": {"country": "UAE", "latitude": 25.2048, "longitude": 55.2708},
    "Rotterdam": {"country": "Netherlands", "latitude": 51.9244, "longitude": 4.4777},
    "Shanghai": {"country": "China", "latitude": 31.2304, "longitude": 121.4737},
}

# How each port is searched for in the IMF PortWatch dataset. The names are
# tried in order and the first one that returns data is used. If a port is
# not found, the app falls back to the reference value and says so.
PORTWATCH_LOOKUP = {
    "Chennai": {"iso3": "IND", "names": ["Chennai"]},
    "Kamarajar": {"iso3": "IND", "names": ["Kamarajar", "Ennore"]},
    "Mumbai": {"iso3": "IND", "names": ["Mumbai"]},
    "Kandla": {"iso3": "IND", "names": ["Kandla", "Deendayal"]},
    "Singapore": {"iso3": "SGP", "names": ["Singapore"]},
    "Colombo": {"iso3": "LKA", "names": ["Colombo"]},
    "Dubai": {"iso3": "ARE", "names": ["Dubai", "Jebel Ali"]},
    "Rotterdam": {"iso3": "NLD", "names": ["Rotterdam"]},
    "Shanghai": {"iso3": "CHN", "names": ["Shanghai"]},
}

PORTWATCH_URL = (
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services/"
    "Daily_Ports_Data/FeatureServer/0/query"
)


# ============================================================
# REFERENCE DATA (used when live data is unavailable)
# ============================================================

REFERENCE_FREIGHT_RATES = {
    "Container": 85,
    "Dry Bulk": 32,
    "Liquid Bulk": 45,
    "Crude Oil": 52,
    "Petroleum Products": 58,
    "LNG": 75,
    "LPG": 68,
    "Coal": 30,
    "Iron Ore": 28,
    "Grain": 34,
    "Automobile": 90,
    "General Cargo": 55,
}

REFERENCE_CONGESTION = {
    "Chennai": 62,
    "Kamarajar": 58,
    "Mumbai": 48,
    "Kandla": 35,
    "Singapore": 71,
    "Colombo": 55,
    "Dubai": 43,
    "Rotterdam": 67,
    "Shanghai": 76,
}

LEVEL_ORDER = ["Low", "Moderate", "High", "Severe"]

RATING_TEXT = {
    "Low": "Smooth sailing",
    "Moderate": "Manageable",
    "High": "Elevated risk",
    "Severe": "High risk",
}


# ============================================================
# SMALL HELPERS
# ============================================================

def describe_error(error):
    """Short, readable reason for a failed request."""
    if isinstance(error, requests.exceptions.Timeout):
        return "the request timed out"
    if isinstance(error, requests.exceptions.ConnectionError):
        return "could not connect to the service"
    if isinstance(error, requests.exceptions.HTTPError):
        return f"the service returned an error ({error})"
    return str(error) or error.__class__.__name__


def congestion_level(score):
    if score < 40:
        return "Low"
    if score < 65:
        return "Moderate"
    if score < 80:
        return "High"
    return "Severe"


def weather_level(score):
    if score < 30:
        return "Low"
    if score < 60:
        return "Moderate"
    if score < 80:
        return "High"
    return "Severe"


def estimate_waiting_hours(score):
    """Original model: 2 hours at zero congestion up to 48 hours at 100."""
    return 2 + (score / 100) * 46


# ============================================================
# WEATHER (Open-Meteo, free, no key)
# ============================================================

def fetch_weather(latitude, longitude):
    """Current weather at a port. Raises on failure."""
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,relative_humidity_2m,wind_speed_10m,"
                "wind_direction_10m,wind_gusts_10m,precipitation,weather_code"
            ),
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
            "timezone": "auto",
        },
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()

    if "current" not in data:
        raise ValueError("Weather API returned no current weather data.")

    current = data["current"]
    return {
        "temperature": current.get("temperature_2m"),
        "humidity": current.get("relative_humidity_2m"),
        "wind_speed": current.get("wind_speed_10m"),
        "wind_direction": current.get("wind_direction_10m"),
        "wind_gusts": current.get("wind_gusts_10m"),
        "precipitation": current.get("precipitation"),
        "weather_code": current.get("weather_code"),
        "time": current.get("time"),
    }


def weather_description(code):
    weather_codes = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Light rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Light snow", 73: "Moderate snow", 75: "Heavy snow",
        80: "Light rain showers", 81: "Moderate rain showers",
        82: "Heavy rain showers",
        95: "Thunderstorm", 96: "Thunderstorm with hail",
        99: "Thunderstorm with heavy hail",
    }
    return weather_codes.get(code, "Unknown")


def calculate_weather_risk(weather):
    """Unchanged from the original app."""
    if not weather or "error" in weather:
        return "Unavailable", 0

    wind_speed = weather.get("wind_speed")
    precipitation = weather.get("precipitation")
    weather_code = weather.get("weather_code")

    if wind_speed is None:
        return "Unavailable", 0

    if wind_speed < 15:
        wind_score = 10
    elif wind_speed < 30:
        wind_score = 30
    elif wind_speed < 45:
        wind_score = 60
    else:
        wind_score = 90

    weather_score = 0
    if precipitation is not None:
        if precipitation > 10:
            weather_score = 30
        elif precipitation > 5:
            weather_score = 20
        elif precipitation > 1:
            weather_score = 10

    if weather_code in [95, 96, 99]:
        weather_score = max(weather_score, 70)

    final_score = max(wind_score, weather_score)
    return weather_level(final_score), final_score


# ============================================================
# PORT CONGESTION
# ============================================================

def _query_portwatch(name, iso3):
    """Most recent daily port-call rows for ports matching a name."""
    safe_name = name.replace("'", "''")

    def ask(order):
        response = requests.get(
            PORTWATCH_URL,
            params={
                "where": f"portname LIKE '%{safe_name}%' AND ISO3 = '{iso3}'",
                "outFields": "date,portid,portname,portcalls",
                "orderByFields": order,
                "resultRecordCount": 500,
                "returnGeometry": "false",
                "f": "json",
            },
            timeout=25,
        )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", "PortWatch query error"))
        return [feature["attributes"] for feature in data.get("features", [])]

    try:
        return ask("date DESC")
    except RuntimeError:
        # Some ArcGIS services reject sorting on the date field. The rows are
        # stored oldest to newest, so sorting by row id gives the latest ones.
        return ask("ObjectId DESC")


def summarise_port_activity(rows):
    """
    Turn daily port-call rows into a congestion score.

    Method: compare the last 7 days of ship calls with the port's own
    average over the 90 days before that. Normal traffic scores 35.
    Every 10% above normal adds 15 points, every 10% below removes 15.
    This measures how busy the port is versus its usual level, which is
    a proxy for congestion, not a direct measure of waiting time.
    """
    if not rows:
        return None

    df = pd.DataFrame(rows)
    if not {"date", "portid", "portcalls"} <= set(df.columns):
        return None

    df = df.dropna(subset=["date", "portcalls"])
    if df.empty:
        return None

    busiest = df.groupby("portid")["portcalls"].sum().idxmax()
    df = df[df["portid"] == busiest].copy()
    port_name = str(df["portname"].iloc[0]) if "portname" in df else str(busiest)

    df["date"] = pd.to_datetime(df["date"], unit="ms")
    df = df.sort_values("date").drop_duplicates("date")
    calls = df.set_index("date")["portcalls"].astype(float)

    if len(calls) < 30:
        return None

    recent = calls.iloc[-7:].mean()
    baseline = calls.iloc[-97:-7].mean()
    if pd.isna(baseline) or baseline <= 0:
        return None

    ratio = recent / baseline
    score = int(round(min(100, max(0, 35 + (ratio - 1) * 150))))

    history = pd.DataFrame(
        {
            "Daily ship calls": calls,
            "7-day average": calls.rolling(7).mean(),
        }
    ).iloc[-90:]

    return {
        "port_name": port_name,
        "as_of": calls.index.max().date().isoformat(),
        "recent_avg": float(recent),
        "baseline_avg": float(baseline),
        "change_pct": float((ratio - 1) * 100),
        "score": score,
        "history": history,
    }


def fetch_port_activity(port):
    """Live port activity from IMF PortWatch. Raises on network failure,
    returns None if the port is not found in the dataset."""
    lookup = PORTWATCH_LOOKUP.get(port)
    if not lookup:
        return None

    for name in lookup["names"]:
        summary = summarise_port_activity(_query_portwatch(name, lookup["iso3"]))
        if summary:
            return summary
    return None


def congestion_status_live(port, activity):
    score = activity["score"]
    detail = (
        f"Last 7 days: {activity['recent_avg']:.1f} ship calls a day, "
        f"against {activity['baseline_avg']:.1f} on a normal day "
        f"({activity['change_pct']:+.0f}%)."
    )
    age_days = (datetime.now(timezone.utc).date()
                - datetime.fromisoformat(activity["as_of"]).date()).days
    if age_days > 14:
        detail += f" This data is {age_days} days old."
    return {
        "port": port,
        "score": score,
        "level": congestion_level(score),
        "waiting_hours": estimate_waiting_hours(score),
        "source": "live",
        "source_label": "IMF PortWatch (satellite ship tracking)",
        "as_of": activity["as_of"],
        "detail": detail,
        "history": activity["history"],
        "note": "",
    }


def congestion_status_reference(port, note=""):
    score = REFERENCE_CONGESTION.get(port, 50)
    return {
        "port": port,
        "score": score,
        "level": congestion_level(score),
        "waiting_hours": estimate_waiting_hours(score),
        "source": "reference",
        "source_label": "Stored reference estimate",
        "as_of": None,
        "detail": "",
        "history": None,
        "note": note,
    }


# ============================================================
# FREIGHT RATE
# ============================================================

def fetch_api_freight_rate(url, api_key, cargo, origin, destination):
    """
    Live freight rate from a provider you have an account with.

    This is a template. Providers differ in URL, parameters and response
    layout, so edit the three marked lines to match yours. It must return
    a dict with the rate in US dollars per tonne. Raises on failure.
    """
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {api_key}"},          # <- auth style
        params={"cargo": cargo, "origin": origin,                # <- request
                "destination": destination, "unit": "tonne"},
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()

    rate = data.get("rate_usd_per_tonne")                        # <- response field
    if rate is None:
        raise ValueError("The freight API response had no rate field.")

    return {
        "rate": float(rate),
        "as_of": data.get("as_of"),
        "source": data.get("source", "Freight rate API"),
    }


def resolve_freight_rate(cargo, manual_rate=None, api_result=None, api_note=""):
    """Pick the best available base rate: manual quote, then API, then table."""
    if manual_rate and manual_rate > 0:
        return {
            "base_rate": float(manual_rate),
            "source": "manual",
            "source_label": "Live quote entered by you",
            "as_of": datetime.now(timezone.utc).date().isoformat(),
            "note": "",
        }

    if api_result:
        return {
            "base_rate": api_result["rate"],
            "source": "live",
            "source_label": api_result.get("source", "Freight rate API"),
            "as_of": api_result.get("as_of"),
            "note": "",
        }

    return {
        "base_rate": float(REFERENCE_FREIGHT_RATES.get(cargo, 50)),
        "source": "reference",
        "source_label": "Stored reference rate (not a live market quote)",
        "as_of": None,
        "note": api_note,
    }


# ============================================================
# DISTANCE, VOYAGE COST, FREIGHT FORECAST (unchanged formulas)
# ============================================================

def calculate_distance(origin, destination):
    """Great-circle distance in nautical miles."""
    lat1 = radians(PORTS[origin]["latitude"])
    lon1 = radians(PORTS[origin]["longitude"])
    lat2 = radians(PORTS[destination]["latitude"])
    lon2 = radians(PORTS[destination]["longitude"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    distance_km = 6371 * c
    return distance_km * 0.539957


def calculate_voyage_cost(distance_nm, vessel_speed, daily_cost, port_days):
    if vessel_speed <= 0:
        return None

    sailing_days = distance_nm / (vessel_speed * 24)
    total_days = sailing_days + port_days
    total_cost = total_days * daily_cost

    return {
        "sailing_days": sailing_days,
        "total_days": total_days,
        "total_cost": total_cost,
    }


def forecast_freight_rate(base_rate, congestion_score, weather_risk_score):
    congestion_effect = (congestion_score / 100) * 0.15
    weather_effect = (weather_risk_score / 100) * 0.10
    return base_rate * (1 + congestion_effect + weather_effect)


# ============================================================
# FULL VOYAGE CALCULATION
# ============================================================

def compute_voyage(inputs, origin_congestion, destination_congestion,
                   origin_weather, destination_weather, freight):
    """Combine all the pieces into one result dictionary."""
    origin = inputs["origin"]
    destination = inputs["destination"]

    distance_nm = calculate_distance(origin, destination)

    o_level, o_score = calculate_weather_risk(origin_weather)
    d_level, d_score = calculate_weather_risk(destination_weather)
    weather_available = not (o_level == "Unavailable" and d_level == "Unavailable")
    overall_score = max(o_score, d_score)
    overall_level = (
        weather_level(overall_score) if weather_available else "Unavailable"
    )

    waiting_hours = (
        origin_congestion["waiting_hours"] + destination_congestion["waiting_hours"]
    )
    waiting_days = waiting_hours / 24
    port_days_total = inputs["port_days"] + waiting_days

    voyage = calculate_voyage_cost(
        distance_nm, inputs["vessel_speed"], inputs["daily_cost"], port_days_total
    )
    if voyage is None:
        raise ValueError("Vessel speed must be greater than zero.")

    worst_congestion = max(origin_congestion["score"], destination_congestion["score"])
    base_rate = freight["base_rate"]
    forecast_rate = forecast_freight_rate(base_rate, worst_congestion, overall_score)
    freight_cost = forecast_rate * inputs["cargo_quantity"]

    return {
        "inputs": dict(inputs),
        "generated_at": datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
        "distance_nm": distance_nm,
        "voyage": voyage,
        "origin": {
            "port": origin,
            "congestion": origin_congestion,
            "weather": origin_weather,
            "weather_level": o_level,
            "weather_score": o_score,
        },
        "destination": {
            "port": destination,
            "congestion": destination_congestion,
            "weather": destination_weather,
            "weather_level": d_level,
            "weather_score": d_score,
        },
        "weather": {
            "overall_level": overall_level,
            "overall_score": overall_score,
            "available": weather_available,
        },
        "waiting": {"hours": waiting_hours, "days": waiting_days},
        "port_days_total": port_days_total,
        "freight": {
            "status": freight,
            "base_rate": base_rate,
            "forecast_rate": forecast_rate,
            "congestion_pct": (worst_congestion / 100) * 15,
            "weather_pct": (overall_score / 100) * 10,
            "uplift_pct": (forecast_rate / base_rate - 1) * 100 if base_rate else 0.0,
            "cost": freight_cost,
        },
        "total_cost": voyage["total_cost"] + freight_cost,
    }


# ============================================================
# PLAIN-ENGLISH SUMMARY
# ============================================================

def build_summary(r):
    """Short, readable summary of a voyage result."""
    inp = r["inputs"]
    o, d = r["origin"], r["destination"]
    voyage, freight = r["voyage"], r["freight"]

    levels = [o["congestion"]["level"], d["congestion"]["level"]]
    if r["weather"]["available"]:
        levels.append(r["weather"]["overall_level"])
    worst = max(levels, key=LEVEL_ORDER.index)
    rating = RATING_TEXT[worst]

    headline = (
        f"{o['port']} to {d['port']}: {rating.lower()}. "
        f"Allow roughly {voyage['total_days']:.1f} days in total and an "
        f"estimated cost of ${r['total_cost']:,.0f}."
    )

    bullets = []

    bullets.append(
        f"The route is about {r['distance_nm']:,.0f} nautical miles. At "
        f"{inp['vessel_speed']:.1f} knots that is {voyage['sailing_days']:.1f} "
        f"days at sea and {r['port_days_total']:.1f} days in port."
    )

    oc, dc = o["congestion"], d["congestion"]
    bullets.append(
        f"Port congestion is {oc['level'].lower()} at {o['port']} "
        f"(about {oc['waiting_hours']:.0f} hours of waiting) and "
        f"{dc['level'].lower()} at {d['port']} "
        f"(about {dc['waiting_hours']:.0f} hours), adding "
        f"{r['waiting']['days']:.1f} days of waiting in total."
    )

    if r["weather"]["available"]:
        bullets.append(
            f"Weather risk is {r['weather']['overall_level'].lower()}: "
            f"{o['weather_level'].lower()} at {o['port']} and "
            f"{d['weather_level'].lower()} at {d['port']}."
        )
    else:
        bullets.append(
            "Live weather could not be retrieved, so weather is left out of "
            "the risk rating and the freight forecast."
        )

    if abs(freight["uplift_pct"]) < 0.05:
        change = "in line with"
    else:
        change = f"{freight['uplift_pct']:+.1f}% against"
    bullets.append(
        f"The forecast freight rate is ${freight['forecast_rate']:,.2f} per "
        f"tonne, {change} the ${freight['base_rate']:,.2f} base rate. "
        f"Congestion adds {freight['congestion_pct']:.1f}% and weather adds "
        f"{freight['weather_pct']:.1f}%."
    )

    total = r["total_cost"] or 1
    bullets.append(
        f"Freight is ${freight['cost']:,.0f} ({freight['cost'] / total * 100:.0f}% "
        f"of the total) and vessel running cost is ${voyage['total_cost']:,.0f} "
        f"({voyage['total_cost'] / total * 100:.0f}%)."
    )

    watch = []
    if "High" in (oc["level"], dc["level"]) or "Severe" in (oc["level"], dc["level"]):
        watch.append(
            "Build extra waiting time into the schedule. Each extra day in "
            f"port costs about ${inp['daily_cost']:,.0f} in vessel running cost."
        )
    if r["weather"]["overall_level"] in ("High", "Severe"):
        watch.append(
            "Check the forecast again close to departure, as heavy weather "
            "can cause delays or a change of route."
        )
    if freight["status"]["source"] == "reference":
        watch.append(
            "The freight rate is a stored reference figure, not a live market "
            "quote. Enter a current quote for a closer estimate."
        )
    fallback_ports = [
        p["port"] for p in (o, d) if p["congestion"]["source"] == "reference"
    ]
    if fallback_ports:
        watch.append(
            "Live congestion data was not used for "
            + " and ".join(fallback_ports)
            + ", so a stored reference value was used instead."
        )
    if not watch:
        watch.append("No major warning signs in the data available.")

    return {
        "rating": rating,
        "level": worst,
        "headline": headline,
        "bullets": bullets,
        "watch": watch,
    }


# ============================================================
# PLAIN-TEXT REPORT
# ============================================================

def build_text_report(r):
    inp = r["inputs"]
    o, d = r["origin"], r["destination"]
    s = r["summary"]
    voyage, freight = r["voyage"], r["freight"]
    lines = [
        "VOYAGE ANALYSIS REPORT",
        "Intelligent Freight Forecasting & Vessel Chartering System",
        f"Generated: {r['generated_at']}",
        "=" * 60,
        "",
        "SUMMARY",
        "-" * 60,
        f"Outlook: {s['rating']}",
        s["headline"],
        "",
    ]
    lines += [f"- {b}" for b in s["bullets"]]
    lines += ["", "What to watch:"] + [f"- {w}" for w in s["watch"]]
    lines += [
        "",
        "VOYAGE DETAILS",
        "-" * 60,
        f"Vessel: {inp['vessel_name']} ({inp['vessel_type']})",
        f"Cargo: {inp['cargo']}, {inp['cargo_quantity']:,.0f} MT",
        f"Route: {o['port']} to {d['port']}",
        f"Distance: {r['distance_nm']:,.0f} NM at {inp['vessel_speed']:.1f} knots",
        f"Sailing days: {voyage['sailing_days']:.2f}",
        f"Total port days: {r['port_days_total']:.2f}",
        "",
        "PORT CONGESTION",
        "-" * 60,
    ]
    for p in (o, d):
        c = p["congestion"]
        when = f", as of {c['as_of']}" if c["as_of"] else ""
        lines.append(
            f"{p['port']}: {c['level']} ({c['score']}/100), about "
            f"{c['waiting_hours']:.1f} h wait. Source: {c['source_label']}{when}"
        )
    lines += [
        f"Total waiting: {r['waiting']['hours']:.1f} h ({r['waiting']['days']:.2f} days)",
        "",
        "WEATHER",
        "-" * 60,
        f"Overall: {r['weather']['overall_level']} ({r['weather']['overall_score']}/100)",
        f"{o['port']}: {o['weather_level']} ({o['weather_score']}/100)",
        f"{d['port']}: {d['weather_level']} ({d['weather_score']}/100)",
        "",
        "FREIGHT",
        "-" * 60,
        f"Base rate: ${freight['base_rate']:,.2f}/MT ({freight['status']['source_label']})",
        f"Forecast rate: ${freight['forecast_rate']:,.2f}/MT",
        f"Freight cost: ${freight['cost']:,.2f}",
        "",
        "COSTS",
        "-" * 60,
        f"Voyage cost: ${voyage['total_cost']:,.2f}",
        f"Freight cost: ${freight['cost']:,.2f}",
        f"Total project cost: ${r['total_cost']:,.2f}",
        "",
        "Estimates for decision support only. Distances are straight-line, not shipping lanes.",
    ]
    return "\n".join(lines)
