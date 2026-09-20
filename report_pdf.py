"""
report_pdf.py

Builds the downloadable PDF voyage report from a result dictionary
produced by freight_core.compute_voyage() and build_summary().

Uses reportlab's built-in fonts, which only cover Western characters, so
all text goes through _t() to swap or drop anything they cannot draw.
"""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from freight_core import weather_description
from reportlab.platypus import (
    HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

NAVY = colors.HexColor("#12283A")
TEAL = colors.HexColor("#1F7A8C")
SIGNAL = colors.HexColor("#E0A100")
INK = colors.HexColor("#1F2933")
MUTED = colors.HexColor("#5B6B7A")
RULE = colors.HexColor("#D5DDE5")
PAPER = colors.HexColor("#F3F6F8")

LEVEL_COLORS = {
    "Low": "#2F8F5B",
    "Moderate": "#B78600",
    "High": "#C2551F",
    "Severe": "#B3261E",
    "Unavailable": "#5B6B7A",
}

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


# ------------------------------------------------------------
# Text helpers
# ------------------------------------------------------------

def _t(value):
    """Make text safe for reportlab's built-in fonts and Paragraph markup."""
    text = str(value)
    text = text.replace("\u2192", " to ").replace("\u2248", "about ")
    text = text.encode("cp1252", "replace").decode("cp1252")
    return escape(text)


def _level(level):
    color = LEVEL_COLORS.get(level, LEVEL_COLORS["Unavailable"])
    return f'<font color="{color}"><b>{_t(level)}</b></font>'


# ------------------------------------------------------------
# Styles
# ------------------------------------------------------------

def _styles():
    base = dict(fontName="Helvetica", textColor=INK, alignment=TA_LEFT)
    return {
        "body": ParagraphStyle("body", fontSize=9.5, leading=13.5, **base),
        "small": ParagraphStyle(
            "small", fontSize=8, leading=11, **{**base, "textColor": MUTED}
        ),
        "cell": ParagraphStyle("cell", fontSize=9, leading=12, **base),
        "cell_head": ParagraphStyle(
            "cell_head", fontSize=8.5, leading=11,
            **{**base, "fontName": "Helvetica-Bold", "textColor": MUTED},
        ),
        "h2": ParagraphStyle(
            "h2", fontSize=12.5, leading=16, spaceBefore=14, spaceAfter=3,
            **{**base, "fontName": "Helvetica-Bold", "textColor": NAVY},
        ),
        "headline": ParagraphStyle(
            "headline", fontSize=14, leading=19, spaceAfter=6,
            **{**base, "fontName": "Times-Roman", "textColor": NAVY},
        ),
        "rating": ParagraphStyle(
            "rating", fontSize=10, leading=13, spaceAfter=3,
            **{**base, "fontName": "Helvetica-Bold"},
        ),
        "kpi_label": ParagraphStyle(
            "kpi_label", fontSize=8, leading=10,
            **{**base, "textColor": MUTED},
        ),
        "kpi_value": ParagraphStyle(
            "kpi_value", fontSize=14, leading=18,
            **{**base, "fontName": "Helvetica-Bold", "textColor": NAVY},
        ),
        "kpi_sub": ParagraphStyle(
            "kpi_sub", fontSize=7.5, leading=10, **{**base, "textColor": MUTED}
        ),
    }


def _heading(text, styles):
    return [
        Paragraph(_t(text), styles["h2"]),
        HRFlowable(width="100%", thickness=0.6, color=RULE, spaceAfter=5),
    ]


def _table(data, col_widths, header=True, align_right_from=None):
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
    ]
    if header:
        style += [("LINEBELOW", (0, 0), (-1, 0), 0.8, MUTED)]
    if align_right_from is not None:
        style += [("ALIGN", (align_right_from, 0), (-1, -1), "RIGHT")]
    table = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    table.setStyle(TableStyle(style))
    return table


# ------------------------------------------------------------
# Building blocks
# ------------------------------------------------------------

def _header_band(r, styles):
    title = ParagraphStyle(
        "t", fontName="Times-Bold", fontSize=21, leading=25,
        textColor=colors.white,
    )
    sub = ParagraphStyle(
        "s", fontName="Helvetica", fontSize=9, leading=12,
        textColor=colors.HexColor("#C9D6E2"),
    )
    right = ParagraphStyle(
        "r", fontName="Helvetica", fontSize=8.5, leading=12,
        textColor=colors.HexColor("#C9D6E2"), alignment=2,
    )
    left_cell = [
        Paragraph("Voyage analysis report", title),
        Paragraph("Intelligent Freight Forecasting &amp; Vessel Chartering System", sub),
    ]
    right_cell = [Paragraph(f"Generated<br/>{_t(r['generated_at'])}", right)]
    band = Table([[left_cell, right_cell]], colWidths=[CONTENT_W * 0.7, CONTENT_W * 0.3])
    band.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LINEBELOW", (0, 0), (-1, -1), 3, SIGNAL),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return band


def _summary_block(r, styles):
    s = r["summary"]
    color = colors.HexColor(LEVEL_COLORS[s["level"]])
    hex_color = LEVEL_COLORS[s["level"]]

    cell = [
        Paragraph(
            f'<font color="{hex_color}">Overall outlook: {_t(s["rating"])}</font>',
            styles["rating"],
        ),
        Paragraph(_t(s["headline"]), styles["headline"]),
    ]
    for bullet in s["bullets"]:
        cell.append(Paragraph(_t(bullet), styles["body"], bulletText="\u2022"))
        cell.append(Spacer(1, 2))
    cell.append(Spacer(1, 4))
    cell.append(Paragraph("<b>What to watch</b>", styles["body"]))
    for item in s["watch"]:
        cell.append(Paragraph(_t(item), styles["body"], bulletText="\u2022"))

    block = Table([[cell]], colWidths=[CONTENT_W])
    block.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PAPER),
        ("LINEBEFORE", (0, 0), (0, -1), 5, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return block


def _key_figures(r, styles):
    inp, voyage, freight = r["inputs"], r["voyage"], r["freight"]
    cells = [
        ("Distance", f"{r['distance_nm']:,.0f} NM", f"at {inp['vessel_speed']:.1f} knots"),
        ("Total time", f"{voyage['total_days']:.1f} days",
         f"{voyage['sailing_days']:.1f} at sea, {r['port_days_total']:.1f} in port"),
        ("Forecast freight", f"${freight['forecast_rate']:,.2f}/MT",
         f"{freight['uplift_pct']:+.1f}% vs base rate"),
        ("Total project cost", f"${r['total_cost']:,.0f}",
         f"Freight ${freight['cost']:,.0f}"),
    ]
    row = [
        [
            Paragraph(_t(label), styles["kpi_label"]),
            Paragraph(_t(value), styles["kpi_value"]),
            Paragraph(_t(sub), styles["kpi_sub"]),
        ]
        for label, value, sub in cells
    ]
    table = Table([row], colWidths=[CONTENT_W / 4] * 4)
    table.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, NAVY),
        ("LINEBELOW", (0, 0), (-1, 0), 0.4, RULE),
        ("LINEBEFORE", (1, 0), (-1, 0), 0.4, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _passage_drawing(r):
    """Bar showing how the voyage time splits between waiting, sailing and port."""
    o, d = r["origin"], r["destination"]
    segments = [
        ("Wait, origin", o["congestion"]["waiting_hours"] / 24, SIGNAL),
        ("At sea", r["voyage"]["sailing_days"], TEAL),
        ("Wait, dest.", d["congestion"]["waiting_hours"] / 24, SIGNAL),
        ("Port stay", r["inputs"]["port_days"], MUTED),
    ]
    segments = [s for s in segments if s[1] > 0.005]
    total = sum(s[1] for s in segments) or 1

    width, height, bar_h = CONTENT_W, 46, 16
    drawing = Drawing(width, height)

    min_share = 0.13
    shares = [max(s[1] / total, min_share) for s in segments]
    scale = sum(shares)
    x = 0
    for (label, days, color), share in zip(segments, shares):
        w = width * share / scale
        drawing.add(Rect(x, height - bar_h, w - 1.5, bar_h, fillColor=color, strokeColor=None))
        drawing.add(String(x + 1, height - bar_h - 11, label, fontName="Helvetica", fontSize=7.5, fillColor=INK))
        drawing.add(String(x + 1, height - bar_h - 21, f"{days:.1f} days", fontName="Helvetica-Bold", fontSize=7.5, fillColor=INK))
        x += w
    return drawing


def _congestion_section(r, styles):
    rows = [[Paragraph(_t(h), styles["cell_head"]) for h in
             ("Port", "Level", "Score", "Est. wait", "Data source", "Data as of")]]
    notes = []
    for p in (r["origin"], r["destination"]):
        c = p["congestion"]
        rows.append([
            Paragraph(_t(p["port"]), styles["cell"]),
            Paragraph(_level(c["level"]), styles["cell"]),
            Paragraph(f"{c['score']}/100", styles["cell"]),
            Paragraph(f"{c['waiting_hours']:.0f} h", styles["cell"]),
            Paragraph(_t(c["source_label"]), styles["cell"]),
            Paragraph(_t(c["as_of"] or "n/a"), styles["cell"]),
        ])
        if c["detail"]:
            notes.append(f"{p['port']}: {c['detail']}")
        if c["note"]:
            notes.append(f"{p['port']}: live data not used ({c['note']}).")

    widths = [CONTENT_W * f for f in (0.14, 0.13, 0.10, 0.11, 0.35, 0.17)]
    out = _heading("Port congestion", styles) + [_table(rows, widths)]
    out.append(Spacer(1, 3))
    out.append(Paragraph(
        f"Total estimated waiting: {r['waiting']['hours']:.1f} hours "
        f"({r['waiting']['days']:.2f} days).", styles["body"]))
    for note in notes:
        out.append(Paragraph(_t(note), styles["small"]))
    return out


def _weather_section(r, styles):
    o, d = r["origin"], r["destination"]

    def cell(weather, key, fmt, suffix=""):
        if not weather or "error" in weather or weather.get(key) is None:
            return "n/a"
        return f"{weather[key]:{fmt}}{suffix}"

    def condition(weather):
        if not weather or "error" in weather:
            return "n/a"
        return weather_description(weather.get("weather_code"))

    ow, dw = o["weather"], d["weather"]
    rows = [
        [Paragraph(_t(h), styles["cell_head"]) for h in ("Measure", o["port"], d["port"])],
        ["Condition", condition(ow), condition(dw)],
        ["Temperature", cell(ow, "temperature", ".1f", " °C"), cell(dw, "temperature", ".1f", " °C")],
        ["Wind speed", cell(ow, "wind_speed", ".1f", " km/h"), cell(dw, "wind_speed", ".1f", " km/h")],
        ["Wind gusts", cell(ow, "wind_gusts", ".1f", " km/h"), cell(dw, "wind_gusts", ".1f", " km/h")],
        ["Rain", cell(ow, "precipitation", ".1f", " mm"), cell(dw, "precipitation", ".1f", " mm")],
        ["Weather risk", None, None],
    ]
    body = [rows[0]]
    for row in rows[1:-1]:
        body.append([Paragraph(_t(v), styles["cell"]) for v in row])
    body.append([
        Paragraph("Weather risk", styles["cell"]),
        Paragraph(f"{_level(o['weather_level'])} ({o['weather_score']}/100)", styles["cell"]),
        Paragraph(f"{_level(d['weather_level'])} ({d['weather_score']}/100)", styles["cell"]),
    ])

    widths = [CONTENT_W * f for f in (0.28, 0.36, 0.36)]
    out = _heading("Weather at the ports", styles) + [_table(body, widths)]
    out.append(Spacer(1, 3))
    overall = r["weather"]
    out.append(Paragraph(
        f"Overall weather risk: {_level(overall['overall_level'])}"
        + (f" ({overall['overall_score']}/100)" if overall["available"] else ""),
        styles["body"]))
    times = [w["time"] for w in (ow, dw) if w and "error" not in w and w.get("time")]
    if times:
        out.append(Paragraph(f"Live weather from Open-Meteo, latest reading {_t(max(times))}.", styles["small"]))
    return out


def _freight_section(r, styles):
    f = r["freight"]
    status = f["status"]
    qty = r["inputs"]["cargo_quantity"]
    rows = [
        [Paragraph(h, styles["cell_head"]) for h in ("Item", "Value")],
        [Paragraph(f"Base freight rate<br/><font size=7.5 color='#5B6B7A'>{_t(status['source_label'])}</font>", styles["cell"]),
         Paragraph(f"${f['base_rate']:,.2f} per MT", styles["cell"])],
        [Paragraph("Congestion adjustment", styles["cell"]), Paragraph(f"+{f['congestion_pct']:.1f}%", styles["cell"])],
        [Paragraph("Weather adjustment", styles["cell"]), Paragraph(f"+{f['weather_pct']:.1f}%", styles["cell"])],
        [Paragraph("<b>Forecast freight rate</b>", styles["cell"]), Paragraph(f"<b>${f['forecast_rate']:,.2f} per MT</b>", styles["cell"])],
        [Paragraph("Cargo quantity", styles["cell"]), Paragraph(f"{qty:,.0f} MT", styles["cell"])],
        [Paragraph("<b>Freight cost</b>", styles["cell"]), Paragraph(f"<b>${f['cost']:,.2f}</b>", styles["cell"])],
    ]
    widths = [CONTENT_W * 0.6, CONTENT_W * 0.4]
    out = _heading("Freight rate forecast", styles) + [_table(rows, widths)]
    if status["as_of"]:
        out.append(Spacer(1, 3))
        out.append(Paragraph(f"Base rate as of {_t(status['as_of'])}.", styles["small"]))
    return out


def _cost_section(r, styles):
    voyage, f = r["voyage"], r["freight"]
    total = r["total_cost"] or 1
    rows = [
        [Paragraph(h, styles["cell_head"]) for h in ("Cost", "Amount", "Share")],
        [Paragraph("Vessel running cost", styles["cell"]),
         Paragraph(f"${voyage['total_cost']:,.2f}", styles["cell"]),
         Paragraph(f"{voyage['total_cost'] / total * 100:.0f}%", styles["cell"])],
        [Paragraph("Freight cost", styles["cell"]),
         Paragraph(f"${f['cost']:,.2f}", styles["cell"]),
         Paragraph(f"{f['cost'] / total * 100:.0f}%", styles["cell"])],
        [Paragraph("<b>Total project cost</b>", styles["cell"]),
         Paragraph(f"<b>${r['total_cost']:,.2f}</b>", styles["cell"]),
         Paragraph("100%", styles["cell"])],
    ]
    widths = [CONTENT_W * 0.5, CONTENT_W * 0.3, CONTENT_W * 0.2]
    return _heading("Cost summary", styles) + [_table(rows, widths)]


def _sources_section(r, styles):
    o, d = r["origin"], r["destination"]
    items = []
    for p in (o, d):
        c = p["congestion"]
        when = f", data as of {c['as_of']}" if c["as_of"] else ""
        items.append(f"Congestion at {p['port']}: {c['source_label']}{when}.")
    if any(p["congestion"]["source"] == "live" for p in (o, d)):
        items.append(
            "Live congestion compares the last 7 days of ship calls with the port's "
            "usual level over the previous 90 days. It shows how busy a port is, "
            "not the actual waiting time. Waiting hours are estimated from the score."
        )
    items.append("Weather: current conditions from Open-Meteo.")
    items.append(f"Freight base rate: {r['freight']['status']['source_label']}.")
    items.append(
        "Distances are straight-line (great-circle) and do not follow shipping lanes, "
        "so real sailing distance can be longer."
    )
    items.append("Figures are estimates to support a decision and are not a quotation.")

    out = _heading("Data sources and assumptions", styles)
    for item in items:
        out.append(Paragraph(_t(item), styles["small"], bulletText="\u2022"))
        out.append(Spacer(1, 2))
    return out


# ------------------------------------------------------------
# Page furniture
# ------------------------------------------------------------

def _footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 14 * mm, PAGE_W - MARGIN, 14 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 10 * mm, "Intelligent Freight Forecasting & Vessel Chartering System")
    canvas.drawRightString(PAGE_W - MARGIN, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


# ------------------------------------------------------------
# Public function
# ------------------------------------------------------------

def build_pdf(r):
    """Return the report as PDF bytes."""
    styles = _styles()
    inp = r["inputs"]
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=20 * mm,
        title=_t(f"Voyage report: {r['origin']['port']} to {r['destination']['port']}"),
        author="Intelligent Freight Forecasting System",
    )

    voyage_line = (
        f"<b>{_t(inp['vessel_name'])}</b> ({_t(inp['vessel_type'])}), "
        f"{_t(inp['cargo'])}, {inp['cargo_quantity']:,.0f} MT, "
        f"{_t(r['origin']['port'])} to {_t(r['destination']['port'])}"
    )

    story = [
        _header_band(r, styles),
        Spacer(1, 8),
        Paragraph(voyage_line, styles["body"]),
        Spacer(1, 8),
        _summary_block(r, styles),
        Spacer(1, 10),
        _key_figures(r, styles),
        Spacer(1, 12),
        Paragraph("How the voyage time is spent", styles["small"]),
        Spacer(1, 2),
        _passage_drawing(r),
        KeepTogether(_congestion_section(r, styles)),
        KeepTogether(_weather_section(r, styles)),
        KeepTogether(_freight_section(r, styles)),
        KeepTogether(_cost_section(r, styles)),
        KeepTogether(_sources_section(r, styles)),
    ]

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
