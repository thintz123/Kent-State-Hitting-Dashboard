"""Compose the interactive hitting dashboard and the separate At-Bat breakdown sheet."""

from html import escape
import pandas as pd
import streamlit as st

from dashboard_charts import (
    render_at_bat_cards,
    render_chase_quadrants_chart,
    render_contact_in_play_charts,
    render_heart_take_whiff_chart,
    render_plate_location,
)
from dashboard_stats import (
    at_bat_pitch_log_table,
    contact_in_play_table,
    fmt,
    hitting_overview_metrics,
    report_table,
)


def _render_kpi_cards(data: pd.DataFrame, ui=st) -> None:
    m = hitting_overview_metrics(data)
    cards = [
        (
            "Heart Swing %",
            fmt(m["heart_swing_pct"], "%"),
            f"{m['heart_swings']} swings / {m['heart_pitches']} pitches in Heart "
            f"({m['heart_takes']} takes, {fmt(m['heart_take_pct'], '%')})",
            "#2563eb",
        ),
        (
            "Heart Miss %",
            fmt(m["heart_miss_pct"], "%"),
            f"{m['heart_misses']} whiffs / {m['heart_swings']} Heart swings "
            f"({fmt(m['heart_miss_per_pitch_pct'], '%')} of Heart pitches)",
            "#dc2626",
        ),
        (
            "Swing & Miss %",
            fmt(m["swing_miss_pct"], "%"),
            f"{m['total_whiffs']} whiffs / {m['total_swings']} total swings "
            f"({fmt(m['swstr_pct'], '%')} SwStr)",
            "#ea580c",
        ),
        (
            "Chase %",
            fmt(m["chase_pct"], "%"),
            f"{m['chase_swings']} / {m['out_of_zone_pitches']} pitches out of zone",
            "#9333ea",
        ),
        (
            "Contact in Play (EV & LA)",
            f"{m['in_play_count']} BIP",
            f"Avg EV: {fmt(m['avg_exit_velo'], ' mph')} | "
            f"Max EV: {fmt(m['max_exit_velo'], ' mph')} | "
            f"Avg LA: {fmt(m['avg_launch_angle'], '°')}",
            "#16a34a",
        ),
    ]
    cards_html = "".join(
        f'<div class="kpi-card" style="border-top: 4px solid {color};">'
        f'<div class="kpi-label">{escape(label)}</div>'
        f'<div class="kpi-value">{escape(val)}</div>'
        f'<div class="kpi-sub">{escape(sub)}</div>'
        f"</div>"
        for label, val, sub, color in cards
    )
    ui.markdown(f'<div class="kpi-grid">{cards_html}</div>', unsafe_allow_html=True)


def compose_main_report(data: pd.DataFrame, ui=st) -> None:
    """Render Sheet 1: Hitters Report (Strike Zone, Heart Takes & Whiffs, Quadrant Chase, EV/LA & Spray Chart)."""
    table = report_table(data)
    ui.markdown(
        "<div class='report-title'><h1>Kent State Hitters Report</h1>"
        "<p>Strike Zone | Heart Takes &amp; Whiffs | Quadrant Chase | EV, Launch Angle &amp; Spray Chart</p></div>",
        unsafe_allow_html=True,
    )

    _render_kpi_cards(data, ui=ui)

    ui.subheader("Pitch Type Summary — Zone, Heart, Swing Decisions & Contact")
    ui.dataframe(
        table,
        hide_index=True,
        use_container_width=True,
        height=min(280, 42 + len(table) * 35),
    )

    location_col, heart_col = ui.columns(2)
    with location_col:
        render_plate_location(data, ui=ui)
    with heart_col:
        render_heart_take_whiff_chart(data, ui=ui)

    ui.subheader("Chase in Each Quadrant")
    render_chase_quadrants_chart(data, ui=ui)

    ui.subheader("Every Contact in Play — EV Spray Chart (Green=Good, Yellow=Solid, Red=Bad), EV & Launch Angle")
    render_contact_in_play_charts(data, ui=ui)

    bip_table = contact_in_play_table(data)
    if bip_table.empty:
        ui.info("No balls in play were recorded for the selected filters.")
    else:
        ui.dataframe(
            bip_table,
            hide_index=True,
            use_container_width=True,
            height=min(360, 42 + len(bip_table) * 35),
        )


def compose_at_bat_sheet(data: pd.DataFrame, ui=st) -> None:
    """Render Sheet 2: Every At-Bat Pitch Type (Velos), Count, and Location in Zone."""
    ui.markdown(
        "<div class='report-title sheet-break'><h1>At-Bat Pitch-by-Pitch Breakdown</h1>"
        "<p>Every At-Bat Pitch Type, Velocity, Count &amp; Zone/Heart Location</p></div>",
        unsafe_allow_html=True,
    )
    render_at_bat_cards(data, ui=ui)

    ui.subheader("Complete At-Bat Pitch Log")
    log_table = at_bat_pitch_log_table(data)
    if log_table.empty:
        ui.info("No pitch rows available for the selected filters.")
    else:
        ui.dataframe(
            log_table,
            hide_index=True,
            use_container_width=True,
            height=min(420, 42 + len(log_table) * 35),
        )


def compose_report(data: pd.DataFrame, ui=st, sheet_mode: str = "both") -> None:
    """Render the requested report sheet(s): 'main', 'at_bats', or 'both'."""
    if sheet_mode in {"main", "both"}:
        compose_main_report(data, ui=ui)
    if sheet_mode in {"at_bats", "both"}:
        compose_at_bat_sheet(data, ui=ui)


def render_report(
    data: pd.DataFrame,
    source_name: str = "",
    batter_side: str = "Both",
    sheet_mode: str = "both",
) -> None:
    """Display the same browser document used by the PDF exporter."""
    import streamlit.components.v1 as components
    from report_html import build_report_html

    components.html(
        build_report_html(data, source_name, batter_side, sheet_mode=sheet_mode),
        height=1050,
        scrolling=True,
    )
