"""One self-contained, interactive report document for the website and PDF."""

from contextlib import contextmanager
from html import escape
import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs
from plotly.utils import PlotlyJSONEncoder

from dashboard_config import format_height_ft_in

REPORT_WIDTH = 1400

REPORT_CSS = """
* { box-sizing: border-box; }
html, body { margin: 0; background: white; color: #202124; }
body { font-family: Arial, sans-serif; font-size: 14px; overflow-x: hidden; }
#report { width: 1400px; padding: 24px; transform-origin: top left; }
.report-title { text-align: center; margin: 0 0 12px; }
.report-title h1 { margin: 0 0 6px; font-size: 30px; color: #0f172a; }
.report-title p { margin: 0; color: #475569; }
.sheet-break { margin-top: 36px; padding-top: 24px; border-top: 3px solid #cbd5e1; page-break-before: always; }
h2 { font-size: 17px; text-align: center; margin: 16px 0 8px; color: #1e293b; }
.kpi-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin: 12px 0 18px; }
.kpi-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 14px; text-align: center; }
.kpi-label { font-size: 12px; font-weight: 700; text-transform: uppercase; color: #475569; letter-spacing: 0.04em; }
.kpi-value { font-size: 26px; font-weight: 800; color: #0f172a; margin: 4px 0; }
.kpi-sub { font-size: 11px; color: #64748b; line-height: 1.35; }
.ab-card-header { display: flex; justify-content: space-between; align-items: center; background: #f1f5f9; border: 1px solid #cbd5e1; border-left: 4px solid #1e293b; border-radius: 6px; padding: 8px 14px; margin: 18px 0 6px; font-size: 13.5px; color: #0f172a; }
.ab-outcome { color: #1e3a8a; }
.columns { display: grid; gap: 16px; align-items: start; margin-top: 12px; }
.column { min-width: 0; }
.plot { width: 100%; }
.scatter-caption { text-align: center; color: #666; font-size: 18px; margin: 4px 0 12px; }
.caption { color: #666; line-height: 1.5; margin: 8px 0 12px; }
.metadata { text-align: center; margin: 0 0 12px; font-weight: 600; color: #334155; }
.info { background: #edf5fc; padding: 12px; border-radius: 6px; text-align: center; color: #1e3a8a; }
table { width: 100%; border-collapse: collapse; font-size: 12px; table-layout: auto; margin-bottom: 12px; }
th, td { border: 1px solid #cbd5e1; padding: 8px 6px; text-align: right; overflow-wrap: anywhere; }
th { background: #f1f5f9; font-weight: 700; color: #1e293b; }
th:first-child, td:first-child { text-align: left; }
@media print { body { print-color-adjust: exact; -webkit-print-color-adjust: exact; } }
"""

INTEGER_COLUMNS = {
    "Count",
    "In Play",
    "AB #",
    "Pitch #",
    "Distance (ft)",
    "Out-of-Zone Pitches",
    "Chases",
    "Takes",
}


class ReportHTML:
    """Render the report's UI calls into HTML without global Streamlit patching."""

    def __init__(self):
        self.root = []
        self.current = self.root
        self.plots = []

    def markdown(self, text, unsafe_allow_html=False):
        self.current.append(text if unsafe_allow_html else f"<p>{escape(text)}</p>")

    def caption(self, text):
        self.current.append(f'<p class="caption">{escape(text)}</p>')

    def info(self, text):
        self.current.append(f'<p class="info">{escape(text)}</p>')

    def subheader(self, text):
        self.current.append(f"<h2>{escape(text)}</h2>")

    def dataframe(self, table, **kwargs):
        display = table.copy().astype(object)
        for column in display:
            formatted = []
            for value in display[column]:
                if pd.isna(value):
                    formatted.append("-")
                elif isinstance(value, (int, np.integer)) or (
                    column in INTEGER_COLUMNS and isinstance(value, (float, np.floating))
                ):
                    formatted.append(str(int(round(float(value)))))
                elif isinstance(value, (float, np.floating)):
                    formatted.append(f"{value:.1f}")
                else:
                    formatted.append(str(value))
            display[column] = formatted
        self.current.append(display.to_html(index=False, escape=True, border=0))

    @contextmanager
    def _column(self, target):
        previous = self.current
        self.current = target
        try:
            yield
        finally:
            self.current = previous

    def columns(self, count):
        children = [[] for _ in range(count)]
        self.current.append(children)
        return [self._column(child) for child in children]

    def plotly_chart(self, figure, **kwargs):
        plot_id = f"plot-{len(self.plots)}"
        figure = go.Figure(figure)
        figure.update_xaxes(automargin=True)
        figure.update_yaxes(automargin=True)
        margin = figure.layout.margin.to_plotly_json()
        minimum = dict(l=55, r=25, t=45, b=55)
        if any(trace.type in {"scatterpolar", "barpolar"} for trace in figure.data):
            minimum = dict(l=45, r=45, t=40, b=40)
            figure.update_polars(radialaxis_title_text="")
        elif figure.layout.xaxis.visible is False and figure.layout.yaxis.visible is False:
            minimum = dict(l=15, r=15, t=20, b=40)
        figure.update_layout(margin={
            key: max(margin.get(key, 0), value) for key, value in minimum.items()
        })
        spec = figure.to_plotly_json()
        height = spec["layout"].get("height", 450)
        self.plots.append({"id": plot_id, "figure": spec})
        width = spec["layout"].get("width")
        sizing = f"width:{width}px;max-width:100%;margin:0 auto;" if width else ""
        self.current.append(f'<div class="plot" id="{plot_id}" style="{sizing}height:{height}px"></div>')

    def _render(self, nodes):
        parts = []
        for node in nodes:
            if isinstance(node, str):
                parts.append(node)
            else:
                columns = "".join(f'<div class="column">{self._render(child)}</div>' for child in node)
                parts.append(
                    f'<div class="columns" style="grid-template-columns:repeat({len(node)},1fr)">'
                    f"{columns}</div>"
                )
        return "".join(parts)

    def document(self):
        payload = json.dumps(self.plots, cls=PlotlyJSONEncoder).replace(
            "<", "\\u003c"
        ).replace(">", "\\u003e").replace("&", "\\u0026")
        return (
            '<!doctype html><html><head><meta charset="utf-8">'
            '<title>TrackMan Hitting Report</title>'
            f"<style>{REPORT_CSS}</style></head><body>"
            f'<main id="report">{self._render(self.root)}</main>'
            f"<script>{get_plotlyjs()}</script>"
            f'<script type="application/json" id="plot-specs">{payload}</script>'
            """<script>
window.reportReady = false;
const report = document.getElementById('report');
function fitReport() {
    const scale = Math.min(1, document.documentElement.clientWidth / 1400);
    report.style.transform = `scale(${scale})`;
    document.body.style.height = `${Math.ceil(report.offsetHeight * scale)}px`;
}
async function drawReport() {
    try {
        await document.fonts.ready;
        const specs = JSON.parse(document.getElementById('plot-specs').textContent);
        for (const {id, figure} of specs) {
            await Plotly.newPlot(id, figure.data, figure.layout, {
                displayModeBar: false, responsive: false, staticPlot: false
            });
        }
        fitReport();
        window.reportReady = true;
    } catch (error) {
        window.reportError = String(error);
    }
}
window.addEventListener('resize', fitReport);
drawReport();
</script></body></html>"""
        )


def build_report_html(data, source_name="", batter_side="Both", sheet_mode="both"):
    from dashboard_report import compose_report

    renderer = ReportHTML()
    id_col = "Hitter" if "Hitter" in data.columns else "Pitcher"
    hitters = data[id_col].dropna().unique() if id_col in data.columns else []
    identity = str(hitters[0]) if len(hitters) == 1 else f"{len(hitters)} hitters"
    height_info = ""
    if len(hitters) == 1 and "HitterHeightIn" in data.columns and data["HitterHeightIn"].notna().any():
        height_info = f" | Height: {format_height_ft_in(float(data['HitterHeightIn'].dropna().iloc[0]))}"
    details = f"{identity}{height_info} | {len(data)} pitches | Batter side: {batter_side}"
    if source_name:
        details += f" | Source: {source_name}"
    renderer.markdown(f'<p class="caption metadata">{escape(details)}</p>', unsafe_allow_html=True)
    compose_report(data, ui=renderer, sheet_mode=sheet_mode)
    return renderer.document()
