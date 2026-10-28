"""Pitch classification, plate-discipline metrics, contact in play, and at-bat breakdowns."""

import numpy as np
import pandas as pd

from dashboard_config import CHASE_QUADRANTS, PITCH_CATEGORY_SETS, PITCH_COLORS, TAGGED_DATA_THRESHOLD


def rate(numerator: pd.Series | int | float, denominator: int | float) -> float:
    num = float(numerator.sum()) if hasattr(numerator, "sum") else float(numerator)
    return float(num / denominator) if denominator else np.nan


def fmt(value: float, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{value:.1f}{suffix}"


def classify_pitch_types(data: pd.DataFrame) -> tuple[bool, dict[str, set[str]]]:
    """Classify known pitch labels and determine whether tags are sufficiently complete."""
    tagged = data["TaggedPitchType"].fillna("Other")
    tagged_ratio = tagged.ne("Other").mean()
    return tagged_ratio >= TAGGED_DATA_THRESHOLD, PITCH_CATEGORY_SETS


def get_pitch_color_map_and_types(
    data: pd.DataFrame,
) -> tuple[dict[str, str], pd.DataFrame]:
    """Map pitch labels to detailed types or broad categories based on tag coverage."""
    sufficient_tagged_data, pitch_types = classify_pitch_types(data)
    data = data.copy()

    if sufficient_tagged_data:
        color_map = dict(PITCH_COLORS)
        data["MappedPitchType"] = data["TaggedPitchType"]
    else:
        color_map = {
            "Fastball": PITCH_COLORS["Fastball"],
            "Offspeed": PITCH_COLORS["Offspeed"],
            "Breaking": PITCH_COLORS["Breaking"],
            "Other": PITCH_COLORS["Other"],
        }
        pitch_to_category = {
            pitch: category
            for category, pitches in pitch_types.items()
            for pitch in pitches
        }
        data["MappedPitchType"] = (
            data["TaggedPitchType"]
            .where(data["TaggedPitchType"].ne("Other"), data["AutoPitchType"])
            .map(pitch_to_category)
            .fillna("Other")
        )

    return color_map, data


def tilt_to_minutes(tilt_time: object) -> int | None:
    """Convert a clock-formatted tilt value to modular 12-hour minutes."""
    if hasattr(tilt_time, "hour") and hasattr(tilt_time, "minute"):
        hours = tilt_time.hour
        minutes = tilt_time.minute
    elif isinstance(tilt_time, str) and ":" in tilt_time:
        try:
            hours, minutes = map(int, tilt_time.split(":")[:2])
        except ValueError:
            return None
    else:
        return None

    if not 0 <= minutes < 60 or not 0 <= hours <= 23:
        return None
    return (0 if hours == 12 else hours) * 60 + minutes


def minutes_to_tilt(total_minutes: int | None) -> str | None:
    """Convert modular 12-hour minutes back to a clock-formatted tilt."""
    if total_minutes is None:
        return None
    hours = (total_minutes // 60) % 12
    minutes = total_minutes % 60
    return f"{12 if hours == 0 else hours}:{minutes:02d}"


def average_tilt(tilt_values: list[object]) -> str | None:
    """Compute a circular average tilt rounded to the nearest 15 minutes."""
    angles = []
    for tilt in tilt_values:
        minutes = tilt_to_minutes(tilt)
        if minutes is not None:
            angle = (minutes / (12 * 60)) * 2 * np.pi
            angles.append(angle)

    if not angles:
        return None

    mean_x = np.mean(np.cos(angles))
    mean_y = np.mean(np.sin(angles))
    average_angle = np.arctan2(mean_y, mean_x) % (2 * np.pi)
    average_minutes = (average_angle / (2 * np.pi)) * (12 * 60)
    rounded_minutes = int(round(average_minutes / 15.0) * 15)
    return minutes_to_tilt(rounded_minutes)


def hitting_overview_metrics(data: pd.DataFrame) -> dict[str, object]:
    """Calculate headline plate-discipline, heart-zone, and contact metrics."""
    total_pitches = int(len(data))
    located_pitches = int(data["HasLocation"].sum()) if "HasLocation" in data else 0
    zone_pitches = int(data["IsZone"].sum()) if "IsZone" in data else 0
    heart_pitches = int(data["IsHeart"].sum()) if "IsHeart" in data else 0
    out_of_zone_pitches = int(data["IsOutOfZone"].sum()) if "IsOutOfZone" in data else 0

    total_swings = int(data["IsSwing"].sum()) if "IsSwing" in data else 0
    total_whiffs = int(data["IsWhiff"].sum()) if "IsWhiff" in data else 0
    heart_swings = int(data["IsHeartSwing"].sum()) if "IsHeartSwing" in data else 0
    heart_misses = int(data["IsHeartMiss"].sum()) if "IsHeartMiss" in data else 0
    heart_takes = int(data["IsHeartTake"].sum()) if "IsHeartTake" in data else max(0, heart_pitches - heart_swings)
    chase_swings = int(data["IsChase"].sum()) if "IsChase" in data else 0
    in_play_count = int(data["IsInPlay"].sum()) if "IsInPlay" in data else 0

    in_play_data = data[data["IsInPlay"]] if "IsInPlay" in data else data.iloc[0:0]
    ev_series = in_play_data["ExitSpeed"].dropna() if "ExitSpeed" in in_play_data else pd.Series(dtype=float)
    la_series = in_play_data["Angle"].dropna() if "Angle" in in_play_data else pd.Series(dtype=float)

    return {
        "total_pitches": total_pitches,
        "located_pitches": located_pitches,
        "zone_pitches": zone_pitches,
        "heart_pitches": heart_pitches,
        "out_of_zone_pitches": out_of_zone_pitches,
        "total_swings": total_swings,
        "total_whiffs": total_whiffs,
        "heart_swings": heart_swings,
        "heart_misses": heart_misses,
        "heart_takes": heart_takes,
        "chase_swings": chase_swings,
        "in_play_count": in_play_count,
        "zone_pct": (zone_pitches / located_pitches * 100.0) if located_pitches else np.nan,
        "heart_pct": (heart_pitches / located_pitches * 100.0) if located_pitches else np.nan,
        "heart_swing_pct": (heart_swings / heart_pitches * 100.0) if heart_pitches else np.nan,
        "heart_take_pct": (heart_takes / heart_pitches * 100.0) if heart_pitches else np.nan,
        "heart_miss_pct": (heart_misses / heart_swings * 100.0) if heart_swings else np.nan,
        "heart_miss_per_pitch_pct": (heart_misses / heart_pitches * 100.0) if heart_pitches else np.nan,
        "swing_miss_pct": (total_whiffs / total_swings * 100.0) if total_swings else np.nan,
        "swstr_pct": (total_whiffs / total_pitches * 100.0) if total_pitches else np.nan,
        "chase_pct": (chase_swings / out_of_zone_pitches * 100.0) if out_of_zone_pitches else np.nan,
        "avg_exit_velo": float(ev_series.mean()) if not ev_series.empty else np.nan,
        "max_exit_velo": float(ev_series.max()) if not ev_series.empty else np.nan,
        "avg_launch_angle": float(la_series.mean()) if not la_series.empty else np.nan,
    }


def chase_by_quadrant_table(data: pd.DataFrame) -> pd.DataFrame:
    """Summarize out-of-zone pitches, swings (chases), takes, and Chase % in each of the 4 quadrants."""
    ooz = data[data["IsOutOfZone"]].copy() if "IsOutOfZone" in data.columns else data.iloc[0:0]
    rows = []
    for quad in CHASE_QUADRANTS:
        sub = ooz[ooz["Quadrant"].eq(quad)] if "Quadrant" in ooz.columns else ooz.iloc[0:0]
        pitches = int(len(sub))
        chases = int(sub["IsSwing"].sum()) if pitches else 0
        takes = pitches - chases
        whiffs = int(sub["IsWhiff"].sum()) if pitches else 0
        rows.append(
            {
                "Quadrant": quad,
                "Out-of-Zone Pitches": pitches,
                "Chases": chases,
                "Takes": takes,
                "Chase %": round(chases / pitches * 100.0, 1) if pitches else np.nan,
                "Chase Whiff %": round(whiffs / chases * 100.0, 1) if chases else np.nan,
            }
        )
    tot_pitches = int(len(ooz))
    tot_chases = int(ooz["IsSwing"].sum()) if tot_pitches else 0
    tot_whiffs = int(ooz["IsWhiff"].sum()) if tot_pitches else 0
    rows.append(
        {
            "Quadrant": "Total Out of Zone",
            "Out-of-Zone Pitches": tot_pitches,
            "Chases": tot_chases,
            "Takes": tot_pitches - tot_chases,
            "Chase %": round(tot_chases / tot_pitches * 100.0, 1) if tot_pitches else np.nan,
            "Chase Whiff %": round(tot_whiffs / tot_chases * 100.0, 1) if tot_chases else np.nan,
        }
    )
    return pd.DataFrame(rows)


def pitch_summary(data: pd.DataFrame) -> pd.DataFrame:
    """Summarize pitch counts, velocities, zone/heart discipline, and contact by pitch type."""
    rows = []
    total_len = len(data)
    for pitch_type, group in data.groupby("MappedPitchType", dropna=False):
        m = hitting_overview_metrics(group)
        velos = group["RelSpeed"].dropna()
        rows.append(
            {
                "MappedPitchType": pitch_type,
                "Pitches": len(group),
                "Usage": (len(group) / total_len * 100.0) if total_len else np.nan,
                "Avg Velo": float(velos.mean()) if not velos.empty else np.nan,
                "Max Velo": float(velos.max()) if not velos.empty else np.nan,
                "Zone %": m["zone_pct"],
                "Heart %": m["heart_pct"],
                "Heart Swing %": m["heart_swing_pct"],
                "Heart Miss %": m["heart_miss_pct"],
                "Swing & Miss %": m["swing_miss_pct"],
                "Chase %": m["chase_pct"],
                "In Play": m["in_play_count"],
                "Avg EV": m["avg_exit_velo"],
                "Max EV": m["max_exit_velo"],
                "Avg LA": m["avg_launch_angle"],
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "MappedPitchType",
                "Pitches",
                "Usage",
                "Avg Velo",
                "Max Velo",
                "Zone %",
                "Heart %",
                "Heart Swing %",
                "Heart Miss %",
                "Swing & Miss %",
                "Chase %",
                "In Play",
                "Avg EV",
                "Max EV",
                "Avg LA",
            ]
        )
    return pd.DataFrame(rows).sort_values("Pitches", ascending=False).reset_index(drop=True)


def report_table(data: pd.DataFrame) -> pd.DataFrame:
    """Build shared screen/PDF hitting summary table by pitch type."""
    summary = pitch_summary(data).copy()
    summary["Pitch"] = summary["MappedPitchType"]
    summary["Count"] = summary["Pitches"].astype(int)
    summary["In Play"] = summary["In Play"].astype(int)

    table_columns = [
        "Pitch",
        "Count",
        "Avg Velo",
        "Max Velo",
        "Zone %",
        "Heart %",
        "Heart Swing %",
        "Heart Miss %",
        "Swing & Miss %",
        "Chase %",
        "In Play",
        "Avg EV",
        "Max EV",
        "Avg LA",
    ]
    table = summary.reindex(columns=table_columns)
    numeric_cols = [
        "Avg Velo",
        "Max Velo",
        "Zone %",
        "Heart %",
        "Heart Swing %",
        "Heart Miss %",
        "Swing & Miss %",
        "Chase %",
        "Avg EV",
        "Max EV",
        "Avg LA",
    ]
    for column in numeric_cols:
        table[column] = pd.to_numeric(table[column], errors="coerce").round(1)
    return table


def _format_inning(row: pd.Series) -> str:
    inning = row.get("Inning")
    top_bottom = str(row.get("Top/Bottom", "") or "").strip()
    if pd.isna(inning):
        return "-"
    prefix = ""
    if top_bottom.lower().startswith("top"):
        prefix = "Top "
    elif top_bottom.lower().startswith("bot"):
        prefix = "Bot "
    return f"{prefix}{int(inning)}"


def _format_pitch_outcome(row: pd.Series) -> str:
    call = str(row.get("PitchCall", "Unknown") or "Unknown")
    play_result = str(row.get("PlayResult", "Undefined") or "Undefined")
    korbb = str(row.get("KorBB", "Undefined") or "Undefined")
    if call == "InPlay" and play_result not in {"Undefined", "Unknown", ""}:
        return f"In Play ({play_result})"
    if korbb in {"Walk", "Strikeout"}:
        return f"{korbb} ({call})"
    call_labels = {
        "StrikeCalled": "Called Strike",
        "StrikeSwinging": "Swinging Strike (Miss)",
        "BallCalled": "Ball",
        "BallinDirt": "Ball in Dirt",
        "FoulBall": "Foul",
        "FoulBallNotFieldable": "Foul",
        "FoulBallFieldable": "Foul (Fieldable)",
        "FoulTip": "Foul Tip",
        "InPlay": "In Play",
        "HitByPitch": "Hit By Pitch",
    }
    return call_labels.get(call, call)


def build_at_bats(data: pd.DataFrame) -> list[dict[str, object]]:
    """Segment pitch rows into ordered Plate Appearances (At-Bats) with pitch sequences."""
    if data.empty:
        return []

    ordered = data.copy()
    has_pa_cols = (
        "PAofInning" in ordered.columns
        and ordered["PAofInning"].notna().any()
        and "Inning" in ordered.columns
        and ordered["Inning"].notna().any()
    )

    pa_ids = []
    current_pa = 0
    prev_key = None
    prev_ended_pa = False

    for _, row in ordered.iterrows():
        if has_pa_cols and pd.notna(row.get("PAofInning")) and pd.notna(row.get("Inning")):
            key = (
                str(row.get("GameID", "")),
                str(row.get("Date", "")),
                int(row.get("Inning")),
                str(row.get("Top/Bottom", "")),
                int(row.get("PAofInning")),
                str(row.get("Hitter", "")),
            )
            if key != prev_key:
                current_pa += 1
                prev_key = key
        else:
            hitter = str(row.get("Hitter", ""))
            pitcher = str(row.get("Pitcher", ""))
            pitch_of_pa = row.get("PitchofPA")
            new_ab = (
                prev_key is None
                or hitter != prev_key[0]
                or pitcher != prev_key[1]
                or prev_ended_pa
                or (pd.notna(pitch_of_pa) and int(pitch_of_pa) == 1)
            )
            if new_ab:
                current_pa += 1
            prev_key = (hitter, pitcher)

        pa_ids.append(current_pa)
        call = str(row.get("PitchCall", ""))
        korbb = str(row.get("KorBB", ""))
        prev_ended_pa = call in {"InPlay", "HitByPitch"} or korbb in {"Walk", "Strikeout"}

    ordered["_PA_ID"] = pa_ids
    at_bats: list[dict[str, object]] = []

    for ab_num, (_, group) in enumerate(ordered.groupby("_PA_ID", sort=False), start=1):
        group = group.copy().reset_index(drop=True)
        group["PitchInAB"] = np.arange(1, len(group) + 1)
        group["OutcomeLabel"] = group.apply(_format_pitch_outcome, axis=1)

        last = group.iloc[-1]
        play_result = str(last.get("PlayResult", "Undefined") or "Undefined")
        korbb = str(last.get("KorBB", "Undefined") or "Undefined")
        if play_result not in {"Undefined", "Unknown", ""}:
            ab_result = play_result
        elif korbb not in {"Undefined", "Unknown", ""}:
            ab_result = korbb
        else:
            ab_result = _format_pitch_outcome(last)

        at_bats.append(
            {
                "ab_number": ab_num,
                "hitter": str(last.get("Hitter", "Unknown")),
                "batter_side": str(last.get("BatterSide", "Unknown")),
                "pitcher": str(last.get("Pitcher", "Unknown")),
                "pitcher_throws": str(last.get("PitcherThrows", "Unknown")),
                "inning": _format_inning(last),
                "result": ab_result,
                "pitches": group,
            }
        )

    return at_bats


def contact_in_play_table(data: pd.DataFrame) -> pd.DataFrame:
    """Return a table of every ball put in play with Exit Velocity and Launch Angle."""
    at_bats = build_at_bats(data)
    rows = []
    multiple_hitters = data["Hitter"].nunique() > 1 if "Hitter" in data else False

    for ab in at_bats:
        pitches = ab["pitches"]
        in_play = pitches[pitches["IsInPlay"]]
        for _, row in in_play.iterrows():
            entry: dict[str, object] = {
                "AB #": ab["ab_number"],
            }
            if multiple_hitters:
                entry["Hitter"] = ab["hitter"]
            entry.update(
                {
                    "Inning": ab["inning"],
                    "Pitcher": ab["pitcher"],
                    "Count": row.get("Count", "-"),
                    "Pitch Type": row.get("MappedPitchType", "Other"),
                    "Pitch Velo (mph)": round(float(row["RelSpeed"]), 1)
                    if pd.notna(row.get("RelSpeed"))
                    else np.nan,
                    "Zone": row.get("ZoneRegion", "Unlocated"),
                    "Exit Velo (mph)": round(float(row["ExitSpeed"]), 1)
                    if pd.notna(row.get("ExitSpeed"))
                    else np.nan,
                    "EV Quality": str(row.get("EVQuality", "-")),
                    "Launch Angle (°)": round(float(row["Angle"]), 1)
                    if pd.notna(row.get("Angle"))
                    else np.nan,
                    "Hit Type": str(row.get("TaggedHitType", "-"))
                    if str(row.get("TaggedHitType", "Undefined")) != "Undefined"
                    else "-",
                    "Result": str(row.get("PlayResult", "-"))
                    if str(row.get("PlayResult", "Undefined")) != "Undefined"
                    else "In Play",
                    "Distance (ft)": round(float(row["Distance"]), 0)
                    if pd.notna(row.get("Distance"))
                    else np.nan,
                }
            )
            rows.append(entry)

    if not rows:
        cols = ["AB #"] + (["Hitter"] if multiple_hitters else []) + [
            "Inning",
            "Pitcher",
            "Count",
            "Pitch Type",
            "Pitch Velo (mph)",
            "Zone",
            "Exit Velo (mph)",
            "EV Quality",
            "Launch Angle (°)",
            "Hit Type",
            "Result",
            "Distance (ft)",
        ]
        return pd.DataFrame(columns=cols)

    return pd.DataFrame(rows)


def at_bat_pitch_log_table(data: pd.DataFrame) -> pd.DataFrame:
    """Return a flat pitch-by-pitch table across all At-Bats with count, velo, and zone location."""
    at_bats = build_at_bats(data)
    rows = []
    multiple_hitters = data["Hitter"].nunique() > 1 if "Hitter" in data else False

    for ab in at_bats:
        for _, row in ab["pitches"].iterrows():
            side = row.get("PlateLocSide")
            height = row.get("PlateLocHeight")
            coords = (
                f"({side:+.2f}, {height:.2f})"
                if pd.notna(side) and pd.notna(height)
                else "-"
            )
            ev = row.get("ExitSpeed")
            la = row.get("Angle")
            contact_str = (
                f"{ev:.1f} mph / {la:.1f}°"
                if pd.notna(ev) and pd.notna(la)
                else (f"{ev:.1f} mph" if pd.notna(ev) else "-")
            )
            entry: dict[str, object] = {
                "AB #": ab["ab_number"],
                "Pitch #": int(row["PitchInAB"]),
            }
            if multiple_hitters:
                entry["Hitter"] = ab["hitter"]
            entry.update(
                {
                    "Inning": ab["inning"],
                    "Pitcher": ab["pitcher"],
                    "Count": row.get("Count", "-"),
                    "Pitch Type": row.get("MappedPitchType", "Other"),
                    "Velo (mph)": round(float(row["RelSpeed"]), 1)
                    if pd.notna(row.get("RelSpeed"))
                    else np.nan,
                    "Location": row.get("ZoneRegion", "Unlocated"),
                    "Coords (X, Y ft)": coords,
                    "Outcome": row.get("OutcomeLabel", "-"),
                    "Contact (EV / LA)": contact_str,
                }
            )
            rows.append(entry)

    if not rows:
        return pd.DataFrame(
            columns=[
                "AB #",
                "Pitch #",
                "Inning",
                "Pitcher",
                "Count",
                "Pitch Type",
                "Velo (mph)",
                "Location",
                "Coords (X, Y ft)",
                "Outcome",
                "Contact (EV / LA)",
            ]
        )
    return pd.DataFrame(rows)
