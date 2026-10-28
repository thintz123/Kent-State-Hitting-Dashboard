"""Plotly strike-zone, octagonal heart (take & whiff), quadrant chase, EV/LA, and spray charts."""

from html import escape
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard_config import (
    DEFAULT_HITTER_HEIGHT_IN,
    EV_QUALITY_COLORS,
    GOOD_EV_MIN,
    PITCH_COLORS,
    SOLID_EV_MIN,
    format_height_ft_in,
    get_zone_and_heart_bounds,
    heart_octagon_svg_path,
)
from dashboard_stats import (
    build_at_bats,
    chase_by_quadrant_table,
    fmt,
    hitting_overview_metrics,
    pitch_summary,
)

LIGHT_MARKER_COLORS = {"#eab308", "yellow", "lime", "cyan", "#65a30d", "#facc15"}


def _resolve_plot_height_in(data: pd.DataFrame) -> float:
    if "HitterHeightIn" in data.columns and data["HitterHeightIn"].notna().any():
        return float(data["HitterHeightIn"].dropna().mean())
    return DEFAULT_HITTER_HEIGHT_IN


def add_zone_and_heart_shapes(
    fig: go.Figure,
    height_in: float | None = None,
    compact: bool = False,
    show_heart_label: bool = False,
    emphasize_heart: bool = False,
) -> go.Figure:
    """Draw the height-adjusted 3x3 strike zone, octagonal Heart zone, and home plate."""
    bounds = get_zone_and_heart_bounds(height_in)
    sz_x_min, sz_x_max = bounds["sz_x_min"], bounds["sz_x_max"]
    sz_y_min, sz_y_max = bounds["sz_y_min"], bounds["sz_y_max"]

    # Outer Strike Zone
    fig.add_shape(
        type="rect",
        x0=sz_x_min,
        x1=sz_x_max,
        y0=sz_y_min,
        y1=sz_y_max,
        line=dict(color="#111827", width=2.8 if not compact else 2.2),
        fillcolor="rgba(241, 245, 249, 0.50)",
        layer="below",
    )

    # 3x3 Strike Zone Grid Lines
    for x in [
        sz_x_min + (sz_x_max - sz_x_min) / 3.0,
        sz_x_min + 2.0 * (sz_x_max - sz_x_min) / 3.0,
    ]:
        fig.add_shape(
            type="line",
            x0=x,
            x1=x,
            y0=sz_y_min,
            y1=sz_y_max,
            line=dict(color="#475569", width=1.4 if not compact else 1.1),
            layer="below",
        )
    for y in [
        sz_y_min + (sz_y_max - sz_y_min) / 3.0,
        sz_y_min + 2.0 * (sz_y_max - sz_y_min) / 3.0,
    ]:
        fig.add_shape(
            type="line",
            x0=sz_x_min,
            x1=sz_x_max,
            y0=y,
            y1=y,
            line=dict(color="#475569", width=1.4 if not compact else 1.1),
            layer="below",
        )

    # Inner Octagonal (Chamfered-Corner) Heart Zone
    fig.add_shape(
        type="path",
        path=heart_octagon_svg_path(bounds),
        line=dict(
            color="#b91c1c" if emphasize_heart else "#dc2626",
            width=3.2 if emphasize_heart else (2.6 if not compact else 2.2),
        ),
        fillcolor="rgba(239, 68, 68, 0.22)" if emphasize_heart else "rgba(239, 68, 68, 0.15)",
        layer="below",
    )

    if show_heart_label:
        ht_label = format_height_ft_in(bounds["height_in"])
        fig.add_annotation(
            x=1.95,
            y=4.32,
            text=f"Zone Height: {ht_label}",
            showarrow=False,
            xanchor="right",
            yanchor="top",
            font=dict(size=10, color="#475569"),
            bgcolor="rgba(248, 250, 252, 0.90)",
            bordercolor="#cbd5e1",
            borderwidth=1,
            borderpad=3,
        )

    # Home Plate Pentagon
    fig.add_shape(
        type="path",
        path="M -0.71,0.55 L 0,0.35 L 0.71,0.55 L 0.52,0.75 L -0.52,0.75 Z",
        line=dict(color="#111827", width=2.5 if not compact else 2),
        fillcolor="white",
        layer="below",
    )
    return fig


def render_plate_location(data: pd.DataFrame, ui=st) -> None:
    """Render Strike Zone of where every pitch was and what pitch type it was."""
    plot_data = data.dropna(subset=["PlateLocSide", "PlateLocHeight"]).copy()
    height_in = _resolve_plot_height_in(data)
    fig = go.Figure()
    add_zone_and_heart_shapes(fig, height_in=height_in, show_heart_label=True)

    for pitch_type in plot_data["MappedPitchType"].dropna().unique():
        pitch_data = plot_data[plot_data["MappedPitchType"].eq(pitch_type)]
        custom = np.column_stack(
            [
                pitch_data["PitchCall"].fillna("-"),
                pitch_data["RelSpeed"].fillna(np.nan),
                pitch_data["Count"].fillna("-"),
                pitch_data["ZoneRegion"].fillna("-"),
            ]
        )
        fig.add_trace(
            go.Scatter(
                x=pitch_data["PlateLocSide"],
                y=pitch_data["PlateLocHeight"],
                mode="markers",
                marker=dict(
                    color=PITCH_COLORS.get(pitch_type, "#334155"),
                    size=11,
                    line=dict(color="#0f172a", width=1.2),
                ),
                name=pitch_type,
                customdata=custom,
                hovertemplate=(
                    "<b>%{fullData.name}</b><br>"
                    "Count: %{customdata[2]}<br>"
                    "Velo: %{customdata[1]:.1f} mph<br>"
                    "Zone: %{customdata[3]}<br>"
                    "Call: %{customdata[0]}<br>"
                    "Loc: (%{x:.2f}, %{y:.2f}) ft"
                    "<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        height=510,
        title=dict(text="Strike Zone — Every Pitch Location & Pitch Type", x=0.5, xanchor="center"),
        legend_title_text="",
        legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.20, font=dict(size=11)),
        margin=dict(l=45, r=20, t=45, b=85),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    fig.update_xaxes(
        title=dict(text="Horizontal location (ft, catcher's view)", standoff=10),
        range=[-2.2, 2.2],
        zeroline=False,
        showgrid=True,
        gridcolor="#f1f5f9",
        constrain="domain",
    )
    fig.update_yaxes(
        title="Vertical location (ft)",
        range=[0.25, 4.5],
        zeroline=False,
        showgrid=True,
        gridcolor="#f1f5f9",
        scaleanchor="x",
        scaleratio=1,
        constrain="domain",
    )
    ui.plotly_chart(fig, use_container_width=True)


def render_heart_take_whiff_chart(data: pd.DataFrame, ui=st) -> None:
    """Render separate chart for Heart of the Strike Zone: Takes & Whiffs."""
    plot_data = data.dropna(subset=["PlateLocSide", "PlateLocHeight"]).copy()
    height_in = _resolve_plot_height_in(data)
    fig = go.Figure()
    add_zone_and_heart_shapes(fig, height_in=height_in, show_heart_label=False, emphasize_heart=True)

    m = hitting_overview_metrics(data)
    heart_data = plot_data[plot_data["IsHeart"]].copy()

    if not heart_data.empty:
        conditions = [
            heart_data["IsHeartMiss"],
            heart_data["IsHeartTake"],
            heart_data["IsInPlay"],
            heart_data["IsHeartSwing"] & ~heart_data["IsHeartMiss"] & ~heart_data["IsInPlay"],
        ]
        choices = [
            "Heart Whiff (Miss)",
            "Heart Take",
            "Heart In Play",
            "Heart Foul",
        ]
        heart_data["HeartOutcome"] = np.select(conditions, choices, default="Heart Take")

        bucket_styles = [
            ("Heart Whiff (Miss)", dict(color="#dc2626", symbol="x", size=14)),
            ("Heart Take", dict(color="#2563eb", symbol="circle", size=12)),
            ("Heart In Play", dict(color="#16a34a", symbol="star", size=13)),
            ("Heart Foul", dict(color="#eab308", symbol="diamond", size=11)),
        ]
        for label, style in bucket_styles:
            sub = heart_data[heart_data["HeartOutcome"].eq(label)]
            if sub.empty:
                continue
            custom = np.column_stack(
                [
                    sub["MappedPitchType"].fillna("-"),
                    sub["RelSpeed"].fillna(np.nan),
                    sub["Count"].fillna("-"),
                    sub["PitchCall"].fillna("-"),
                ]
            )
            fig.add_trace(
                go.Scatter(
                    x=sub["PlateLocSide"],
                    y=sub["PlateLocHeight"],
                    mode="markers",
                    name=label,
                    marker=dict(
                        color=style["color"],
                        symbol=style["symbol"],
                        size=style["size"],
                        line=dict(color="#0f172a", width=1.3),
                    ),
                    customdata=custom,
                    hovertemplate=(
                        "<b>%{fullData.name}</b><br>"
                        "Pitch: %{customdata[0]} (%{customdata[1]:.1f} mph)<br>"
                        "Count: %{customdata[2]} | Call: %{customdata[3]}<br>"
                        "Loc: (%{x:.2f}, %{y:.2f}) ft"
                        "<extra></extra>"
                    ),
                )
            )

    summary_banner = (
        f"Heart Pitches: {m['heart_pitches']} | "
        f"Takes: {m['heart_takes']} ({fmt(m['heart_take_pct'], '%')}) | "
        f"Whiffs: {m['heart_misses']} ({fmt(m['heart_miss_pct'], '%')}) | "
        f"Heart Swing: {fmt(m['heart_swing_pct'], '%')}"
    )
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.98,
        text=f"<b>{summary_banner}</b>",
        showarrow=False,
        xanchor="center",
        yanchor="top",
        font=dict(size=10.5, color="#0f172a"),
        bgcolor="rgba(254, 242, 242, 0.94)",
        bordercolor="#dc2626",
        borderwidth=1,
        borderpad=4,
    )

    fig.update_layout(
        height=510,
        title=dict(
            text="Heart of the Strike Zone — Takes & Whiffs",
            x=0.5,
            xanchor="center",
        ),
        legend_title_text="",
        legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.20, font=dict(size=11)),
        margin=dict(l=45, r=20, t=45, b=85),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    fig.update_xaxes(
        title=dict(text="Horizontal location (ft, catcher's view)", standoff=10),
        range=[-2.2, 2.2],
        zeroline=False,
        showgrid=True,
        gridcolor="#f1f5f9",
        constrain="domain",
    )
    fig.update_yaxes(
        title="Vertical location (ft)",
        range=[0.25, 4.5],
        zeroline=False,
        showgrid=True,
        gridcolor="#f1f5f9",
        scaleanchor="x",
        scaleratio=1,
        constrain="domain",
    )
    ui.plotly_chart(fig, use_container_width=True)


def render_chase_quadrants_chart(data: pd.DataFrame, ui=st) -> None:
    """Render Chase in each of the 4 quadrants around the Strike Zone (chart + table)."""
    height_in = _resolve_plot_height_in(data)
    bounds = get_zone_and_heart_bounds(height_in)
    sz_y_min, sz_y_max = bounds["sz_y_min"], bounds["sz_y_max"]
    sz_mid_y = (sz_y_min + sz_y_max) / 2.0

    quad_table = chase_by_quadrant_table(data)
    quad_map = {
        row["Quadrant"]: row for _, row in quad_table.iterrows()
    }

    fig = go.Figure()
    fig.add_hline(y=sz_mid_y, line=dict(color="#64748b", width=1.8, dash="dash"))
    fig.add_vline(x=0.0, line=dict(color="#64748b", width=1.8, dash="dash"))

    add_zone_and_heart_shapes(fig, height_in=height_in, show_heart_label=False)

    ooz = data[data["IsOutOfZone"]].dropna(subset=["PlateLocSide", "PlateLocHeight"]).copy()
    if not ooz.empty:
        ooz["ChaseOutcome"] = np.select(
            [
                ooz["IsSwing"] & ooz["IsWhiff"],
                ooz["IsSwing"] & ~ooz["IsWhiff"],
            ],
            [
                "Chase — Whiff",
                "Chase — Foul / In Play",
            ],
            default="Out-of-Zone Take (Ball)",
        )
        styles = [
            ("Chase — Whiff", dict(color="#dc2626", symbol="x", size=12)),
            ("Chase — Foul / In Play", dict(color="#ea580c", symbol="diamond", size=11)),
            ("Out-of-Zone Take (Ball)", dict(color="#94a3b8", symbol="circle-open", size=9)),
        ]
        for label, style in styles:
            sub = ooz[ooz["ChaseOutcome"].eq(label)]
            if sub.empty:
                continue
            custom = np.column_stack(
                [
                    sub["MappedPitchType"].fillna("-"),
                    sub["RelSpeed"].fillna(np.nan),
                    sub["Count"].fillna("-"),
                    sub["Quadrant"].fillna("-"),
                ]
            )
            fig.add_trace(
                go.Scatter(
                    x=sub["PlateLocSide"],
                    y=sub["PlateLocHeight"],
                    mode="markers",
                    name=label,
                    marker=dict(
                        color=style["color"],
                        symbol=style["symbol"],
                        size=style["size"],
                        line=dict(color="#0f172a", width=1.2),
                    ),
                    customdata=custom,
                    hovertemplate=(
                        "<b>%{fullData.name}</b><br>"
                        "Quadrant: %{customdata[3]}<br>"
                        "Pitch: %{customdata[0]} (%{customdata[1]:.1f} mph)<br>"
                        "Count: %{customdata[2]}<br>"
                        "Loc: (%{x:.2f}, %{y:.2f}) ft"
                        "<extra></extra>"
                    ),
                )
            )

    quad_positions = [
        ("Up-Left", -1.45, 4.08),
        ("Up-Right", 1.45, 4.08),
        ("Down-Left", -1.45, 1.02),
        ("Down-Right", 1.45, 1.02),
    ]
    for q_name, qx, qy in quad_positions:
        row = quad_map.get(q_name, {})
        pitches = int(row.get("Out-of-Zone Pitches", 0))
        chases = int(row.get("Chases", 0))
        chase_pct = row.get("Chase %", np.nan)
        pct_str = f"{chase_pct:.1f}%" if pd.notna(chase_pct) else "-"
        fig.add_annotation(
            x=qx,
            y=qy,
            text=f"<b>{q_name}</b><br>Chase: <b>{pct_str}</b><br>({chases}/{pitches} pitches)",
            showarrow=False,
            font=dict(size=10.5, color="#1e293b"),
            bgcolor="rgba(248, 250, 252, 0.92)",
            bordercolor="#94a3b8",
            borderwidth=1,
            borderpad=4,
        )

    fig.update_layout(
        height=490,
        title=dict(text="Chase % in Each Quadrant (Out-of-Zone Pitches)", x=0.5, xanchor="center"),
        legend_title_text="",
        legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.20, font=dict(size=11)),
        margin=dict(l=45, r=20, t=45, b=85),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    fig.update_xaxes(
        title=dict(text="Horizontal location (ft, catcher's view)", standoff=10),
        range=[-2.25, 2.25],
        zeroline=False,
        showgrid=True,
        gridcolor="#f1f5f9",
        constrain="domain",
    )
    fig.update_yaxes(
        title="Vertical location (ft)",
        range=[0.25, 4.55],
        zeroline=False,
        showgrid=True,
        gridcolor="#f1f5f9",
        scaleanchor="x",
        scaleratio=1,
        constrain="domain",
    )

    chart_col, table_col = ui.columns(2)
    with chart_col:
        ui.plotly_chart(fig, use_container_width=True)
    with table_col:
        ui.subheader("Chase Breakdown by Quadrant")
        ui.dataframe(quad_table, hide_index=True, use_container_width=True)
        render_discipline_by_pitch_chart(data, ui=ui)


def render_discipline_by_pitch_chart(data: pd.DataFrame, ui=st) -> None:
    """Render grouped bar chart of Heart Swing %, Heart Miss %, Swing & Miss %, and Chase % by pitch type."""
    summary = pitch_summary(data)
    if summary.empty:
        return

    metrics = [
        ("Heart Swing %", "#2563eb"),
        ("Heart Miss %", "#dc2626"),
        ("Swing & Miss %", "#ea580c"),
        ("Chase %", "#9333ea"),
    ]
    fig = go.Figure()
    for col, color in metrics:
        vals = summary[col].fillna(0.0)
        labels = [f"{v:.0f}%" if pd.notna(raw) else "" for v, raw in zip(vals, summary[col])]
        fig.add_trace(
            go.Bar(
                x=summary["MappedPitchType"],
                y=vals,
                name=col,
                marker_color=color,
                text=labels,
                textposition="outside",
                textfont=dict(size=9),
                hovertemplate="%{x}<br>%{fullData.name}: %{y:.1f}%<extra></extra>",
            )
        )

    fig.update_layout(
        height=290,
        barmode="group",
        title=dict(
            text="Plate Discipline & Heart Zone Rates by Pitch Type",
            x=0.5,
            xanchor="center",
            y=0.97,
        ),
        yaxis=dict(title="Rate (%)", range=[0, 120], showgrid=True, gridcolor="#e2e8f0"),
        xaxis=dict(title="", tickangle=-20, tickfont=dict(size=10)),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=1.02, yanchor="bottom", font=dict(size=10)),
        margin=dict(l=45, r=15, t=72, b=55),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    ui.plotly_chart(fig, use_container_width=True)


def _outfield_wall_radius(angles_deg: np.ndarray) -> np.ndarray:
    """Smoothly interpolate the outfield wall distance (ft) through the 5 stadium dimensions:
    320 LF (-45°), 385 LC (-22.5°), 415 CF (0°), 355 RC (+22.5°), 320 RF (+45°).
    Uses monotonic Hermite cubic splines so the wall stays convex without polynomial overshoot.
    """
    ctrl_x = np.array([-45.0, -22.5, 0.0, 22.5, 45.0])
    ctrl_y = np.array([320.0, 385.0, 415.0, 355.0, 320.0])
    # Slopes at the 5 control points (zero slope at dead center 0°)
    slopes = np.array([3.2, 2.1, 0.0, -2.1, -1.4])

    result = np.empty_like(angles_deg, dtype=float)
    for idx, a in enumerate(angles_deg):
        a_clamped = float(np.clip(a, -45.0, 45.0))
        seg = int(np.clip(np.searchsorted(ctrl_x, a_clamped) - 1, 0, 3))
        x0, x1 = ctrl_x[seg], ctrl_x[seg + 1]
        y0, y1 = ctrl_y[seg], ctrl_y[seg + 1]
        m0, m1 = slopes[seg], slopes[seg + 1]
        h = x1 - x0
        t = (a_clamped - x0) / h
        h00 = 2 * t**3 - 3 * t**2 + 1
        h10 = t**3 - 2 * t**2 + t
        h01 = -2 * t**3 + 3 * t**2
        h11 = t**3 - t**2
        result[idx] = h00 * y0 + h10 * h * m0 + h01 * y1 + h11 * h * m1
    return result


def _smooth_corner(
    p_start: tuple[float, float],
    p_corner: tuple[float, float],
    p_end: tuple[float, float],
    steps: int = 12,
) -> list[tuple[float, float]]:
    """Quadratic Bezier fillet between p_start -> p_corner -> p_end."""
    t_vals = np.linspace(0.0, 1.0, steps)
    return [
        (
            float((1 - t) ** 2 * p_start[0] + 2 * (1 - t) * t * p_corner[0] + t ** 2 * p_end[0]),
            float((1 - t) ** 2 * p_start[1] + 2 * (1 - t) * t * p_corner[1] + t ** 2 * p_end[1]),
        )
        for t in t_vals
    ]


def _build_stadium_shapes() -> list[dict[str, object]]:
    """Build SVG paths for the baseball field with 320 LF, 385 LC, 415 CF, 355 RC, 320 RF."""
    def _stadium_closed_path(offset: float = 0.0) -> str:
        pts: list[tuple[float, float]] = []
        d_foul = 22.0 + offset
        shift = d_foul * np.sqrt(2.0)

        # Outfield wall profile from -41° through LC (-22.5°), CF (0°), RC (+22.5°) to +41°
        wall_angles = np.linspace(-41.0, 41.0, 83)
        wall_radii = _outfield_wall_radius(wall_angles) + offset
        wall_pts = [
            (float(r_out * np.sin(np.radians(a))), float(r_out * np.cos(np.radians(a))))
            for a, r_out in zip(wall_angles, wall_radii)
        ]

        # Left foul-territory line: y = -x - shift, meeting the LF corner smoothly
        lf_line_top = (-205.0 - 0.7 * offset, 205.0 + 0.7 * offset - shift)
        lf_corner_ctrl = (-236.0 - 0.85 * offset, 224.0 + 0.65 * offset)
        pts.extend(_smooth_corner(lf_line_top, lf_corner_ctrl, wall_pts[0], steps=14))

        # Outfield wall curve
        pts.extend(wall_pts[1:-1])

        # Right foul-territory line: y = x - shift, meeting the RF corner smoothly
        rf_line_top = (205.0 + 0.7 * offset, 205.0 + 0.7 * offset - shift)
        rf_corner_ctrl = (236.0 + 0.85 * offset, 224.0 + 0.65 * offset)
        pts.extend(_smooth_corner(wall_pts[-1], rf_corner_ctrl, rf_line_top, steps=14))

        # Rounded backstop behind home plate
        for a in np.linspace(-45.0, -135.0, 25):
            rad = np.radians(a)
            pts.append((float(d_foul * np.cos(rad)), float(-6.0 + d_foul * np.sin(rad))))

        first = f"M {pts[0][0]:.2f},{pts[0][1]:.2f}"
        rest = " ".join(f"L {x:.2f},{y:.2f}" for x, y in pts[1:])
        return f"{first} {rest} Z"

    outer_wall_path = _stadium_closed_path(offset=16.0)
    turf_path = _stadium_closed_path(offset=0.0)

    mound_y = 60.5
    r_infield = 95.0
    max_alpha = float(np.degrees(np.arctan2(89.20, 93.20 - mound_y)))
    arc_angles = np.linspace(-max_alpha, max_alpha, 61)
    dirt_pts = [(-3.8, 0.0), (-89.20, 93.20)]
    for a in arc_angles:
        rad = np.radians(a)
        dirt_pts.append((r_infield * np.sin(rad), mound_y + r_infield * np.cos(rad)))
    dirt_pts.extend([(89.20, 93.20), (3.8, 0.0)])
    dirt_path = (
        f"M {dirt_pts[0][0]:.2f},{dirt_pts[0][1]:.2f} "
        + " ".join(f"L {x:.2f},{y:.2f}" for x, y in dirt_pts[1:])
        + " Z"
    )

    inner_grass_path = "M 0,13.5 L 51.5,63.64 L 0,113.8 L -51.5,63.64 Z"
    foul_x = 320.0 * np.sin(np.radians(45.0))
    foul_y = 320.0 * np.cos(np.radians(45.0))

    return [
        dict(
            type="path",
            path=outer_wall_path,
            fillcolor="white",
            line=dict(color="#e2e8f0", width=1.8),
            layer="below",
        ),
        dict(
            type="path",
            path=turf_path,
            fillcolor="#a8dad7",
            line=dict(color="#a8dad7", width=1),
            layer="below",
        ),
        dict(
            type="path",
            path=dirt_path,
            fillcolor="white",
            line=dict(color="white", width=1),
            layer="below",
        ),
        dict(
            type="path",
            path=inner_grass_path,
            fillcolor="#a8dad7",
            line=dict(color="white", width=1.5),
            layer="below",
        ),
        dict(
            type="circle",
            x0=-9,
            x1=9,
            y0=51.5,
            y1=69.5,
            fillcolor="white",
            line=dict(color="#dcdcdc", width=1),
            layer="below",
        ),
        dict(
            type="line",
            x0=-2.5,
            y0=60.5,
            x1=2.5,
            y1=60.5,
            line=dict(color="#b8c2cc", width=2),
            layer="below",
        ),
        dict(
            type="circle",
            x0=-13,
            x1=13,
            y0=-13,
            y1=13,
            fillcolor="white",
            line=dict(color="#dcdcdc", width=1),
            layer="below",
        ),
        dict(
            type="line",
            x0=-9.2,
            y0=9.2,
            x1=-foul_x,
            y1=foul_y,
            line=dict(color="#b8c2cc", width=1.6),
            layer="below",
        ),
        dict(
            type="line",
            x0=9.2,
            y0=9.2,
            x1=foul_x,
            y1=foul_y,
            line=dict(color="#b8c2cc", width=1.6),
            layer="below",
        ),
        dict(
            type="path",
            path="M 0,123.5 L 3.8,127.3 L 0,131.1 L -3.8,127.3 Z",
            fillcolor="#b8c2cc",
            line=dict(width=0),
            layer="below",
        ),
        dict(
            type="path",
            path="M 55.5,63.6 L 59.0,67.1 L 62.5,63.6 L 59.0,60.1 Z",
            fillcolor="#b8c2cc",
            line=dict(width=0),
            layer="below",
        ),
        dict(
            type="path",
            path="M -55.5,63.6 L -59.0,67.1 L -62.5,63.6 L -59.0,60.1 Z",
            fillcolor="#b8c2cc",
            line=dict(width=0),
            layer="below",
        ),
    ]


def build_spray_chart_figure(data: pd.DataFrame) -> go.Figure:
    """Build a Spray Chart of all batted balls colored by Exit Velocity quality (Green=Good, Yellow=Solid, Red=Bad)."""
    in_play = data[data["IsInPlay"]].dropna(subset=["SprayX", "SprayY"]).copy()
    fig = go.Figure()

    distance_annotations = [
        dict(x=-262, y=218, text="<b>320</b>"),
        dict(x=-164, y=382, text="<b>385</b>"),
        dict(x=0, y=442, text="<b>415</b>"),
        dict(x=154, y=354, text="<b>355</b>"),
        dict(x=262, y=218, text="<b>320</b>"),
    ]
    annotations = [
        dict(
            x=item["x"],
            y=item["y"],
            text=item["text"],
            showarrow=False,
            font=dict(size=15, color="#a8dad7", family="Arial Narrow, Arial"),
        )
        for item in distance_annotations
    ]

    if not in_play.empty:
        quality_order = [
            ("Good (95+ mph)", EV_QUALITY_COLORS["Good (95+ mph)"], 13),
            ("Solid (80–94.9 mph)", EV_QUALITY_COLORS["Solid (80–94.9 mph)"], 12),
            ("Bad (<80 mph)", EV_QUALITY_COLORS["Bad (<80 mph)"], 11),
        ]
        for q_label, color, size in quality_order:
            sub = in_play[in_play["EVQuality"].eq(q_label)]
            if sub.empty:
                continue
            custom = np.column_stack(
                [
                    sub["ExitSpeed"].fillna(np.nan),
                    sub["Angle"].fillna(np.nan),
                    sub["Distance"].fillna(np.nan),
                    sub["PlayResult"].replace("Undefined", "In Play").fillna("In Play"),
                    sub["TaggedHitType"].replace("Undefined", "-").fillna("-"),
                    sub["MappedPitchType"].fillna("-"),
                    sub["RelSpeed"].fillna(np.nan),
                ]
            )
            fig.add_trace(
                go.Scatter(
                    x=sub["SprayX"],
                    y=sub["SprayY"],
                    mode="markers",
                    name=q_label,
                    marker=dict(
                        color=color,
                        size=size,
                        line=dict(color="#111827", width=1.5),
                    ),
                    customdata=custom,
                    hovertemplate=(
                        "<b>%{fullData.name}</b> — %{customdata[3]}<br>"
                        "Exit Velo: %{customdata[0]:.1f} mph | LA: %{customdata[1]:.1f}°<br>"
                        "Distance: %{customdata[2]:.0f} ft (%{customdata[4]})<br>"
                        "Pitch: %{customdata[5]} (%{customdata[6]:.1f} mph)"
                        "<extra></extra>"
                    ),
                )
            )

    fig.update_layout(
        height=470,
        title=dict(
            text="Batted Ball Spray Chart (by EV)",
            x=0.5,
            xanchor="center",
            font=dict(size=15),
        ),
        shapes=_build_stadium_shapes(),
        annotations=annotations,
        legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.10, font=dict(size=10.5)),
        margin=dict(l=15, r=15, t=45, b=60),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    fig.update_xaxes(
        visible=False,
        range=[-315, 315],
        fixedrange=False,
        constrain="domain",
    )
    fig.update_yaxes(
        visible=False,
        range=[-65, 475],
        scaleanchor="x",
        scaleratio=1,
        fixedrange=False,
        constrain="domain",
    )
    return fig


def render_contact_in_play_charts(data: pd.DataFrame, ui=st) -> None:
    """Render EV-colored Spray Chart, Exit Velocity vs. Launch Angle scatterplot, and In-Play Zone locations."""
    in_play = data[data["IsInPlay"]].copy()
    height_in = _resolve_plot_height_in(data)
    spray_col, ev_la_col, zone_col = ui.columns(3)

    with spray_col:
        ui.plotly_chart(build_spray_chart_figure(data), use_container_width=True)

    with ev_la_col:
        fig = go.Figure()
        fig.add_shape(
            type="rect",
            x0=GOOD_EV_MIN,
            x1=120,
            y0=8,
            y1=32,
            fillcolor="rgba(22, 163, 74, 0.12)",
            line=dict(color="rgba(22, 163, 74, 0.4)", width=1, dash="dot"),
            layer="below",
        )
        fig.add_hline(y=8, line_dash="dash", line_color="#16a34a", line_width=1)
        fig.add_hline(y=32, line_dash="dash", line_color="#16a34a", line_width=1)
        fig.add_vline(x=GOOD_EV_MIN, line_dash="dash", line_color="#16a34a", line_width=1.5)
        fig.add_vline(x=SOLID_EV_MIN, line_dash="dot", line_color="#eab308", line_width=1.5)

        valid_ev_la = in_play.dropna(subset=["ExitSpeed", "Angle"]).copy()
        show_ev_text = len(valid_ev_la) <= 6
        if not valid_ev_la.empty:
            for q_label, color in EV_QUALITY_COLORS.items():
                sub = valid_ev_la[valid_ev_la["EVQuality"].eq(q_label)]
                if sub.empty:
                    continue
                labels = [
                    f"{ev:.1f} mph | {la:.1f}°"
                    for ev, la in zip(sub["ExitSpeed"], sub["Angle"])
                ]
                custom = np.column_stack(
                    [
                        sub["PlayResult"].replace("Undefined", "In Play").fillna("In Play"),
                        sub["MappedPitchType"].fillna("-"),
                        sub["RelSpeed"].fillna(np.nan),
                        sub["Count"].fillna("-"),
                        sub["TaggedHitType"].replace("Undefined", "-").fillna("-"),
                    ]
                )
                fig.add_trace(
                    go.Scatter(
                        x=sub["ExitSpeed"],
                        y=sub["Angle"],
                        mode="markers+text" if show_ev_text else "markers",
                        name=q_label,
                        text=labels if show_ev_text else None,
                        textposition="top center",
                        textfont=dict(size=9.5, color="#1e293b"),
                        marker=dict(
                            color=color,
                            size=12,
                            line=dict(color="#0f172a", width=1.3),
                        ),
                        customdata=custom,
                        hovertemplate=(
                            "<b>%{fullData.name}</b> — %{customdata[0]}<br>"
                            "Exit Velo: %{x:.1f} mph | Launch Angle: %{y:.1f}°<br>"
                            "Hit Type: %{customdata[4]}<br>"
                            "Pitch: %{customdata[1]} (%{customdata[2]:.1f} mph) | Count: %{customdata[3]}"
                            "<extra></extra>"
                        ),
                    )
                )

        min_ev = float(valid_ev_la["ExitSpeed"].min()) - 5 if not valid_ev_la.empty else 55
        max_ev = float(valid_ev_la["ExitSpeed"].max()) + 8 if not valid_ev_la.empty else 115
        fig.update_layout(
            height=470,
            title=dict(
                text="Exit Velocities (EV) & Launch Angle (°)",
                x=0.5,
                xanchor="center",
                font=dict(size=15),
            ),
            xaxis=dict(
                title=dict(text="Exit Velocity (mph)", standoff=10),
                range=[min(60, min_ev), max(112, max_ev)],
                showgrid=True,
                gridcolor="#e2e8f0",
            ),
            yaxis=dict(
                title="Launch Angle (°)",
                range=[-45, 75],
                showgrid=True,
                gridcolor="#e2e8f0",
                zeroline=True,
                zerolinecolor="#94a3b8",
            ),
            legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.22, font=dict(size=10.5)),
            margin=dict(l=45, r=20, t=45, b=85),
            paper_bgcolor="white",
            plot_bgcolor="white",
        )
        ui.plotly_chart(fig, use_container_width=True)

    with zone_col:
        fig_zone = go.Figure()
        add_zone_and_heart_shapes(fig_zone, height_in=height_in, show_heart_label=False)
        loc_in_play = in_play.dropna(subset=["PlateLocSide", "PlateLocHeight"]).copy()
        show_zone_text = len(loc_in_play) <= 5
        if not loc_in_play.empty:
            for q_label, color in EV_QUALITY_COLORS.items():
                sub = loc_in_play[loc_in_play["EVQuality"].eq(q_label)]
                if sub.empty:
                    continue
                labels = [
                    f"{ev:.1f} mph / {la:.1f}°"
                    if pd.notna(ev) and pd.notna(la)
                    else (f"{ev:.1f} mph" if pd.notna(ev) else "In Play")
                    for ev, la in zip(sub["ExitSpeed"], sub["Angle"])
                ]
                custom = np.column_stack(
                    [
                        sub["PlayResult"].replace("Undefined", "In Play").fillna("In Play"),
                        sub["MappedPitchType"].fillna("-"),
                        sub["RelSpeed"].fillna(np.nan),
                        sub["Count"].fillna("-"),
                        sub["ZoneRegion"].fillna("-"),
                        sub["ExitSpeed"].fillna(np.nan),
                        sub["Angle"].fillna(np.nan),
                    ]
                )
                fig_zone.add_trace(
                    go.Scatter(
                        x=sub["PlateLocSide"],
                        y=sub["PlateLocHeight"],
                        mode="markers+text" if show_zone_text else "markers",
                        name=q_label,
                        text=labels if show_zone_text else None,
                        textposition="top center",
                        textfont=dict(size=9, color="#0f172a"),
                        marker=dict(
                            color=color,
                            size=12,
                            symbol="star",
                            line=dict(color="#0f172a", width=1.2),
                        ),
                        customdata=custom,
                        hovertemplate=(
                            "<b>%{fullData.name}</b> — %{customdata[0]}<br>"
                            "EV: %{customdata[5]:.1f} mph | LA: %{customdata[6]:.1f}°<br>"
                            "Pitch: %{customdata[1]} (%{customdata[2]:.1f} mph)<br>"
                            "Count: %{customdata[3]} | %{customdata[4]}"
                            "<extra></extra>"
                        ),
                    )
                )

        fig_zone.update_layout(
            height=470,
            title=dict(
                text="Contact in Play — Zone Location",
                x=0.5,
                xanchor="center",
                font=dict(size=15),
            ),
            legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.22, font=dict(size=10.5)),
            margin=dict(l=45, r=20, t=45, b=85),
            paper_bgcolor="white",
            plot_bgcolor="white",
        )
        fig_zone.update_xaxes(
            title=dict(text="Horizontal location (ft, catcher's view)", standoff=10),
            range=[-2.2, 2.2],
            zeroline=False,
            showgrid=True,
            gridcolor="#f1f5f9",
            constrain="domain",
        )
        fig_zone.update_yaxes(
            title="Vertical location (ft)",
            range=[0.25, 4.5],
            zeroline=False,
            showgrid=True,
            gridcolor="#f1f5f9",
            scaleanchor="x",
            scaleratio=1,
            constrain="domain",
        )
        ui.plotly_chart(fig_zone, use_container_width=True)


def _deoverlap_at_bat_positions(
    xs: np.ndarray,
    ys: np.ndarray,
    min_dist: float = 0.25,
) -> tuple[np.ndarray, np.ndarray]:
    """Slightly separate numbered pitch markers within an At-Bat so numbers never overlap."""
    adj_x = xs.astype(float).copy()
    adj_y = ys.astype(float).copy()
    n = len(adj_x)
    if n <= 1:
        return adj_x, adj_y

    for _ in range(12):
        moved = False
        for i in range(n):
            for j in range(i + 1, n):
                dx = adj_x[j] - adj_x[i]
                dy = adj_y[j] - adj_y[i]
                dist = float(np.hypot(dx, dy))
                if dist < min_dist:
                    if dist < 1e-4:
                        angle = (j - i) * (np.pi / 3.0)
                        ux, uy = float(np.cos(angle)), float(np.sin(angle))
                    else:
                        ux, uy = dx / dist, dy / dist
                    push = 0.52 * (min_dist - dist)
                    adj_x[i] -= ux * push
                    adj_y[i] -= uy * push
                    adj_x[j] += ux * push
                    adj_y[j] += uy * push
                    moved = True
        if not moved:
            break
    return adj_x, adj_y


def build_at_bat_zone_figure(ab: dict[str, object]) -> go.Figure:
    """Build a compact Zone with Octagonal Heart plot for a single At-Bat with numbered pitches."""
    pitches: pd.DataFrame = ab["pitches"]
    located = pitches.dropna(subset=["PlateLocSide", "PlateLocHeight"]).copy()
    height_in = _resolve_plot_height_in(pitches)

    fig = go.Figure()
    add_zone_and_heart_shapes(fig, height_in=height_in, compact=True, show_heart_label=False)

    if not located.empty:
        adj_x, adj_y = _deoverlap_at_bat_positions(
            located["PlateLocSide"].to_numpy(),
            located["PlateLocHeight"].to_numpy(),
            min_dist=0.38,
        )
        located["PlotX"] = adj_x
        located["PlotY"] = adj_y

        for pitch_type in located["MappedPitchType"].dropna().unique():
            sub = located[located["MappedPitchType"].eq(pitch_type)]
            bg_color = PITCH_COLORS.get(pitch_type, "#334155")
            text_color = "#0f172a" if str(bg_color).lower() in LIGHT_MARKER_COLORS else "white"
            custom = np.column_stack(
                [
                    sub["PitchInAB"].astype(int),
                    sub["Count"].fillna("-"),
                    sub["RelSpeed"].fillna(np.nan),
                    sub["OutcomeLabel"].fillna("-"),
                    sub["ZoneRegion"].fillna("-"),
                    sub["PlateLocSide"].fillna(np.nan),
                    sub["PlateLocHeight"].fillna(np.nan),
                ]
            )
            fig.add_trace(
                go.Scatter(
                    x=sub["PlotX"],
                    y=sub["PlotY"],
                    mode="markers+text",
                    name=pitch_type,
                    text=sub["PitchInAB"].astype(int).astype(str),
                    textposition="middle center",
                    textfont=dict(color=text_color, size=10.5, family="Arial Black, Arial"),
                    marker=dict(
                        color=bg_color,
                        size=21,
                        line=dict(color="#0f172a", width=1.6),
                    ),
                    customdata=custom,
                    hovertemplate=(
                        "<b>Pitch #%{customdata[0]} — %{fullData.name}</b><br>"
                        "Count: %{customdata[1]}<br>"
                        "Velo: %{customdata[2]:.1f} mph<br>"
                        "Zone: %{customdata[4]}<br>"
                        "Coords: (%{customdata[5]:.2f}, %{customdata[6]:.2f}) ft<br>"
                        "Result: %{customdata[3]}"
                        "<extra></extra>"
                    ),
                )
            )

    fig.update_layout(
        height=355,
        showlegend=True,
        title=dict(
            text="Pitch Sequence in Zone & Heart",
            x=0.5,
            xanchor="center",
            y=0.97,
            font=dict(size=13),
        ),
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=1.01,
            yanchor="bottom",
            font=dict(size=10.5),
        ),
        margin=dict(l=40, r=20, t=58, b=45),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    fig.update_xaxes(
        title=dict(text="Horizontal (ft, catcher's view)", standoff=8, font=dict(size=11)),
        range=[-2.15, 2.15],
        zeroline=False,
        showgrid=True,
        gridcolor="#f1f5f9",
        constrain="domain",
    )
    fig.update_yaxes(
        title=dict(text="Vertical (ft)", font=dict(size=11)),
        range=[0.25, 4.4],
        zeroline=False,
        showgrid=True,
        gridcolor="#f1f5f9",
        scaleanchor="x",
        scaleratio=1,
        constrain="domain",
    )
    return fig


def format_single_ab_table(pitches: pd.DataFrame) -> pd.DataFrame:
    """Format pitch sequence table for one At-Bat."""
    rows = []
    for _, row in pitches.iterrows():
        ev = row.get("ExitSpeed")
        la = row.get("Angle")
        contact_str = (
            f"{ev:.1f} mph / {la:.1f}°"
            if pd.notna(ev) and pd.notna(la)
            else (f"{ev:.1f} mph" if pd.notna(ev) else "-")
        )
        rows.append(
            {
                "Pitch #": int(row["PitchInAB"]),
                "Count": str(row.get("Count", "-")),
                "Pitch Type": str(row.get("MappedPitchType", "Other")),
                "Velo (mph)": round(float(row["RelSpeed"]), 1)
                if pd.notna(row.get("RelSpeed"))
                else np.nan,
                "Location": str(row.get("ZoneRegion", "Unlocated")),
                "Call / Result": str(row.get("OutcomeLabel", "-")),
                "Contact (EV / LA)": contact_str,
            }
        )
    return pd.DataFrame(rows)


def render_at_bat_cards(data: pd.DataFrame, ui=st) -> None:
    """Render every At-Bat with its full-width header, Zone-with-Heart pitch map, and sequence table."""
    at_bats = build_at_bats(data)
    if not at_bats:
        ui.info("No at-bats are available for the selected filters.")
        return

    for ab in at_bats:
        header_html = (
            f'<div class="ab-card-header">'
            f'<span><b>AB #{ab["ab_number"]}</b> &bull; {escape(str(ab["inning"]))}</span>'
            f'<span>{escape(str(ab["hitter"]))} ({escape(str(ab["batter_side"]))}) '
            f'vs. {escape(str(ab["pitcher"]))} ({escape(str(ab["pitcher_throws"]))})</span>'
            f'<span class="ab-outcome">Outcome: <b>{escape(str(ab["result"]))}</b></span>'
            f"</div>"
        )
        ui.markdown(header_html, unsafe_allow_html=True)
        zone_col, table_col = ui.columns(2)
        with zone_col:
            ui.plotly_chart(build_at_bat_zone_figure(ab), use_container_width=True)
        with table_col:
            ab_table = format_single_ab_table(ab["pitches"])
            ui.dataframe(ab_table, hide_index=True, use_container_width=True)


def report_chart_layout(fig: go.Figure, height: int = 300) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=25, r=20, t=45, b=30),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(size=11),
        showlegend=False,
    )
    return fig
