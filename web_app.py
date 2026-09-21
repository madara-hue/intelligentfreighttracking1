"""
Intelligent Freight Forecasting & Vessel Chartering System

Run with:  streamlit run web_app.py

Files that go together:
    web_app.py      this file, the screens
    freight_core.py data sources, calculations, plain-English summary
    report_pdf.py   the downloadable PDF report
"""

import base64
import html
import os

import pandas as pd
import streamlit as st

import freight_core as fc

try:
    from report_pdf import build_pdf
except ImportError:  # reportlab not installed yet
    build_pdf = None


# ============================================================
# PAGE SETUP AND STYLE
# ============================================================

st.set_page_config(
    page_title="Intelligent Freight Forecasting",
    page_icon="🚢",
    layout="wide",
)

CSS = """
<style>
.block-container {padding-top: 2rem; max-width: 1200px;}

.hero {background:#12283a; color:#f4f7fa; padding:1.6rem 1.9rem; border-radius:6px;
       border:1px solid rgba(255,255,255,.10); border-bottom:4px solid #e0a100; margin-bottom:1.4rem;}
.hero-title {font-family:Georgia,'Times New Roman',serif; font-size:2.05rem;
             font-weight:700; line-height:1.2;}
.hero-sub {margin-top:.55rem; color:#c9d6e2; font-size:1.02rem; line-height:1.5; max-width:44rem;}

.summary {border-left:6px solid #5b6b7a; background:rgba(18,40,58,.78);
          padding:1.2rem 1.5rem; border-radius:0 6px 6px 0; margin-bottom:.9rem;}
.summary-rating {font-weight:700; font-size:.95rem; margin-bottom:.2rem;}
.summary-headline {font-family:Georgia,'Times New Roman',serif; font-size:1.5rem;
                   line-height:1.35; margin:.1rem 0 .8rem;}
.summary ul {margin:.2rem 0 .7rem 1.1rem; padding:0;}
.summary li {margin:.3rem 0; line-height:1.5;}
.watch {border-top:1px solid rgba(128,140,150,.4); padding-top:.65rem; margin-top:.5rem;}
.watch-title {font-weight:700; margin-bottom:.2rem;}

.ledger {display:flex; flex-wrap:wrap; border-top:2px solid #2bb0c4; background:rgba(12,26,38,.70);
         border-bottom:1px solid rgba(128,140,150,.4); margin:.6rem 0 1.2rem;}
.ledger > div {flex:1 1 200px; padding:.85rem 1rem; border-left:1px solid rgba(128,140,150,.4);}
.ledger > div:first-child {border-left:none; padding-left:1rem;}
.l-label {font-size:.88rem; opacity:.7;}
.l-value {font-size:1.65rem; font-weight:700; line-height:1.3;}
.l-sub {font-size:.85rem; opacity:.7;}
@media (max-width: 640px) {
  .ledger > div {flex:1 1 100%; border-left:none; padding-left:1rem;
                 border-top:1px solid rgba(128,140,150,.4);}
  .ledger > div:first-child {border-top:none;}
}

.passage-title {font-size:.92rem; opacity:.75; margin-bottom:.35rem;}
.passage {display:flex; gap:2px; margin-bottom:1.4rem;}
.seg-bar {height:18px;}
.seg-label {font-size:.82rem; margin-top:.3rem; line-height:1.3;}
.seg-label b {display:block;}

.board {border:1px solid rgba(128,140,150,.4); border-left:6px solid #5b6b7a;
        border-radius:4px; padding:1.05rem 1.2rem; background:rgba(18,40,58,.78);
        margin-bottom:.8rem;}
.board-head {display:flex; justify-content:space-between; align-items:center; margin-bottom:.65rem;}
.board-port {font-family:Georgia,'Times New Roman',serif; font-size:1.35rem; font-weight:700;}
.meter {height:8px; background:rgba(128,140,150,.3); border-radius:2px; overflow:hidden;
        margin-bottom:.8rem;}
.meter span {display:block; height:100%;}
.board-stats {display:flex; gap:2.2rem; margin-bottom:.6rem;}
.board-stats b {font-size:1.3rem; display:block; line-height:1.25;}
.board-stats small {opacity:.7; font-size:.85rem;}
.src {font-size:.88rem; margin:.3rem 0;}
.board-detail {font-size:.92rem; line-height:1.45; margin-top:.5rem;}
.board-note {font-size:.88rem; opacity:.85; margin-top:.5rem; line-height:1.4;}

.badge {display:inline-block; padding:.12rem .6rem; border-radius:3px; font-size:.8rem;
        font-weight:600; color:#fff; white-space:nowrap; margin-right:.35rem;}
.b-low {background:#2f8f5b;}
.b-moderate {background:#e0a100; color:#2b1d00;}
.b-high {background:#c2551f;}
.b-severe {background:#b3261e;}
.b-unavailable {background:#5b6b7a;}
.b-live {background:#1f7a8c;}
.b-manual {background:#6b4fa0;}
.b-reference {background:#5b6b7a;}

.row {display:flex; justify-content:space-between; gap:1rem; padding:.5rem .1rem;
      border-bottom:1px solid rgba(128,140,150,.3);}
.row-total {font-weight:700; border-bottom:2px solid #2bb0c4;}
.row-sub {font-size:.85rem; opacity:.75;}
.row > span:last-child {text-align:right; font-variant-numeric:tabular-nums;}

.costbar {display:flex; height:26px; border-radius:3px; overflow:hidden; margin:.5rem 0 .55rem;}
.costbar span {display:block; height:100%;}
.legend {display:flex; gap:1.6rem; flex-wrap:wrap; font-size:.92rem;}
.dot {display:inline-block; width:.7rem; height:.7rem; margin-right:.4rem; border-radius:2px;}

.steps {margin:.2rem 0 1rem 1.2rem; line-height:1.7; font-size:1.02rem;}

section[data-testid="stSidebar"] .stButton > button {width:100%; font-weight:600;}
.stDownloadButton > button {font-weight:600;}
button[kind="primary"], button[data-testid="stBaseButton-primary"] {
    background-color:#1f7a8c; border-color:#1f7a8c; color:#fff;}
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {
    background-color:#186270; border-color:#186270; color:#fff;}
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


def set_background(image_name, overlay=0.35):
    """Dark page background from an image next to this file.
    Does nothing if the image is missing, so the app still runs."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), image_name)
    if not os.path.exists(path):
        return
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    ext = path.rsplit(".", 1)[-1].lower()
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    st.markdown(
        "<style>.stApp {"
        f"background-image: linear-gradient(rgba(12,26,38,{overlay}), rgba(12,26,38,{overlay})), "
        f'url("data:image/{mime};base64,{encoded}");'
        "background-size: cover; background-position: center; background-attachment: fixed;"
        "}</style>",
        unsafe_allow_html=True,
    )


set_background("background_dark.jpg")

# Lighter shades for coloured text on the dark panels
LEVEL_TEXT = {
    "Low": "#5fd08f",
    "Moderate": "#f0b429",
    "High": "#f08a4b",
    "Severe": "#ff6b61",
    "Unavailable": "#9fb0bf",
}

USD = "&#36;"  # dollar sign that is never read as maths markup

LEVEL_COLOR = {
    "Low": "#2f8f5b",
    "Moderate": "#e0a100",
    "High": "#c2551f",
    "Severe": "#b3261e",
    "Unavailable": "#5b6b7a",
}


# ============================================================
# SMALL HTML HELPERS
# ============================================================
# Every block starts with a <div> and contains no blank lines or
# indentation, so Streamlit's markdown leaves the HTML alone.

def esc(value):
    """Escape text for HTML. Dollar signs are escaped so they are never
    read as maths markup."""
    return html.escape(str(value)).replace("$", "&#36;")


def md(markup):
    st.markdown(markup, unsafe_allow_html=True)


def badge(text, kind):
    return f'<span class="badge b-{kind}">{esc(text)}</span>'


def level_badge(level):
    return badge(level, level.lower())


def source_badge(source):
    labels = {"live": "Live", "manual": "Your quote", "reference": "Reference"}
    return badge(labels[source], source)


def show(value, suffix=""):
    return "n/a" if value is None else f"{value}{suffix}"


# ============================================================
# SETTINGS AND CACHED DATA CALLS
# ============================================================

def get_setting(name):
    """Read an optional setting from the environment or Streamlit secrets."""
    value = os.environ.get(name)
    if value:
        return value
    try:
        return st.secrets.get(name)
    except Exception:
        return None


FREIGHT_API_URL = get_setting("FREIGHT_API_URL")
FREIGHT_API_KEY = get_setting("FREIGHT_API_KEY")


# Failed requests raise inside these functions, so Streamlit does not
# cache a failure. The wrappers below turn the error into a message.

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_port_activity(port):
    return fc.fetch_port_activity(port)


@st.cache_data(ttl=600, show_spinner=False)
def _cached_weather(latitude, longitude):
    return fc.fetch_weather(latitude, longitude)


@st.cache_data(ttl=1800, show_spinner=False)
def _cached_api_rate(url, key, cargo, origin, destination):
    return fc.fetch_api_freight_rate(url, key, cargo, origin, destination)


def get_port_activity(port):
    try:
        return _cached_port_activity(port), None
    except Exception as error:
        return None, f"PortWatch: {fc.describe_error(error)}"


def get_weather(port):
    try:
        info = fc.PORTS[port]
        return _cached_weather(info["latitude"], info["longitude"])
    except Exception as error:
        return {"error": f"Weather service: {fc.describe_error(error)}"}


def get_api_rate(cargo, origin, destination):
    try:
        return _cached_api_rate(
            FREIGHT_API_URL, FREIGHT_API_KEY, cargo, origin, destination
        ), None
    except Exception as error:
        return None, f"freight API: {fc.describe_error(error)}"


# ============================================================
# ANALYSIS
# ============================================================

def make_pdf(result):
    if build_pdf is None:
        return None, "The PDF library is not installed. Run: pip install reportlab"
    try:
        return build_pdf(result), None
    except Exception as error:
        return None, f"The PDF could not be created: {error}"


def run_analysis(inputs):
    origin, destination = inputs["origin"], inputs["destination"]

    # Port congestion: live from PortWatch, else the stored reference value
    congestion = {}
    for port in (origin, destination):
        if not inputs["use_live"]:
            congestion[port] = fc.congestion_status_reference(
                port, "switched off in the sidebar"
            )
            continue
        activity, error = get_port_activity(port)
        if activity:
            congestion[port] = fc.congestion_status_live(port, activity)
        else:
            congestion[port] = fc.congestion_status_reference(
                port, error or "no matching port in the PortWatch data"
            )

    # Weather: always live
    origin_weather = get_weather(origin)
    destination_weather = get_weather(destination)

    # Freight rate: your quote, then the freight API, then the stored table
    api_result, api_note = None, ""
    manual = inputs["manual_rate"]
    if inputs["use_live"] and not manual and FREIGHT_API_URL and FREIGHT_API_KEY:
        api_result, api_note = get_api_rate(inputs["cargo"], origin, destination)
    freight = fc.resolve_freight_rate(
        inputs["cargo"], manual_rate=manual, api_result=api_result,
        api_note=api_note or "",
    )

    result = fc.compute_voyage(
        inputs, congestion[origin], congestion[destination],
        origin_weather, destination_weather, freight,
    )
    result["summary"] = fc.build_summary(result)
    result["text"] = fc.build_text_report(result)
    result["pdf"], result["pdf_error"] = make_pdf(result)
    return result


# ============================================================
# HTML BUILDERS FOR THE RESULT SCREENS
# ============================================================

def summary_panel(r):
    s = r["summary"]
    color = LEVEL_COLOR[s["level"]]
    bullets = "".join(f"<li>{esc(b)}</li>" for b in s["bullets"])
    watch = "".join(f"<li>{esc(w)}</li>" for w in s["watch"])
    return (
        f'<div class="summary" style="border-left-color:{color}">'
        f'<div class="summary-rating" style="color:{LEVEL_TEXT[s["level"]]}">Overall outlook: {esc(s["rating"])}</div>'
        f'<div class="summary-headline">{esc(s["headline"])}</div>'
        f"<ul>{bullets}</ul>"
        f'<div class="watch"><div class="watch-title">What to watch</div><ul>{watch}</ul></div>'
        "</div>"
    )


def ledger(r):
    voyage, freight, inp = r["voyage"], r["freight"], r["inputs"]
    cells = [
        ("Distance", f"{r['distance_nm']:,.0f} NM", f"at {inp['vessel_speed']:.1f} knots"),
        ("Total time", f"{voyage['total_days']:.1f} days",
         f"{voyage['sailing_days']:.1f} at sea, {r['port_days_total']:.1f} in port"),
        ("Forecast freight rate", f"${freight['forecast_rate']:,.2f}/MT",
         f"{freight['uplift_pct']:+.1f}% against the base rate"),
        ("Total project cost", f"${r['total_cost']:,.0f}",
         f"Freight ${freight['cost']:,.0f}"),
    ]
    inner = "".join(
        f'<div><div class="l-label">{esc(a)}</div>'
        f'<div class="l-value">{esc(b)}</div>'
        f'<div class="l-sub">{esc(c)}</div></div>'
        for a, b, c in cells
    )
    return f'<div class="ledger">{inner}</div>'


def passage_strip(r):
    """How the voyage time splits between waiting, sailing and port stay."""
    o, d = r["origin"], r["destination"]
    parts = [
        ("Waiting at origin", o["congestion"]["waiting_hours"] / 24, "#e0a100"),
        ("At sea", r["voyage"]["sailing_days"], "#1f7a8c"),
        ("Waiting at destination", d["congestion"]["waiting_hours"] / 24, "#e0a100"),
        ("Planned port stay", r["inputs"]["port_days"], "#5b6b7a"),
    ]
    parts = [p for p in parts if p[1] > 0.005]
    total = sum(p[1] for p in parts) or 1
    segments = "".join(
        f'<div style="flex:{max(days, total * 0.12):.3f} 1 0%;min-width:72px">'
        f'<div class="seg-bar" style="background:{color}"></div>'
        f'<div class="seg-label"><b>{days:.1f} days</b>{esc(label)}</div></div>'
        for label, days, color in parts
    )
    return (
        '<div><div class="passage-title">How the voyage time is spent</div>'
        f'<div class="passage">{segments}</div></div>'
    )


def port_board(p):
    c = p["congestion"]
    color = LEVEL_COLOR[c["level"]]
    as_of = f", data as of {esc(c['as_of'])}" if c["as_of"] else ""
    out = (
        f'<div class="board" style="border-left-color:{color}">'
        f'<div class="board-head"><span class="board-port">{esc(p["port"])}</span>'
        f'{level_badge(c["level"])}</div>'
        f'<div class="meter"><span style="width:{c["score"]}%;background:{color}"></span></div>'
        '<div class="board-stats">'
        f'<div><b>{c["score"]}/100</b><small>congestion score</small></div>'
        f'<div><b>{c["waiting_hours"]:.0f} hours</b><small>estimated wait</small></div>'
        "</div>"
        f'<div class="src">{source_badge(c["source"])}{esc(c["source_label"])}{as_of}</div>'
    )
    if c["detail"]:
        out += f'<div class="board-detail">{esc(c["detail"])}</div>'
    if c["note"]:
        out += (
            '<div class="board-note">Live data was not used: '
            f'{esc(c["note"])}. A stored reference value is shown instead.</div>'
        )
    return out + "</div>"


def weather_board(p):
    w, level = p["weather"], p["weather_level"]
    color = LEVEL_COLOR[level]
    head = (
        f'<div class="board" style="border-left-color:{color}">'
        f'<div class="board-head"><span class="board-port">{esc(p["port"])}</span>'
        f"{level_badge(level)}</div>"
    )
    if not w or "error" in w:
        reason = (w or {}).get("error", "no data returned")
        return head + (
            f'<div class="board-note">Live weather is unavailable ({esc(reason)}). '
            "It is left out of the risk rating for this port.</div></div>"
        )

    rows = [
        ("Condition", fc.weather_description(w.get("weather_code"))),
        ("Temperature", show(w.get("temperature"), " °C")),
        ("Wind speed", show(w.get("wind_speed"), " km/h")),
        ("Wind gusts", show(w.get("wind_gusts"), " km/h")),
        ("Wind direction", show(w.get("wind_direction"), "°")),
        ("Rain", show(w.get("precipitation"), " mm")),
        ("Humidity", show(w.get("humidity"), "%")),
    ]
    body = "".join(
        f'<div class="row"><span>{esc(a)}</span><span>{esc(b)}</span></div>'
        for a, b in rows
    )
    return (
        head
        + f'<div class="meter"><span style="width:{p["weather_score"]}%;background:{color}"></span></div>'
        + f'<div class="src">Weather risk score {p["weather_score"]}/100</div>'
        + body
        + f'<div class="board-note">Live from Open-Meteo, updated {esc(show(w.get("time")))}.</div>'
        "</div>"
    )


def rate_buildup(r):
    f = r["freight"]
    status = f["status"]
    as_of = f", as of {esc(status['as_of'])}" if status["as_of"] else ""
    rows = [
        ('<div class="row"><span>Base freight rate'
         f'<div class="row-sub">{source_badge(status["source"])}{esc(status["source_label"])}{as_of}</div></span>'
         f'<span>{USD}{f["base_rate"]:,.2f} per MT</span></div>'),
        f'<div class="row"><span>Congestion adjustment</span><span>+{f["congestion_pct"]:.1f}%</span></div>',
        f'<div class="row"><span>Weather adjustment</span><span>+{f["weather_pct"]:.1f}%</span></div>',
        f'<div class="row row-total"><span>Forecast freight rate</span><span>{USD}{f["forecast_rate"]:,.2f} per MT</span></div>',
        f'<div class="row"><span>Cargo quantity</span><span>{r["inputs"]["cargo_quantity"]:,.0f} MT</span></div>',
        f'<div class="row row-total"><span>Freight cost</span><span>{USD}{f["cost"]:,.2f}</span></div>',
    ]
    note = ""
    if status["note"]:
        note = f'<div class="board-note">Live rate not used: {esc(status["note"])}.</div>'
    return "<div>" + "".join(rows) + note + "</div>"


def cost_bar(r):
    voyage_cost, freight_cost = r["voyage"]["total_cost"], r["freight"]["cost"]
    total = r["total_cost"] or 1
    v_pct, f_pct = voyage_cost / total * 100, freight_cost / total * 100
    return (
        '<div><div class="passage-title">Where the money goes</div>'
        '<div class="costbar">'
        f'<span style="width:{v_pct:.1f}%;background:#5b6b7a"></span>'
        f'<span style="width:{f_pct:.1f}%;background:#1f7a8c"></span></div>'
        '<div class="legend">'
        f'<div><span class="dot" style="background:#5b6b7a"></span>Vessel running cost {USD}{voyage_cost:,.0f} ({v_pct:.0f}%)</div>'
        f'<div><span class="dot" style="background:#1f7a8c"></span>Freight cost {USD}{freight_cost:,.0f} ({f_pct:.0f}%)</div>'
        "</div></div>"
    )


def figures_table(r):
    inp, o, d = r["inputs"], r["origin"], r["destination"]
    voyage, freight = r["voyage"], r["freight"]
    rows = [
        ("Vessel", inp["vessel_name"]),
        ("Vessel type", inp["vessel_type"]),
        ("Cargo", inp["cargo"]),
        ("Quantity", f"{inp['cargo_quantity']:,.0f} MT"),
        ("Route", f"{o['port']} to {d['port']}"),
        ("Distance", f"{r['distance_nm']:,.0f} NM"),
        ("Sailing time", f"{voyage['sailing_days']:.2f} days"),
        ("Total port time", f"{r['port_days_total']:.2f} days"),
        ("Weather risk", f"{r['weather']['overall_level']} ({r['weather']['overall_score']}/100)"),
        (f"Congestion at {o['port']}", f"{o['congestion']['level']} ({o['congestion']['score']}/100)"),
        (f"Congestion at {d['port']}", f"{d['congestion']['level']} ({d['congestion']['score']}/100)"),
        ("Total waiting", f"{r['waiting']['days']:.2f} days"),
        ("Forecast freight", f"${freight['forecast_rate']:,.2f}/MT"),
        ("Voyage cost", f"${voyage['total_cost']:,.2f}"),
        ("Freight cost", f"${freight['cost']:,.2f}"),
        ("Total project cost", f"${r['total_cost']:,.2f}"),
    ]
    return pd.DataFrame(rows, columns=["Parameter", "Value"])


def sources_table(r):
    o, d = r["origin"], r["destination"]
    weather_times = [
        p["weather"]["time"] for p in (o, d)
        if p["weather"] and "error" not in p["weather"] and p["weather"].get("time")
    ]
    rows = []
    for p in (o, d):
        c = p["congestion"]
        rows.append((f"Congestion, {p['port']}", c["source_label"], c["as_of"] or "n/a"))
    rows.append(("Weather", "Open-Meteo", max(weather_times) if weather_times else "unavailable"))
    status = r["freight"]["status"]
    rows.append(("Base freight rate", status["source_label"], status["as_of"] or "n/a"))
    return pd.DataFrame(rows, columns=["Item", "Source", "Data as of"])


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("### Voyage setup")

    st.markdown("**Vessel and cargo**")
    vessel_name = st.text_input("Vessel name", "MV Ocean Star")
    vessel_type = st.selectbox(
        "Vessel type",
        ["Container Ship", "Bulk Carrier", "Tanker", "LNG Carrier",
         "LPG Carrier", "General Cargo"],
    )
    cargo = st.selectbox("Cargo type", list(fc.REFERENCE_FREIGHT_RATES.keys()))
    cargo_quantity = st.number_input(
        "Cargo quantity (tonnes)", min_value=1.0, value=10000.0, step=500.0
    )

    st.markdown("**Route**")
    origin = st.selectbox("Origin port", list(fc.PORTS.keys()))
    destination = st.selectbox(
        "Destination port", [p for p in fc.PORTS.keys() if p != origin]
    )

    st.markdown("**Operations**")
    vessel_speed = st.number_input(
        "Vessel speed (knots)", min_value=1.0, value=14.0, step=0.5
    )
    daily_cost = st.number_input(
        "Daily vessel cost ($)", min_value=100.0, value=25000.0, step=1000.0
    )
    port_days = st.number_input(
        "Planned port stay (days)", min_value=0.0, value=2.0, step=0.5
    )

    st.markdown("**Live data**")
    use_live = st.checkbox(
        "Use live congestion and freight data",
        value=True,
        help="Port congestion comes from IMF PortWatch. Turn this off to use "
             "the stored reference values instead.",
    )
    manual_rate = st.number_input(
        "Current freight quote ($ per tonne, optional)",
        min_value=0.0, value=0.0, step=1.0,
        help="If you have a current quote from a broker or index, enter it here "
             "and it replaces the base rate. Leave at 0 to use the freight API "
             "(if set up) or the stored rate.",
    )

    analyse = st.button("Analyse voyage", type="primary")


current_inputs = {
    "vessel_name": vessel_name,
    "vessel_type": vessel_type,
    "cargo": cargo,
    "origin": origin,
    "destination": destination,
    "cargo_quantity": cargo_quantity,
    "vessel_speed": vessel_speed,
    "daily_cost": daily_cost,
    "port_days": port_days,
    "use_live": use_live,
    "manual_rate": manual_rate,
}


# ============================================================
# MAIN SCREEN
# ============================================================

md(
    '<div class="hero">'
    '<div class="hero-title">Intelligent Freight Forecasting</div>'
    '<div class="hero-sub">See what a voyage will cost, how long it will take, '
    "and what could slow it down, using current port and weather data.</div>"
    "</div>"
)

if analyse:
    with st.spinner("Fetching port, weather and freight data..."):
        try:
            st.session_state["result"] = run_analysis(current_inputs)
        except ValueError as error:
            st.error(str(error))
            st.stop()

result = st.session_state.get("result")

if result is None:
    md(
        '<div class="steps"><ol>'
        "<li>Enter the vessel, cargo and route in the sidebar.</li>"
        "<li>Click Analyse voyage.</li>"
        "<li>Read the summary, then download the report as a PDF.</li>"
        "</ol></div>"
    )
    st.info(
        "Port congestion comes from IMF PortWatch ship-tracking data, which is "
        "refreshed weekly. Weather comes from Open-Meteo. For freight rates, enter "
        "a current quote in the sidebar, or the app uses stored reference rates."
    )

else:
    if result["inputs"] != current_inputs:
        st.info("You changed the inputs. Click Analyse voyage to update the results.")

    md(summary_panel(result))

    left, middle, _ = st.columns([1.3, 1, 3])
    route_tag = f"{result['origin']['port']}_{result['destination']['port']}".lower()
    with left:
        if result["pdf"]:
            st.download_button(
                "Download PDF report",
                data=result["pdf"],
                file_name=f"voyage_report_{route_tag}.pdf",
                mime="application/pdf",
                type="primary",
                key="download_pdf",
            )
    with middle:
        st.download_button(
            "Download as text",
            data=result["text"],
            file_name=f"voyage_report_{route_tag}.txt",
            mime="text/plain",
            key="download_txt",
        )
    if not result["pdf"]:
        st.warning(result["pdf_error"])

    md(ledger(result))
    md(passage_strip(result))

    tab_ports, tab_weather, tab_money, tab_data = st.tabs(
        ["Ports and congestion", "Weather", "Freight and costs", "Data and assumptions"]
    )

    with tab_ports:
        col_a, col_b = st.columns(2)
        for column, key in ((col_a, "origin"), (col_b, "destination")):
            port = result[key]
            with column:
                md(port_board(port))
                history = port["congestion"]["history"]
                if history is not None:
                    st.caption(f"Daily ship calls at {port['port']}, last 90 days")
                    st.line_chart(history)
        st.info(
            f"Total estimated waiting across both ports: "
            f"{result['waiting']['hours']:.1f} hours ({result['waiting']['days']:.2f} days)."
        )

    with tab_weather:
        col_a, col_b = st.columns(2)
        with col_a:
            md(weather_board(result["origin"]))
        with col_b:
            md(weather_board(result["destination"]))
        overall = result["weather"]
        if overall["available"]:
            st.info(
                f"Overall weather risk: {overall['overall_level']} "
                f"({overall['overall_score']}/100), taken from the worse of the two ports."
            )

    with tab_money:
        col_a, col_b = st.columns([1, 1])
        with col_a:
            st.markdown("**How the freight rate is built**")
            md(rate_buildup(result))
        with col_b:
            st.markdown("**Cost split**")
            md(cost_bar(result))
            st.markdown("**All figures**")
            st.dataframe(figures_table(result), hide_index=True)

    with tab_data:
        st.markdown("**Where each figure comes from**")
        st.dataframe(sources_table(result), hide_index=True)
        st.markdown(
            "- **Congestion score (live):** compares the last 7 days of ship calls "
            "with the port's own average over the 90 days before that. Normal traffic "
            "scores 35, and every 10% above normal adds 15 points. It shows how busy a "
            "port is, not the actual waiting time. Waiting hours are estimated from the "
            "score, from 2 hours at zero up to 48 hours at 100.\n"
            "- **Freight forecast:** the base rate plus up to 15% for congestion and up "
            "to 10% for weather risk.\n"
            "- **Distance:** straight-line (great-circle) distance between the ports. "
            "Real routes around land or through canals are longer, so sailing time and "
            "vessel cost are likely understated.\n"
            "- **Estimates only:** these figures support a decision and are not a quotation."
        )
        st.caption(f"Report generated {result['generated_at']}.")


# ============================================================
# FOOTER
# ============================================================

st.divider()
st.caption(
    "Intelligent Freight Forecasting & Vessel Chartering System. "
    "Live data: IMF PortWatch (port activity) and Open-Meteo (weather)."
)
