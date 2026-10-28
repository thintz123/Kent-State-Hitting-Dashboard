"""Print the website's shared hitting report document to PDF using Chromium."""

from contextlib import contextmanager
from io import BytesIO
import subprocess
import sys
import re
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from report_html import REPORT_WIDTH, build_report_html


def pdf_filename(hitter: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(hitter)).strip("_")[:90]
    return f"{name or 'hitter'}_report.pdf"


@contextmanager
def report_browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser_path = playwright.chromium.executable_path
        if not browser_path or not Path(browser_path).exists():
            try:
                subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as exc:
                detail = (exc.stderr or exc.stdout or "").strip()
                raise RuntimeError(
                    "Could not install the PDF browser on the server."
                    + (f" {detail}" if detail else "")
                ) from exc
        try:
            browser = playwright.chromium.launch(
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
        except Exception as exc:
            detail = str(exc).strip()
            raise RuntimeError(
                "Could not start the PDF browser after installing Chromium."
                + (f" {detail}" if detail else "")
            ) from exc
        try:
            yield browser
        finally:
            browser.close()


def print_report(browser, document):
    """Use a continuous page so browser columns and charts are never split."""
    page = browser.new_page(viewport={"width": REPORT_WIDTH, "height": 1000}, device_scale_factor=1)
    try:
        page.route("**/*", lambda route: route.abort())
        page.set_content(document, wait_until="load")
        page.wait_for_function("window.reportReady || window.reportError", timeout=60000)
        error = page.evaluate("window.reportError")
        if error:
            raise RuntimeError(f"Report chart rendering failed: {error}")
        page.emulate_media(media="screen")
        height = page.locator("#report").evaluate("element => Math.ceil(element.scrollHeight) + 2")
        return page.pdf(
            width=f"{REPORT_WIDTH}px", height=f"{height}px",
            print_background=True, margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            scale=1,
        )
    finally:
        page.close()


def build_hitter_pdf(data, source_name, batter_side="Both", sheet_mode="both"):
    id_col = "Hitter" if "Hitter" in data.columns else "Pitcher"
    if data.empty or data[id_col].nunique() != 1:
        raise ValueError("A PDF must contain pitches from exactly one hitter.")
    document = build_report_html(data, source_name, batter_side, sheet_mode=sheet_mode)
    with report_browser() as browser:
        return print_report(browser, document)


# Keep build_pitcher_pdf alias for backward compatibility
build_pitcher_pdf = build_hitter_pdf


def build_report_zip(data, source_name, batter_side="Both", sheet_mode="both"):
    """Reuse one browser; isolate each hitter and avoid filename collisions."""
    if data.empty:
        raise ValueError("No pitches are available to export.")
    id_col = "Hitter" if "Hitter" in data.columns else "Pitcher"
    output = BytesIO()
    with report_browser() as browser, ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for index, (_, group) in enumerate(data.groupby(id_col, sort=True), start=1):
            filename = f"{index:03d}_{pdf_filename(group[id_col].iloc[0])}"
            document = build_report_html(group, source_name, batter_side, sheet_mode=sheet_mode)
            archive.writestr(filename, print_report(browser, document))
    return output.getvalue()
