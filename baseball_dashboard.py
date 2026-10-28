"""Streamlit entry point: uploads, hitter filters, height-adjusted Heart zone, and PDF downloads.

Run with: streamlit run baseball_dashboard.py
"""

from pathlib import Path
from io import BytesIO
import hashlib

import pandas as pd
import streamlit as st

from dashboard_config import (
    KENT_STATE_TEAM,
    format_height_ft_in,
    get_hitter_height_in,
)
from dashboard_data import apply_zone_and_heart, normalize_data, read_upload
from dashboard_report import render_report


def main() -> None:
    st.set_page_config(
        page_title="Kent State Hitting Dashboard",
        page_icon="⚾",
        layout="wide",
    )
    st.markdown(
        """
        <style>
        .report-title { text-align: center; margin: -20px 0 8px; }
        .report-title h1 { margin-bottom: 0; font-size: 2rem; }
        .report-title p { margin-top: 2px; color: #666; }
        .scatter-caption { text-align: center; color: #666; font-size: 1.25rem; margin: -12px 0 12px; }
        [data-testid="stDataFrame"] { border: 1px solid #aaa; }
        h2 { font-size: 1.1rem !important; text-align: center; margin: 5px 0 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.header("Upload hitting data")
    uploaded = st.sidebar.file_uploader(
        "Drop a TrackMan CSV or Excel file here",
        type=["csv", "xlsx", "xls"],
        help="Include Hitter (or Batter) and TaggedPitchType or AutoPitchType.",
    )

    if uploaded is None:
        st.session_state.pop("pdf_downloads", None)
        st.session_state.pop("pdf_export_key", None)
        st.info("Upload a TrackMan CSV or Excel file in the sidebar to get started.")
        st.stop()

    sheet = 0
    try:
        content = uploaded.getvalue()
        source_name = uploaded.name
        if Path(source_name).suffix.lower() in {".xlsx", ".xls"}:
            with pd.ExcelFile(BytesIO(content)) as workbook:
                sheet = st.sidebar.selectbox("Worksheet", workbook.sheet_names)
        data = normalize_data(read_upload(content, source_name, sheet))
    except Exception as exc:
        st.error(f"Could not read this hitting file: {exc}")
        st.info("Use a TrackMan export with column headers in the first row.")
        st.stop()
    source_id = hashlib.sha256(content).hexdigest()
    st.sidebar.caption(f"{len(data):,} pitches | {data['Hitter'].nunique()} hitters")

    with st.sidebar:
        st.header("Report filters")
        teams = sorted(data["HitterTeam"].unique())
        default_team = KENT_STATE_TEAM if KENT_STATE_TEAM in teams else teams[0]
        team = st.selectbox("Hitter team", teams, index=teams.index(default_team))
        team_data = data[data["HitterTeam"].eq(team)]
        hitters = ["All hitters"] + sorted(team_data["Hitter"].unique())
        hitter = st.selectbox("Hitter", hitters)
        sides = ["Both"] + sorted(team_data["BatterSide"].unique())
        batter_side = st.selectbox("Batter side", sides)

        height_overrides: dict[str, float] = {}
        if hitter != "All hitters":
            default_ht = int(round(get_hitter_height_in(hitter)))
            selected_ht = st.number_input(
                f"Hitter height (inches, {format_height_ft_in(default_ht)})",
                min_value=60,
                max_value=84,
                value=default_ht,
                step=1,
                help="Adjusts the Strike Zone and octagonal Heart vertically for this hitter's height.",
            )
            if selected_ht != default_ht:
                height_overrides[hitter] = float(selected_ht)
                data = apply_zone_and_heart(data, height_overrides=height_overrides)
                team_data = data[data["HitterTeam"].eq(team)]

        if hitter != "All hitters":
            team_data = team_data[team_data["Hitter"].eq(hitter)]
        if batter_side != "Both":
            team_data = team_data[team_data["BatterSide"].eq(batter_side)]

        sheet_choice = st.radio(
            "Report sheet view",
            options=["Both Sheets", "Main Hitting Dashboard", "At-Bat Breakdown Sheet"],
            index=0,
        )
        sheet_mode_map = {
            "Both Sheets": "both",
            "Main Hitting Dashboard": "main",
            "At-Bat Breakdown Sheet": "at_bats",
        }
        sheet_mode = sheet_mode_map[sheet_choice]
        st.divider()
        st.caption("All charts update together for the selected hitter, height, and batter side.")

    if team_data.empty:
        st.warning("No pitches match the selected filters.")
        st.stop()

    with st.sidebar.expander("Download PDF reports", expanded=True):
        st.caption(
            "Each PDF uses the same layout and charts as the report preview, including the Main "
            "Hitting Dashboard and the At-Bat Breakdown Sheet. The ZIP includes every hitter on "
            "the selected team."
        )
        export_key = (
            "hitting-html-v1",
            source_id,
            source_name,
            str(sheet),
            team,
            hitter,
            batter_side,
            sheet_mode,
            tuple(sorted(height_overrides.items())),
        )
        if st.session_state.get("pdf_export_key") != export_key:
            st.session_state.pop("pdf_downloads", None)
            st.session_state["pdf_export_key"] = export_key
        make_single = st.button(
            "Generate selected hitter's PDF",
            disabled=hitter == "All hitters",
            help="Choose an individual hitter in the sidebar.",
            use_container_width=True,
        )
        make_all = st.button("Generate all hitter PDFs (ZIP)", use_container_width=True)
        if make_single or make_all:
            try:
                from pitcher_pdf import build_hitter_pdf, build_report_zip, pdf_filename
                with st.spinner("Generating hitter reports..."):
                    if make_single:
                        result = build_hitter_pdf(
                            team_data, source_name, batter_side, sheet_mode=sheet_mode,
                        )
                        filename, mime = pdf_filename(hitter), "application/pdf"
                    else:
                        batch = data[data["HitterTeam"].eq(team)]
                        if batter_side != "Both":
                            batch = batch[batch["BatterSide"].eq(batter_side)]
                        result = build_report_zip(
                            batch, source_name, batter_side, sheet_mode=sheet_mode,
                        )
                        filename, mime = "hitter_reports.zip", "application/zip"
                    st.session_state["pdf_downloads"] = (result, filename, mime)
            except ImportError:
                st.error("Install the report dependencies with: pip install -r requirements.txt")
            except Exception as exc:
                st.error(f"Could not generate the reports: {exc}")
        if "pdf_downloads" in st.session_state:
            result, filename, mime = st.session_state["pdf_downloads"]
            st.download_button("Download reports", result, file_name=filename, mime=mime)

    render_report(team_data, source_name, batter_side, sheet_mode=sheet_mode)


if __name__ == "__main__":
    main()
