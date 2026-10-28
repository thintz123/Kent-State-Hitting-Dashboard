"""Read and normalize TrackMan files for screen and PDF hitting reports."""

from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from dashboard_config import (
    GOOD_EV_MIN,
    HEART_CHAMFER_FRAC,
    IN_PLAY_CALLS,
    SOLID_EV_MIN,
    STRIKE_ZONE_X_MAX,
    STRIKE_ZONE_X_MIN,
    SWING_CALLS,
    SZ_BOT_HEIGHT_RATIO,
    SZ_TOP_HEIGHT_RATIO,
    WHIFF_CALLS,
    get_hitter_height_in,
    parse_height_inches,
)
from dashboard_stats import get_pitch_color_map_and_types


@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    """Load and normalize the TrackMan export."""
    return normalize_data(pd.read_excel(path))


@st.cache_data
def read_upload(content: bytes, filename: str, sheet: str | int = 0) -> pd.DataFrame:
    if Path(filename).suffix.lower() == ".csv":
        try:
            return pd.read_csv(BytesIO(content), encoding="utf-8-sig")
        except UnicodeDecodeError:
            return pd.read_csv(BytesIO(content), encoding="cp1252")
    return pd.read_excel(BytesIO(content), sheet_name=sheet)


def apply_zone_and_heart(
    data: pd.DataFrame,
    height_overrides: dict[str, float | str] | None = None,
) -> pd.DataFrame:
    """Compute height-adjusted Strike Zone and octagonal Heart classifications per pitch."""
    data = data.copy()
    overrides = {
        str(k).strip().lower(): parse_height_inches(v)
        for k, v in (height_overrides or {}).items()
    }

    def resolve_height(row_hitter: str, file_height: object) -> float:
        clean = str(row_hitter).strip().lower()
        if clean in overrides:
            return overrides[clean]
        if pd.notna(file_height) and str(file_height).strip() != "":
            return parse_height_inches(file_height)
        return get_hitter_height_in(row_hitter)

    file_heights = (
        data["HitterHeight"]
        if "HitterHeight" in data.columns
        else (
            data["BatterHeight"]
            if "BatterHeight" in data.columns
            else pd.Series(np.nan, index=data.index)
        )
    )
    heights_in = pd.Series(
        [resolve_height(h, fh) for h, fh in zip(data["Hitter"], file_heights)],
        index=data.index,
        dtype=float,
    )
    data["HitterHeightIn"] = heights_in

    # Height-scaled Strike Zone top & bottom (in feet)
    sz_y_min = (SZ_BOT_HEIGHT_RATIO * heights_in) / 12.0
    sz_y_max = (SZ_TOP_HEIGHT_RATIO * heights_in) / 12.0
    sz_height = sz_y_max - sz_y_min

    # Height-scaled Heart Zone bounding box (in feet)
    heart_x_min = STRIKE_ZONE_X_MIN * (2 / 3)
    heart_x_max = STRIKE_ZONE_X_MAX * (2 / 3)
    heart_y_min = sz_y_min + sz_height / 6.0
    heart_y_max = sz_y_max - sz_height / 6.0

    data["SzYMin"] = sz_y_min
    data["SzYMax"] = sz_y_max
    data["HeartYMin"] = heart_y_min
    data["HeartYMax"] = heart_y_max

    x = data["PlateLocSide"]
    y = data["PlateLocHeight"]
    data["HasLocation"] = x.notna() & y.notna()

    # Outer Strike Zone check
    data["IsZone"] = (
        data["HasLocation"]
        & x.between(STRIKE_ZONE_X_MIN, STRIKE_ZONE_X_MAX)
        & (y >= sz_y_min)
        & (y <= sz_y_max)
    )

    # Octagonal (chamfered-corner) Heart Zone check
    hx = (heart_x_max - heart_x_min) / 2.0
    hy = (heart_y_max - heart_y_min) / 2.0
    cy_mid = (heart_y_min + heart_y_max) / 2.0
    dx = x.abs()
    dy = (y - cy_mid).abs()

    chamfer_x = (heart_x_max - heart_x_min) * HEART_CHAMFER_FRAC
    chamfer_y = (heart_y_max - heart_y_min) * HEART_CHAMFER_FRAC

    in_heart_box = data["HasLocation"] & (dx <= hx) & (dy <= hy)
    corner_excess_x = np.maximum(0.0, dx - (hx - chamfer_x)) / chamfer_x
    corner_excess_y = np.maximum(0.0, dy - (hy - chamfer_y)) / chamfer_y
    data["IsHeart"] = in_heart_box & ((corner_excess_x + corner_excess_y) <= 1.0)

    data["IsOutOfZone"] = data["HasLocation"] & ~data["IsZone"]
    data["ZoneRegion"] = np.select(
        [
            data["IsHeart"],
            data["IsZone"] & ~data["IsHeart"],
            data["IsOutOfZone"],
        ],
        [
            "Heart",
            "Zone (Edge)",
            "Out of Zone",
        ],
        default="Unlocated",
    )

    data["IsHeartSwing"] = data["IsHeart"] & data["IsSwing"]
    data["IsHeartMiss"] = data["IsHeart"] & data["IsWhiff"]
    data["IsHeartTake"] = data["IsHeart"] & ~data["IsSwing"]
    data["IsChase"] = data["IsOutOfZone"] & data["IsSwing"]

    # Quadrant relative to center of height-adjusted Strike Zone (for Chase in each quadrant)
    data["Quadrant"] = np.select(
        [
            data["HasLocation"] & (x < 0.0) & (y >= cy_mid),
            data["HasLocation"] & (x >= 0.0) & (y >= cy_mid),
            data["HasLocation"] & (x < 0.0) & (y < cy_mid),
            data["HasLocation"] & (x >= 0.0) & (y < cy_mid),
        ],
        [
            "Up-Left",
            "Up-Right",
            "Down-Left",
            "Down-Right",
        ],
        default="Unlocated",
    )

    # Exit Velocity quality classification (Green = Good, Yellow = Solid, Red = Bad)
    ev = data["ExitSpeed"]
    data["EVQuality"] = np.select(
        [
            ev.notna() & (ev >= GOOD_EV_MIN),
            ev.notna() & (ev >= SOLID_EV_MIN) & (ev < GOOD_EV_MIN),
            ev.notna() & (ev < SOLID_EV_MIN),
            data["IsInPlay"] & ev.isna(),
        ],
        [
            "Good (95+ mph)",
            "Solid (80–94.9 mph)",
            "Bad (<80 mph)",
            "Bad (<80 mph)",
        ],
        default="None",
    )
    return data


def normalize_data(
    data: pd.DataFrame,
    height_overrides: dict[str, float | str] | None = None,
) -> pd.DataFrame:
    """Validate hitter identity and keep unavailable measurements missing."""
    data = data.copy()
    data.columns = data.columns.astype(str).str.strip()
    if data.columns.duplicated().any():
        raise ValueError("The file contains duplicate column names.")
    if data.empty:
        raise ValueError("The selected file or worksheet has no pitch rows.")

    # Map standard TrackMan Batter / BatterTeam columns to Hitter / HitterTeam
    if "Hitter" not in data.columns and "Batter" in data.columns:
        data["Hitter"] = data["Batter"]
    elif "Batter" not in data.columns and "Hitter" in data.columns:
        data["Batter"] = data["Hitter"]

    if "HitterTeam" not in data.columns and "BatterTeam" in data.columns:
        data["HitterTeam"] = data["BatterTeam"]
    elif "BatterTeam" not in data.columns and "HitterTeam" in data.columns:
        data["BatterTeam"] = data["HitterTeam"]

    if "Hitter" not in data.columns:
        raise ValueError("The file needs a Hitter or Batter column to create individual reports.")
    if data["Hitter"].isna().any() or data["Hitter"].astype(str).str.strip().eq("").any():
        raise ValueError("Every pitch row needs a hitter name in the Hitter/Batter column.")
    if not {"TaggedPitchType", "AutoPitchType"}.intersection(data.columns):
        raise ValueError("Include TaggedPitchType or AutoPitchType in the export.")

    defaults = {
        "TaggedPitchType": "Other",
        "AutoPitchType": None,
        "PitchCall": "Unknown",
        "KorBB": "Undefined",
        "PlayResult": "Undefined",
        "TaggedHitType": "Undefined",
        "HitterTeam": "Unknown",
        "BatterTeam": "Unknown",
        "Pitcher": "Unknown",
        "PitcherTeam": "Unknown",
        "BatterSide": "Unknown",
        "PitcherThrows": "Unknown",
        "Top/Bottom": "",
        "Tilt": None,
    }
    for column, default in defaults.items():
        if column not in data.columns:
            data[column] = default

    string_columns = [
        "Hitter",
        "Batter",
        "HitterTeam",
        "BatterTeam",
        "Pitcher",
        "PitcherTeam",
        "BatterSide",
        "PitcherThrows",
        "TaggedPitchType",
        "AutoPitchType",
        "PitchCall",
        "KorBB",
        "PlayResult",
        "TaggedHitType",
        "Top/Bottom",
    ]
    for column in string_columns:
        if column in data.columns:
            data[column] = data[column].astype("string").str.strip().replace("", pd.NA)

    if "PitchNo" not in data.columns:
        data["PitchNo"] = np.arange(1, len(data) + 1)
    else:
        pitch_no = pd.to_numeric(data["PitchNo"], errors="coerce")
        if pitch_no.isna().any():
            data["PitchNo"] = np.arange(1, len(data) + 1)
        else:
            data["PitchNo"] = pitch_no.astype(int)

    numeric_columns = [
        "RelSpeed",
        "SpinRate",
        "SpinAxis",
        "SpinAxis3dSpinEfficiency",
        "VertBreak",
        "InducedVertBreak",
        "HorzBreak",
        "PlateLocHeight",
        "PlateLocSide",
        "ExitSpeed",
        "Angle",
        "Direction",
        "Bearing",
        "Distance",
        "Extension",
        "RelSide",
        "RelHeight",
        "VertApprAngle",
        "HorzApprAngle",
        "Balls",
        "Strikes",
        "Inning",
        "PAofInning",
        "PitchofPA",
    ]
    for column in numeric_columns:
        if column not in data.columns:
            data[column] = np.nan
        data[column] = pd.to_numeric(data[column], errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        )

    data["AutoPitchType"] = data["AutoPitchType"].fillna(data["TaggedPitchType"])
    data["TaggedPitchType"] = data["TaggedPitchType"].fillna("Other")
    _, data = get_pitch_color_map_and_types(data)

    data["PitchCall"] = data["PitchCall"].fillna("Unknown")
    data["KorBB"] = data["KorBB"].fillna("Undefined")
    data["PlayResult"] = data["PlayResult"].fillna("Undefined")
    data["TaggedHitType"] = data["TaggedHitType"].fillna("Undefined")
    data["Hitter"] = data["Hitter"].fillna("Unknown")
    data["Batter"] = data["Hitter"]
    data["HitterTeam"] = data["HitterTeam"].fillna("Unknown")
    data["BatterTeam"] = data["HitterTeam"]
    data["Pitcher"] = data["Pitcher"].fillna("Unknown")
    data["PitcherTeam"] = data["PitcherTeam"].fillna("Unknown")
    data["BatterSide"] = data["BatterSide"].fillna("Unknown")
    data["PitcherThrows"] = data["PitcherThrows"].fillna("Unknown")
    data["Top/Bottom"] = data["Top/Bottom"].fillna("")

    # Swing, Whiff, and Contact flags
    data["IsStrike"] = data["PitchCall"].isin(
        ["StrikeCalled", "StrikeSwinging", "FoulBall", "FoulBallNotFieldable", "FoulBallFieldable", "FoulTip", "InPlay"]
    )
    data["IsSwing"] = data["PitchCall"].isin(SWING_CALLS)
    data["IsWhiff"] = data["PitchCall"].isin(WHIFF_CALLS)
    data["IsInPlay"] = data["PitchCall"].isin(IN_PLAY_CALLS)
    data["IsContact"] = data["IsSwing"] & ~data["IsWhiff"]

    # Apply height-adjusted Zone and Octagonal Heart calculations
    data = apply_zone_and_heart(data, height_overrides=height_overrides)

    # Compute Spray Chart X/Y coordinates (in feet from Home Plate) using Distance and Bearing/Direction
    spray_angle_deg = data["Bearing"].where(data["Bearing"].notna(), data["Direction"])
    valid_spray = data["Distance"].notna() & spray_angle_deg.notna()
    angle_rad = np.radians(spray_angle_deg)
    data["SprayX"] = np.where(valid_spray, data["Distance"] * np.sin(angle_rad), np.nan)
    data["SprayY"] = np.where(valid_spray, data["Distance"] * np.cos(angle_rad), np.nan)

    # Formatted count string (Balls-Strikes)
    balls = data["Balls"]
    strikes = data["Strikes"]
    valid_count = balls.notna() & strikes.notna()
    data["Count"] = np.where(
        valid_count,
        balls.fillna(0).astype(int).astype(str) + "-" + strikes.fillna(0).astype(int).astype(str),
        "-",
    )

    data["PreviousPitch"] = pd.NA
    if {"GameID", "PAofInning"}.issubset(data.columns):
        data["PreviousPitch"] = data.groupby(["Hitter", "GameID", "PAofInning"])[
            "MappedPitchType"
        ].shift()
    return data
