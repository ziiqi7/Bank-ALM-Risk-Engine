"""Generate a professional PDF demo-case report for the ALM risk engine."""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path
import sys

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _bootstrap_project_root() -> Path:
    """Add the repository root to ``sys.path`` based on this script location."""

    project_root = Path(__file__).resolve().parents[1]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
    os.environ.setdefault("MPLCONFIGDIR", str(project_root / ".mpl-cache"))
    return project_root


PROJECT_ROOT = _bootstrap_project_root()

from example_pipeline import load_config, load_or_generate_portfolio
from src.reporting.tables import action_log_table, summary_table
from src.stress.management_actions import run_management_action_plan
from src.stress.run_stress import run_stress_tests
from src.stress.scenarios import build_stress_scenarios
from src.irrbb.eve import calculate_eve_sensitivity
from src.irrbb.nii import calculate_12m_nii_sensitivity
from src.irrbb.shocks import build_standard_rate_shocks
from src.liquidity.lcr import calculate_lcr
from src.liquidity.nsfr import calculate_nsfr

DEMO_CASES = (
    ("balanced", "data/portfolios/demo_balanced.csv"),
    ("liquidity_tight", "data/portfolios/demo_liquidity_tight.csv"),
    ("irrbb_heavy", "data/portfolios/demo_irrbb_heavy.csv"),
)


def _extract_markdown_sections(readme_path: Path) -> dict[str, list[str]]:
    """Extract README content grouped by second-level headings."""

    sections: dict[str, list[str]] = {}
    current_heading: str | None = None
    current_lines: list[str] = []

    for raw_line in readme_path.read_text(encoding="utf-8").splitlines():
        if raw_line.startswith("## "):
            if current_heading is not None:
                sections[current_heading] = current_lines
            current_heading = raw_line[3:].strip()
            current_lines = []
            continue
        if current_heading is not None:
            current_lines.append(raw_line)

    if current_heading is not None:
        sections[current_heading] = current_lines
    return sections


def _clean_markdown_text(line: str) -> str:
    """Strip small markdown markers for PDF rendering."""

    return line.replace("`", "").strip()


def _markdown_lines_to_story(lines: list[str], story: list[object], styles: dict[str, ParagraphStyle]) -> None:
    """Render simple README paragraph and bullet lines into platypus flowables."""

    for line in lines:
        cleaned = _clean_markdown_text(line)
        if not cleaned:
            continue
        if cleaned.startswith("- "):
            story.append(Paragraph(f"• {cleaned[2:]}", styles["BulletBody"]))
        else:
            story.append(Paragraph(cleaned, styles["Body"]))
        story.append(Spacer(1, 2.5 * mm))


def _safe_ratio(numerator: float, denominator: float) -> float:
    """Return a defensive ratio."""

    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def _table_from_frame(frame: pd.DataFrame, max_rows: int | None = None) -> list[list[str]]:
    """Convert a DataFrame into a reportlab-ready table payload."""

    trimmed = frame if max_rows is None else frame.head(max_rows)
    rows = [list(trimmed.columns)]
    for record in trimmed.itertuples(index=False):
        row: list[str] = []
        for value in record:
            if isinstance(value, float):
                row.append(f"{value:,.3f}")
            else:
                row.append(str(value))
        rows.append(row)
    return rows


def _make_table(data: list[list[str]], column_widths: list[float] | None = None) -> Table:
    """Build a lightly styled table."""

    table = Table(data, colWidths=column_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9E2F3")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _build_case_result(case_name: str, portfolio_path: str, config) -> dict[str, object]:
    """Compute structured report content for one fixed demo case."""

    portfolio, resolved_path = load_or_generate_portfolio(
        config=config,
        project_root=PROJECT_ROOT,
        portfolio_path=Path(portfolio_path),
        generate=False,
    )
    shocks = build_standard_rate_shocks(config)
    scenarios = build_stress_scenarios(config)
    combined = scenarios["combined"]

    portfolio_frame = portfolio.to_frame()
    total_assets = portfolio.total_assets()
    total_liabilities = portfolio.total_liabilities()
    total_equity = portfolio.total_equity()
    lcr = calculate_lcr(portfolio, config)
    nsfr = calculate_nsfr(portfolio, config)
    nii_parallel_up = calculate_12m_nii_sensitivity(portfolio, config, shocks["parallel_up"])
    eve_parallel_up = calculate_eve_sensitivity(portfolio, config, shocks["parallel_up"])
    stress_summary = run_stress_tests(portfolio, config, scenarios)
    action_result = run_management_action_plan(portfolio, config, combined)
    management_actions = action_log_table(action_result.action_log)

    headline = summary_table(
        {
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "total_equity": total_equity,
            "lcr": lcr.ratio,
            "nsfr": nsfr.ratio,
            "delta_nii_parallel_up": nii_parallel_up.total_delta_nii,
            "delta_eve_parallel_up": eve_parallel_up.delta_eve,
        }
    )

    combined_row = stress_summary.loc[stress_summary["scenario"] == "combined"].iloc[0]
    action_names = list(management_actions.get("action_name", pd.Series(dtype=object)))

    return {
        "case_name": case_name,
        "portfolio_path": resolved_path,
        "headline": headline,
        "stress_summary": stress_summary,
        "management_actions": management_actions,
        "comparison": action_result.comparison,
        "action_names": action_names,
        "summary_metrics": {
            "total_assets": total_assets,
            "mortgage_share": _safe_ratio(
                float(portfolio_frame.loc[portfolio_frame["product_type"] == "fixed_mortgages", "notional"].sum()),
                total_assets,
            ),
            "hqla_share": _safe_ratio(
                float(portfolio_frame.loc[portfolio_frame["hqla_level"] == "level1", "notional"].sum()),
                total_assets,
            ),
            "interbank_share": _safe_ratio(
                float(portfolio_frame.loc[portfolio_frame["product_type"] == "interbank_borrowing", "notional"].sum()),
                total_assets,
            ),
            "equity_ratio": _safe_ratio(total_equity, total_assets),
            "base_lcr": lcr.ratio,
            "base_nsfr": nsfr.ratio,
            "delta_nii_parallel_up": nii_parallel_up.total_delta_nii,
            "delta_eve_parallel_up": eve_parallel_up.delta_eve,
            "stressed_lcr": float(combined_row["lcr"]),
            "stressed_nsfr": float(combined_row["nsfr"]),
            "stressed_delta_nii": float(combined_row["delta_nii_12m"]),
            "stressed_delta_eve": float(combined_row["delta_eve"]),
            "post_action_lcr": float(
                action_result.post_action_metrics.loc[action_result.post_action_metrics["metric"] == "lcr", "value"].iloc[0]
            ),
            "post_action_delta_nii": float(
                action_result.post_action_metrics.loc[
                    action_result.post_action_metrics["metric"] == "total_delta_nii", "value"
                ].iloc[0]
            ),
            "post_action_delta_eve": float(
                action_result.post_action_metrics.loc[
                    action_result.post_action_metrics["metric"] == "total_delta_eve", "value"
                ].iloc[0]
            ),
            "action_count": float(len(management_actions)),
        },
    }


def _case_interpretation(case_result: dict[str, object]) -> str:
    """Return a concise analyst-style interpretation for one demo case."""

    case_name = str(case_result["case_name"])
    metrics = case_result["summary_metrics"]
    action_names = case_result["action_names"]

    if case_name == "balanced":
        return (
            f"The balanced case starts with strong liquidity buffers (base LCR {metrics['base_lcr']:.2f}) "
            f"and remains above the combined-stress action threshold (stressed LCR {metrics['stressed_lcr']:.2f}). "
            "It functions as the stable reference portfolio and shows that the framework can produce a clean no-action outcome."
        )
    if case_name == "liquidity_tight":
        action_text = ", ".join(action_names) if action_names else "liquidity support actions"
        return (
            f"The liquidity-tight case enters stress with a materially thinner buffer (stressed LCR {metrics['stressed_lcr']:.2f}) "
            f"and triggers {action_text}. Post-action LCR improves to {metrics['post_action_lcr']:.2f}, "
            f"but stressed NII moves from {metrics['stressed_delta_nii']:.3f} to {metrics['post_action_delta_nii']:.3f}, "
            "illustrating the liquidity-versus-earnings trade-off."
        )
    return (
        f"The IRRBB-heavy case carries the strongest parallel-up EVE sensitivity ({metrics['delta_eve_parallel_up']:.3f}) "
        f"because of its longer fixed-rate asset mix. Liquidity remains serviceable (stressed LCR {metrics['stressed_lcr']:.2f}), "
        "so the simplified hedge placeholder becomes the relevant response rather than a liquidity action."
    )


def _comparison_table(case_results: list[dict[str, object]]) -> pd.DataFrame:
    """Build a compact cross-case comparison table."""

    rows = []
    for result in case_results:
        metrics = result["summary_metrics"]
        rows.append(
            {
                "case": result["case_name"],
                "total_assets": metrics["total_assets"],
                "base_lcr": metrics["base_lcr"],
                "stressed_lcr": metrics["stressed_lcr"],
                "post_action_lcr": metrics["post_action_lcr"],
                "delta_nii_parallel_up": metrics["delta_nii_parallel_up"],
                "delta_eve_parallel_up": metrics["delta_eve_parallel_up"],
                "action_count": metrics["action_count"],
            }
        )
    return pd.DataFrame(rows)


def _build_styles() -> dict[str, ParagraphStyle]:
    """Create a small set of consistent report styles."""

    stylesheet = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle(
            "TitleCustom",
            parent=stylesheet["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=28,
            textColor=colors.HexColor("#111827"),
            spaceAfter=12,
        ),
        "Subtitle": ParagraphStyle(
            "SubtitleCustom",
            parent=stylesheet["Heading2"],
            fontName="Helvetica",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#4B5563"),
            spaceAfter=10,
        ),
        "Section": ParagraphStyle(
            "SectionCustom",
            parent=stylesheet["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=20,
            textColor=colors.HexColor("#111827"),
            spaceBefore=8,
            spaceAfter=8,
        ),
        "Subsection": ParagraphStyle(
            "SubsectionCustom",
            parent=stylesheet["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#1F2937"),
            spaceBefore=6,
            spaceAfter=4,
        ),
        "Body": ParagraphStyle(
            "BodyCustom",
            parent=stylesheet["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#1F2937"),
        ),
        "BulletBody": ParagraphStyle(
            "BulletBodyCustom",
            parent=stylesheet["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            leftIndent=10,
            textColor=colors.HexColor("#1F2937"),
        ),
        "Small": ParagraphStyle(
            "SmallCustom",
            parent=stylesheet["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#6B7280"),
        ),
    }


def _add_page_number(canvas, doc) -> None:  # type: ignore[no-untyped-def]
    """Draw a compact footer page number."""

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")


def build_pdf_report(output_path: Path) -> Path:
    """Generate the PDF report and return its path."""

    config = load_config(PROJECT_ROOT / "data" / "assumptions" / "base_assumptions.yaml")
    readme_sections = _extract_markdown_sections(PROJECT_ROOT / "README.md")
    styles = _build_styles()

    case_results = [_build_case_result(case_name, portfolio_path, config) for case_name, portfolio_path in DEMO_CASES]
    comparison = _comparison_table(case_results)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
    )
    story: list[object] = []

    story.append(Spacer(1, 40 * mm))
    story.append(Paragraph("bank-alm-risk-engine", styles["Title"]))
    story.append(Paragraph("ALM Risk Engine – Demo Case Analysis", styles["Subtitle"]))
    story.append(Spacer(1, 8 * mm))
    story.append(
        Paragraph(
            f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            styles["Small"],
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            "This report summarizes the project design and compares three fixed showcase portfolios "
            "using the existing ALM risk engine.",
            styles["Body"],
        )
    )
    story.append(PageBreak())

    story.append(Paragraph("Section 1. Executive Summary", styles["Section"]))
    _markdown_lines_to_story(readme_sections.get("Project Motivation", []), story, styles)

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Section 2. Architecture Overview", styles["Section"]))
    _markdown_lines_to_story(readme_sections.get("What This Project Demonstrates", []), story, styles)

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Section 3. Demo Cases Comparison", styles["Section"]))
    story.append(
        _make_table(
            _table_from_frame(comparison),
            column_widths=[28 * mm, 24 * mm, 20 * mm, 22 * mm, 24 * mm, 27 * mm, 27 * mm, 18 * mm],
        )
    )

    for index, result in enumerate(case_results, start=4):
        story.append(PageBreak())
        story.append(Paragraph(f"Section {index}. Demo Case: {result['case_name']}", styles["Section"]))
        story.append(Paragraph(str(result["portfolio_path"]), styles["Small"]))
        story.append(Spacer(1, 2 * mm))

        story.append(Paragraph("Portfolio Summary", styles["Subsection"]))
        story.append(_make_table(_table_from_frame(result["headline"]), column_widths=[55 * mm, 35 * mm]))
        story.append(Spacer(1, 4 * mm))

        story.append(Paragraph("Stress Summary", styles["Subsection"]))
        story.append(
            _make_table(
                _table_from_frame(result["stress_summary"]),
                column_widths=[28 * mm, 26 * mm, 24 * mm, 16 * mm, 16 * mm, 42 * mm],
            )
        )
        story.append(Spacer(1, 4 * mm))

        story.append(Paragraph("Management Actions", styles["Subsection"]))
        management_actions = result["management_actions"]
        if management_actions.empty:
            story.append(Paragraph("No management actions were triggered under the combined stress scenario.", styles["Body"]))
        else:
            compact_actions = management_actions.reindex(
                columns=["step", "action_name", "amount", "trigger", "delta_nii_change", "lcr_after"]
            )
            story.append(
                _make_table(
                    _table_from_frame(compact_actions),
                    column_widths=[12 * mm, 58 * mm, 18 * mm, 20 * mm, 24 * mm, 18 * mm],
                )
            )
        story.append(Spacer(1, 4 * mm))

        story.append(Paragraph("Interpretation", styles["Subsection"]))
        story.append(Paragraph(_case_interpretation(result), styles["Body"]))

    story.append(PageBreak())
    story.append(Paragraph("Section 7. Key Insights", styles["Section"]))
    insights = [
        "Liquidity support actions improve short-term liquidity ratios, but they can worsen stressed NII through higher funding spreads.",
        "IRRBB and liquidity risk behave differently across the three demo cases: the liquidity-tight case is action-driven, while the IRRBB-heavy case is valuation-sensitive.",
        "Balance-sheet structure matters: mortgage share, HQLA share, and wholesale funding share are enough to create visibly different stress outcomes even without changing the core engine.",
    ]
    for insight in insights:
        story.append(Paragraph(f"• {insight}", styles["BulletBody"]))
        story.append(Spacer(1, 2 * mm))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Known Limitations", styles["Subsection"]))
    _markdown_lines_to_story(readme_sections.get("Known Limitations", []), story, styles)

    doc.build(story, onFirstPage=_add_page_number, onLaterPages=_add_page_number)
    return output_path


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for PDF generation."""

    parser = argparse.ArgumentParser(description="Generate a PDF report for the three fixed ALM demo cases.")
    parser.add_argument(
        "--output",
        default="outputs/reports/alm_demo_case_analysis.pdf",
        help="Output PDF path relative to the project root.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    report_path = build_pdf_report(output_path)
    print(f"PDF report written to {report_path}")


if __name__ == "__main__":
    main()
