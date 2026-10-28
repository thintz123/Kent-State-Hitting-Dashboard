"""Shared paths, pitch colors, hitter heights, and strike-zone / octagonal heart settings."""

from pathlib import Path
import re

DATA_FILE = Path(__file__).with_name("20261009-OlgaMuralField-1_unverified.xlsx")
KENT_STATE_TEAM = "KS_GF"

# Reference 6'0" (72 in) strike zone dimensions:
# 19.44 in = 0.27 * 72 in (knees), 38.52 in = 0.535 * 72 in (midpoint of torso)
DEFAULT_HITTER_HEIGHT_IN = 72.0
SZ_BOT_HEIGHT_RATIO = 19.44 / 72.0  # 0.27
SZ_TOP_HEIGHT_RATIO = 38.52 / 72.0  # 0.535

STRIKE_ZONE_WIDTH_FT = 19.44 / 12
STRIKE_ZONE_Y_MIN = (SZ_BOT_HEIGHT_RATIO * DEFAULT_HITTER_HEIGHT_IN) / 12
STRIKE_ZONE_Y_MAX = (SZ_TOP_HEIGHT_RATIO * DEFAULT_HITTER_HEIGHT_IN) / 12
STRIKE_ZONE_X_MIN = -STRIKE_ZONE_WIDTH_FT / 2
STRIKE_ZONE_X_MAX = STRIKE_ZONE_WIDTH_FT / 2

# Heart of the strike zone: chamfered octagon inside the 3x3 strike zone
HEART_ZONE_X_MIN = STRIKE_ZONE_X_MIN * (2 / 3)
HEART_ZONE_X_MAX = STRIKE_ZONE_X_MAX * (2 / 3)
HEART_ZONE_Y_MIN = STRIKE_ZONE_Y_MIN + (STRIKE_ZONE_Y_MAX - STRIKE_ZONE_Y_MIN) / 6
HEART_ZONE_Y_MAX = STRIKE_ZONE_Y_MAX - (STRIKE_ZONE_Y_MAX - STRIKE_ZONE_Y_MIN) / 6
# Corner chamfer fraction of heart width/height (creates the 8-sided clipped-corner Heart from the sketch)
HEART_CHAMFER_FRAC = 0.20

# Kent State roster heights (in inches / ft-in strings), supporting both "Last, First" and "First Last"
# plus common TrackMan spelling variants (e.g., Nathan/Nate, Connor/Conner).
HITTER_HEIGHTS_IN: dict[str, float | str] = {
    "Matthews, Luke": "5'11\"",
    "Luke Matthews": "5'11\"",
    "Manley, Nathan": "5'9\"",
    "Manley, Nate": "5'9\"",
    "Nate Manley": "5'9\"",
    "Nathan Manley": "5'9\"",
    "Olsen, Brenden": "6'6\"",
    "Brenden Olsen": "6'6\"",
    "Marshall, Brady": "5'11\"",
    "Brady Marshall": "5'11\"",
    "Tumis, Easton": "6'5\"",
    "Easton Tumis": "6'5\"",
    "Perazzo, Michael": "5'9\"",
    "Michael Perazzo": "5'9\"",
    "Cain, Ian": "6'0\"",
    "Ian Cain": "6'0\"",
    "Reese, Ripken": "6'2\"",
    "Ripken Reese": "6'2\"",
    "Belcher, Nolan": "6'4\"",
    "Nolan Belcher": "6'4\"",
    "Dalton, Brody": "6'3\"",
    "Brody Dalton": "6'3\"",
    "Wentz, Gannon": "5'11\"",
    "Gannon Wentz": "5'11\"",
    "Camacho, Manny": "6'8\"",
    "Manny Camacho": "6'8\"",
    "Small, Eli": "6'1\"",
    "Eli Small": "6'1\"",
    "Covas, Alejandro": "6'2\"",
    "Alejandro Covas": "6'2\"",
    "Humphrey, Max": "6'1\"",
    "Max Humphrey": "6'1\"",
    "Marcos, Caden": "5'10\"",
    "Caden Marcos": "5'10\"",
    "Strode, Will": "6'3\"",
    "Will Strode": "6'3\"",
    "Denham, Drew": "6'0\"",
    "Drew Denham": "6'0\"",
    "Krzysiak, Brody": "6'1\"",
    "Brody Krzysiak": "6'1\"",
    "Oerther, Drew": "6'1\"",
    "Drew Oerther": "6'1\"",
    "Keffaber, Grant": "6'0\"",
    "Grant Keffaber": "6'0\"",
    "Dennison, Chase": "6'1\"",
    "Chase Dennison": "6'1\"",
    "Rabatin, Ben": "6'1\"",
    "Ben Rabatin": "6'1\"",
    "Bryant, Eli": "6'2\"",
    "Eli Bryant": "6'2\"",
    "Rienstra-Kiracofe, Micah": "6'2\"",
    "Micah Rienstra-Kiracofe": "6'2\"",
    "Gatlin, Wyatt": "6'2\"",
    "Wyatt Gatlin": "6'2\"",
    "Hanley, Ben": "6'1\"",
    "Ben Hanley": "6'1\"",
    "Cuozzo, Connor": "6'1\"",
    "Cuozzo, Conner": "6'1\"",
    "Conner Cuozzo": "6'1\"",
    "Connor Cuozzo": "6'1\"",
    "Schneider, Braylon": "6'1\"",
    "Braylon Schneider": "6'1\"",
    "Holewinski, Evan": "6'5\"",
    "Evan Holewinski": "6'5\"",
    "Williams, Peyton": "6'3\"",
    "Peyton Williams": "6'3\"",
    "Lind, Parker": "6'2\"",
    "Parker Lind": "6'2\"",
    "Muncy, Nathan": "6'2\"",
    "Muncy, Nate": "6'2\"",
    "Nate Muncy": "6'2\"",
    "Nathan Muncy": "6'2\"",
    "Lemieux, Bobby": "6'0\"",
    "Bobby Lemieux": "6'0\"",
    "Jones, Gavin": "6'3\"",
    "Gavin Jones": "6'3\"",
}


def parse_height_inches(value: float | int | str | None) -> float:
    """Convert a height in inches (e.g. 74) or feet-inches string (e.g. \"6'2\\\"\", \"5' 11''\") to inches."""
    if value is None:
        return DEFAULT_HITTER_HEIGHT_IN
    if isinstance(value, (int, float)):
        val = float(value)
        return val * 12.0 if 4.0 <= val <= 7.5 else val
    text = str(value).strip()
    if not text:
        return DEFAULT_HITTER_HEIGHT_IN
    match = re.match(r"^(\d+)\s*(?:'|’|-|ft)\s*(\d+(?:\.\d+)?)?\s*(?:\"|''|’’|in)?$", text, re.I)
    if match:
        feet = float(match.group(1))
        inches = float(match.group(2) or 0.0)
        return feet * 12.0 + inches
    try:
        num = float(text)
        return num * 12.0 if 4.0 <= num <= 7.5 else num
    except ValueError:
        return DEFAULT_HITTER_HEIGHT_IN


def get_hitter_height_in(hitter: str | None) -> float:
    """Look up a hitter's height in inches from HITTER_HEIGHTS_IN (case/format insensitive)."""
    if not hitter:
        return DEFAULT_HITTER_HEIGHT_IN
    clean = re.sub(r"\s+", " ", str(hitter).strip())
    if clean in HITTER_HEIGHTS_IN:
        return parse_height_inches(HITTER_HEIGHTS_IN[clean])
    lower_map = {re.sub(r"\s+", " ", k.strip().lower()): v for k, v in HITTER_HEIGHTS_IN.items()}
    key_lower = clean.lower()
    if key_lower in lower_map:
        return parse_height_inches(lower_map[key_lower])
    # Try flipping "First Last" <-> "Last, First"
    if "," in key_lower:
        last, first = [part.strip() for part in key_lower.split(",", 1)]
        flipped = f"{first} {last}"
        if flipped in lower_map:
            return parse_height_inches(lower_map[flipped])
    elif " " in key_lower:
        first, last = key_lower.split(" ", 1)
        flipped = f"{last.strip()}, {first.strip()}"
        if flipped in lower_map:
            return parse_height_inches(lower_map[flipped])
    return DEFAULT_HITTER_HEIGHT_IN


def format_height_ft_in(height_in: float) -> str:
    """Format height in inches as feet and inches (e.g. 6'2\")."""
    total_in = int(round(height_in))
    return f"{total_in // 12}'{total_in % 12}\""


def get_zone_and_heart_bounds(height_in: float | None = None) -> dict[str, float]:
    """Compute Strike Zone and Heart bounds in feet adjusted for a hitter's height in inches."""
    h = parse_height_inches(height_in)
    sz_y_min = (SZ_BOT_HEIGHT_RATIO * h) / 12.0
    sz_y_max = (SZ_TOP_HEIGHT_RATIO * h) / 12.0
    sz_height = sz_y_max - sz_y_min

    heart_x_min = STRIKE_ZONE_X_MIN * (2 / 3)
    heart_x_max = STRIKE_ZONE_X_MAX * (2 / 3)
    heart_y_min = sz_y_min + sz_height / 6.0
    heart_y_max = sz_y_max - sz_height / 6.0

    chamfer_x = (heart_x_max - heart_x_min) * HEART_CHAMFER_FRAC
    chamfer_y = (heart_y_max - heart_y_min) * HEART_CHAMFER_FRAC

    return {
        "height_in": h,
        "sz_x_min": STRIKE_ZONE_X_MIN,
        "sz_x_max": STRIKE_ZONE_X_MAX,
        "sz_y_min": sz_y_min,
        "sz_y_max": sz_y_max,
        "heart_x_min": heart_x_min,
        "heart_x_max": heart_x_max,
        "heart_y_min": heart_y_min,
        "heart_y_max": heart_y_max,
        "chamfer_x": chamfer_x,
        "chamfer_y": chamfer_y,
    }


def heart_octagon_vertices(bounds: dict[str, float]) -> list[tuple[float, float]]:
    """Return the 8 vertices (plus closing vertex) of the chamfered octagonal Heart zone."""
    x0, x1 = bounds["heart_x_min"], bounds["heart_x_max"]
    y0, y1 = bounds["heart_y_min"], bounds["heart_y_max"]
    cx, cy = bounds["chamfer_x"], bounds["chamfer_y"]
    return [
        (x0 + cx, y1),      # Top-left inner
        (x1 - cx, y1),      # Top-right inner
        (x1, y1 - cy),      # Right-top inner
        (x1, y0 + cy),      # Right-bottom inner
        (x1 - cx, y0),      # Bottom-right inner
        (x0 + cx, y0),      # Bottom-left inner
        (x0, y0 + cy),      # Left-bottom inner
        (x0, y1 - cy),      # Left-top inner
        (x0 + cx, y1),      # Close path
    ]


def heart_octagon_svg_path(bounds: dict[str, float]) -> str:
    """Build a Plotly SVG path string for the chamfered octagonal Heart zone."""
    verts = heart_octagon_vertices(bounds)
    first = f"M {verts[0][0]:.4f},{verts[0][1]:.4f}"
    rest = " ".join(f"L {x:.4f},{y:.4f}" for x, y in verts[1:-1])
    return f"{first} {rest} Z"


SWING_CALLS = {
    "StrikeSwinging",
    "FoulBall",
    "FoulBallNotFieldable",
    "FoulBallFieldable",
    "FoulTip",
    "InPlay",
}
WHIFF_CALLS = {"StrikeSwinging"}
IN_PLAY_CALLS = {"InPlay"}

PITCH_COLORS = {
    "Fastball": "#d62728",
    "Four-Seam": "#c8102e",
    "FourSeamFastBall": "#c8102e",
    "Sinker": "#f28e2b",
    "TwoSeamFastBall": "#f28e2b",
    "Slider": "#eab308",
    "Curveball": "#2563eb",
    "Changeup": "#16a34a",
    "ChangeUp": "#16a34a",
    "Cutter": "#9333ea",
    "Splitter": "#0891b2",
    "Knuckleball": "#7c3aed",
    "Sweeper": "#b45309",
    "Slurve": "#65a30d",
    "Forkball": "#1e3a8a",
    "Screwball": "#db2777",
    "Offspeed": "#16a34a",
    "Breaking": "#2563eb",
    "Other": "#6b7280",
}

# Exit Velocity quality thresholds (mph) and colors for Spray Chart & Contact charts
GOOD_EV_MIN = 95.0
SOLID_EV_MIN = 80.0

EV_QUALITY_COLORS = {
    "Good (95+ mph)": "#16a34a",
    "Solid (80–94.9 mph)": "#eab308",
    "Bad (<80 mph)": "#dc2626",
}

CHASE_QUADRANTS = [
    "Up-Left",
    "Up-Right",
    "Down-Left",
    "Down-Right",
]

PLAY_RESULT_COLORS = {
    "Single": "#fe6100",
    "Double": "#785ef0",
    "Triple": "#ffb000",
    "HomeRun": "#dc267f",
    "Error": "#f59e0b",
    "FieldersChoice": "#0891b2",
    "Sacrifice": "#14b8a6",
    "Out": "#64748b",
    "Undefined": "#94a3b8",
}

PITCH_HEATMAPS = {
    "Fastball": "Reds",
    "Four-Seam": "Reds",
    "FourSeamFastBall": "Reds",
    "Sinker": "YlOrBr",
    "TwoSeamFastBall": "YlOrBr",
    "Slider": "YlOrBr",
    "Curveball": "Blues",
    "Changeup": "Greens",
    "ChangeUp": "Greens",
    "Cutter": "Purples",
    "Splitter": "BuGn",
    "Knuckleball": "Purples",
    "Sweeper": "Oranges",
    "Slurve": "YlGn",
    "Forkball": "PuBu",
    "Screwball": "PuRd",
    "Offspeed": "Greens",
    "Breaking": "Blues",
    "Other": "Greys",
}

PITCH_CATEGORY_SETS = {
    "Fastball": {
        "Fastball",
        "Four-Seam",
        "FourSeamFastBall",
        "Sinker",
        "TwoSeamFastBall",
        "Cutter",
    },
    "Offspeed": {"Changeup", "ChangeUp", "Splitter", "Forkball", "Screwball", "Knuckleball"},
    "Breaking": {"Slider", "Curveball", "Sweeper", "Slurve"},
}

TAGGED_DATA_THRESHOLD = 0.8
