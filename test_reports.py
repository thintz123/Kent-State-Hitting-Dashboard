"""Run with: python -m unittest test_reports."""

from io import BytesIO
import json
import re
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import pandas as pd

from dashboard_data import normalize_data, read_upload
from dashboard_stats import (
    build_at_bats,
    chase_by_quadrant_table,
    contact_in_play_table,
    hitting_overview_metrics,
    report_table,
)
from pitcher_pdf import build_report_zip


class ReportTests(unittest.TestCase):
    def test_csv_and_excel_worksheet(self):
        raw = pd.DataFrame({"Hitter": ["Test"], "TaggedPitchType": ["Fastball"]})
        csv = read_upload(raw.to_csv(index=False).encode(), "pitches.csv")
        pd.testing.assert_frame_equal(csv, raw)
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            raw.to_excel(writer, sheet_name="Pitches", index=False)
            pd.DataFrame({"Other": [1]}).to_excel(writer, sheet_name="Notes", index=False)
        excel = read_upload(buffer.getvalue(), "pitches.xlsx", "Pitches")
        pd.testing.assert_frame_equal(excel, raw)

    def test_accepts_hitter_or_batter_column(self):
        from dashboard_config import get_hitter_height_in

        from_batter = normalize_data(pd.DataFrame({
            "Batter": ["Matthews, Luke"],
            "BatterTeam": ["KS_GF"],
            "TaggedPitchType": ["Fastball"],
        }))
        self.assertEqual(from_batter["Hitter"].iloc[0], "Matthews, Luke")
        self.assertEqual(from_batter["HitterTeam"].iloc[0], "KS_GF")
        self.assertEqual(from_batter["HitterHeightIn"].iloc[0], 71.0)
        self.assertEqual(get_hitter_height_in("Manley, Nathan"), 69.0)
        self.assertEqual(get_hitter_height_in("Olsen, Brenden"), 78.0)
        self.assertEqual(get_hitter_height_in("Cuozzo, Connor"), 73.0)
        self.assertEqual(get_hitter_height_in("Muncy, Nathan"), 74.0)

    def test_missing_metrics_stay_missing(self):
        data = normalize_data(pd.DataFrame({
            "Hitter": ["Test"], "AutoPitchType": ["Fastball"],
        }))
        table = report_table(data)
        self.assertEqual(table["Count"].iloc[0], 1)
        self.assertTrue(pd.isna(table["Avg Velo"].iloc[0]))
        self.assertTrue(pd.isna(table["Heart Swing %"].iloc[0]))

    def test_octagonal_heart_and_height_adjustment(self):
        # At 6'0" (72 in), heart_y_max is ~2.945 ft; at 6'8" (80 in), heart_y_max is ~3.272 ft.
        # A pitch at (0.0, 3.10) is above the Heart for a 6'0" hitter, but inside the Heart for a 6'8" hitter.
        raw = pd.DataFrame({
            "Hitter": ["Player A", "Player A"],
            "TaggedPitchType": ["Fastball", "Fastball"],
            "PlateLocSide": [0.0, 0.53],     # (0.53, 2.94) is in the clipped corner of the octagon
            "PlateLocHeight": [3.10, 2.94],
            "PitchCall": ["StrikeSwinging", "StrikeCalled"],
        })
        default_data = normalize_data(raw, height_overrides={"Player A": 72})
        self.assertFalse(bool(default_data["IsHeart"].iloc[0]))
        # Corner point (0.53, 2.94) is inside the rectangle [-0.54, 0.54] x [1.885, 2.945]
        # but clipped out by the octagonal chamfer!
        self.assertFalse(bool(default_data["IsHeart"].iloc[1]))

        tall_data = normalize_data(raw, height_overrides={"Player A": 80})
        self.assertTrue(bool(tall_data["IsHeart"].iloc[0]))

    def test_hitting_rates_and_contact_in_play(self):
        data = normalize_data(pd.DataFrame({
            "Hitter": ["Test"] * 4,
            "TaggedPitchType": ["Fastball"] * 4,
            "PlateLocSide": [0.0, 0.0, 0.70, 1.40],
            "PlateLocHeight": [2.4, 2.4, 2.4, 2.4],
            "PitchCall": ["StrikeSwinging", "BallCalled", "InPlay", "StrikeSwinging"],
            "PlayResult": ["Undefined", "Undefined", "Double", "Undefined"],
            "ExitSpeed": [None, None, 102.4, None],
            "Angle": [None, None, 18.5, None],
        }))
        metrics = hitting_overview_metrics(data)
        # 2 pitches in Heart: 1 swing (StrikeSwinging), 1 take -> Heart Swing % = 50%, Heart Miss % = 100%
        self.assertAlmostEqual(metrics["heart_swing_pct"], 50.0)
        self.assertAlmostEqual(metrics["heart_miss_pct"], 100.0)
        # 3 total swings (2 whiffs, 1 in play) -> Swing & Miss % = 66.67%
        self.assertAlmostEqual(metrics["swing_miss_pct"], 200.0 / 3.0)
        # 1 pitch out of zone (1.40, 2.4), 1 swing -> Chase % = 100%
        self.assertAlmostEqual(metrics["chase_pct"], 100.0)

        bip = contact_in_play_table(data)
        self.assertEqual(len(bip), 1)
        self.assertEqual(bip["Exit Velo (mph)"].iloc[0], 102.4)
        self.assertEqual(bip["EV Quality"].iloc[0], "Good (95+ mph)")
        self.assertEqual(bip["Launch Angle (°)"].iloc[0], 18.5)
        self.assertEqual(bip["Result"].iloc[0], "Double")

        quads = chase_by_quadrant_table(data)
        down_right = quads[quads["Quadrant"].eq("Down-Right")].iloc[0]
        self.assertEqual(int(down_right["Out-of-Zone Pitches"]), 1)
        self.assertEqual(int(down_right["Chases"]), 1)
        self.assertEqual(float(down_right["Chase %"]), 100.0)

    def test_at_bat_breakdown(self):
        data = normalize_data(pd.DataFrame({
            "Hitter": ["Test"] * 3,
            "Pitcher": ["Pitcher A"] * 3,
            "Inning": [1, 1, 3],
            "Top/Bottom": ["Bottom", "Bottom", "Bottom"],
            "PAofInning": [1, 1, 2],
            "PitchofPA": [1, 2, 1],
            "Balls": [0, 1, 0],
            "Strikes": [0, 0, 0],
            "TaggedPitchType": ["Fastball", "Slider", "Curveball"],
            "RelSpeed": [92.1, 83.4, 78.0],
            "PitchCall": ["BallCalled", "InPlay", "StrikeCalled"],
            "PlayResult": ["Undefined", "Single", "Undefined"],
            "PlateLocSide": [1.1, 0.0, -0.1],
            "PlateLocHeight": [2.5, 2.4, 2.2],
        }))
        at_bats = build_at_bats(data)
        self.assertEqual(len(at_bats), 2)
        self.assertEqual(len(at_bats[0]["pitches"]), 2)
        self.assertEqual(at_bats[0]["result"], "Single")

    def test_rejects_missing_hitter_identity(self):
        for raw in [
            pd.DataFrame({"TaggedPitchType": ["Fastball"]}),
            pd.DataFrame({"Hitter": [""], "TaggedPitchType": ["Fastball"]}),
            pd.DataFrame({"Batter": [None], "TaggedPitchType": ["Fastball"]}),
        ]:
            with self.assertRaises(ValueError):
                normalize_data(raw)

    def test_zip_isolates_hitters_and_avoids_filename_collisions(self):
        data = normalize_data(pd.DataFrame({
            "Hitter": ["A/B", "A B", "A/B"], "TaggedPitchType": ["Fastball"] * 3,
        }))

        def fake_document(group, *args, **kwargs):
            self.assertEqual(group["Hitter"].nunique(), 1)
            return group["Hitter"].iloc[0]

        with (
            patch("pitcher_pdf.report_browser"),
            patch("pitcher_pdf.build_report_html", side_effect=fake_document),
            patch("pitcher_pdf.print_report", side_effect=lambda browser, document: document.encode()),
        ):
            result = build_report_zip(data, "test.csv")
        with ZipFile(BytesIO(result)) as archive:
            self.assertEqual(len(set(archive.namelist())), 2)
            self.assertEqual({archive.read(name) for name in archive.namelist()}, {b"A/B", b"A B"})

    def test_shared_report_keeps_website_charts_and_escapes_upload_labels(self):
        from report_html import build_report_html

        data = normalize_data(pd.DataFrame({
            "Hitter": ["Test"],
            "TaggedPitchType": ["</script><script>alert(1)</script>"],
            "RelSpeed": [90],
            "Balls": [1],
            "Strikes": [2],
            "PitchCall": ["InPlay"],
            "PlayResult": ["Single"],
            "ExitSpeed": [99.5],
            "Angle": [14.2],
            "Distance": [325.0],
            "Bearing": [-12.0],
            "PlateLocSide": [0.0],
            "PlateLocHeight": [2.4],
        }))
        self.assertTrue(pd.notna(data["SprayX"].iloc[0]))
        self.assertTrue(pd.notna(data["SprayY"].iloc[0]))
        html = build_report_html(data, "<test.csv>")
        specs = json.loads(re.search(
            r'<script type="application/json" id="plot-specs">(.*?)</script>', html, re.S,
        ).group(1))
        kinds = {trace["type"] for spec in specs for trace in spec["figure"]["data"]}
        titles = {spec["figure"]["layout"].get("title", {}).get("text", "") for spec in specs}
        self.assertTrue({"scatter", "bar"} <= kinds)
        self.assertIn("Batted Ball Spray Chart (by EV)", titles)
        self.assertIn("Heart of the Strike Zone — Takes & Whiffs", titles)
        self.assertIn("Chase % in Each Quadrant (Out-of-Zone Pitches)", titles)
        self.assertIn("Strike Zone — Every Pitch Location & Pitch Type", titles)
        self.assertIn("Heart Swing %", html)
        self.assertIn("Heart Miss %", html)
        self.assertIn("Swing &amp; Miss %", html)
        self.assertIn("Chase %", html)
        self.assertIn("Every Contact in Play", html)
        self.assertIn("At-Bat Pitch-by-Pitch Breakdown", html)
        self.assertIn("&lt;test.csv&gt;", html)
        self.assertNotIn("</script><script>alert(1)</script>", html)


if __name__ == "__main__":
    unittest.main()
