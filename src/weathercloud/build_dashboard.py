"""Build a static HTML dashboard of rainfall and temperature."""

from __future__ import annotations

import argparse
import calendar
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
from plotly.colors import qualitative

from weathercloud.plot_rainfall import (
    load_daily_rainfall,
    summarize_monthly_rainfall,
    summarize_yearly_rainfall,
)


PLOTLY_JS = "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@4.1.1/plotly.min.js"
OBSERVATIONS_DIR = "weathercloud-observations"


def load_observations(data_dir: Path) -> list[dict[str, object]]:
    observations: list[dict[str, object]] = []
    for path in sorted((data_dir / OBSERVATIONS_DIR).glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as jsonl_file:
            for line_number, line in enumerate(jsonl_file, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON in {path} at line {line_number}") from exc
                if not isinstance(record, dict):
                    raise ValueError(f"Expected an observation object in {path} at line {line_number}")
                if not isinstance(record.get("timestamp"), str):
                    raise ValueError(f"Missing timestamp in {path} at line {line_number}")
                observations.append(record)
    observations.sort(key=lambda record: int(record["epoch"]))
    return observations


def base_figure(title: str, height: int = 420) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        title={"text": title, "x": 0.02, "xanchor": "left"},
        template="plotly_white",
        height=height,
        margin={"l": 58, "r": 24, "t": 64, "b": 54},
        font={"family": "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", "size": 13},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        legend={"title": {"text": "Year"}, "orientation": "h", "y": -0.24},
        colorway=qualitative.Plotly,
    )
    figure.update_xaxes(showgrid=False, zeroline=False)
    figure.update_yaxes(showgrid=True, gridcolor="#e5e9ef", zeroline=False)
    return figure


def make_yearly_chart(monthly: dict) -> go.Figure:
    yearly = summarize_yearly_rainfall(monthly)
    years = sorted(yearly)
    figure = base_figure("Annual rainfall", 360)
    figure.add_bar(
        x=[str(year) for year in years],
        y=[yearly[year].total_mm for year in years],
        marker_color="#2581a8",
        text=[f"{yearly[year].total_mm:.1f}" for year in years],
        textposition="outside",
        customdata=[
            [yearly[year].months_with_readings, yearly[year].missing_days]
            for year in years
        ],
        hovertemplate=(
            "Year %{x}<br>%{y:.1f} mm"
            "<br>Months with readings: %{customdata[0]}/12"
            "<br>Days without readings: %{customdata[1]}<extra></extra>"
        ),
    )
    figure.update_layout(showlegend=False, hovermode="closest")
    figure.update_yaxes(title_text="Rainfall (mm)", rangemode="tozero")
    figure.update_xaxes(title_text="Year")
    return figure


def make_monthly_overlay(monthly: dict) -> go.Figure:
    years = sorted({year for year, _month in monthly})
    month_numbers = list(range(1, 13))
    figure = base_figure("Monthly rainfall by year")
    for year_index, year in enumerate(years):
        values = [monthly.get((year, month)).total_mm if (year, month) in monthly else None for month in month_numbers]
        partial = [
            monthly[(year, month)].missing_days
            if (year, month) in monthly
            else None
            for month in month_numbers
        ]
        point_symbols = []
        for month in month_numbers:
            total = monthly.get((year, month))
            point_symbols.append("circle-open" if total and total.missing_days else "circle")
        figure.add_trace(
            go.Scatter(
                x=[calendar.month_abbr[month] for month in month_numbers],
                y=values,
                customdata=partial,
                mode="lines+markers",
                name=str(year),
                line={"width": 2},
                marker={"size": 7, "symbol": point_symbols},
                connectgaps=False,
                hovertemplate=(
                    "%{x}: %{y:.1f} mm"
                    "<br>Days without readings: %{customdata}"
                    "<extra>%{fullData.name}</extra>"
                ),
            )
        )
    figure.update_layout(hovermode="x unified")
    figure.update_yaxes(title_text="Rainfall (mm)", rangemode="tozero")
    figure.update_xaxes(title_text="Month")
    return figure


def make_daily_overlay(daily_rainfall: dict) -> go.Figure:
    values_by_year: dict[int, dict[int, float]] = defaultdict(dict)
    for observation_date, rain_mm in daily_rainfall.items():
        day_of_year = observation_date.timetuple().tm_yday
        if not calendar.isleap(observation_date.year) and observation_date.month > 2:
            day_of_year += 1
        values_by_year[observation_date.year][day_of_year] = rain_mm

    day_indexes = list(range(1, 367))
    month_starts = [datetime(2000, month, 1).timetuple().tm_yday for month in range(1, 13)]
    figure = base_figure("Daily rainfall by year")
    for year in sorted(values_by_year):
        by_day = values_by_year[year]
        figure.add_trace(
            go.Scatter(
                x=day_indexes,
                y=[by_day.get(day) for day in day_indexes],
                mode="lines",
                name=str(year),
                connectgaps=False,
                line={"width": 1.5},
                hovertemplate="Day %{x}: %{y:.1f} mm<extra>%{fullData.name}</extra>",
            )
        )
    figure.update_yaxes(title_text="Daily rainfall (mm)", rangemode="tozero")
    figure.update_xaxes(
        title_text="Day of year",
        range=[1, 366],
        tickmode="array",
        tickvals=month_starts,
        ticktext=[calendar.month_abbr[month] for month in range(1, 13)],
    )
    return figure


def make_heatmap(monthly: dict) -> go.Figure:
    years = sorted({year for year, _month in monthly})
    months = list(range(1, 13))
    values = [
        [monthly[(year, month)].total_mm if (year, month) in monthly else None for month in months]
        for year in years
    ]
    maximum = max((total.total_mm for total in monthly.values()), default=1.0) or 1.0
    figure = go.Figure(
        go.Heatmap(
            x=[calendar.month_abbr[month] for month in months],
            y=[str(year) for year in years],
            z=values,
            zmin=0,
            zmax=maximum,
            colorscale="Blues",
            colorbar={"title": {"text": "mm"}},
            hoverongaps=False,
            hovertemplate="%{y} %{x}: %{z:.1f} mm<extra></extra>",
        )
    )
    figure.update_layout(
        title={"text": "Monthly rainfall heatmap", "x": 0.02, "xanchor": "left"},
        template="plotly_white",
        height=max(360, 50 * len(years) + 130),
        margin={"l": 58, "r": 24, "t": 64, "b": 54},
        font={"family": "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", "size": 13},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    figure.update_xaxes(side="top")
    figure.update_yaxes(autorange="reversed")
    return figure


def make_temperature_chart(observations: list[dict[str, object]]) -> go.Figure:
    hourly: dict[datetime, list[float]] = defaultdict(list)
    for record in observations:
        raw_temperature = record.get("temperature_c")
        if raw_temperature is None:
            continue
        temperature = float(raw_temperature)
        if not math.isfinite(temperature):
            continue
        timestamp = datetime.fromisoformat(str(record["timestamp"]))
        hour = timestamp.replace(minute=0, second=0, microsecond=0)
        hourly[hour].append(temperature)

    buckets = sorted(hourly)
    figure = base_figure("Temperature history")
    figure.add_trace(
        go.Scatter(
            x=[bucket.isoformat() for bucket in buckets],
            y=[sum(hourly[bucket]) / len(hourly[bucket]) for bucket in buckets],
            mode="lines",
            name="Hourly average",
            line={"color": "#d97932", "width": 2},
            hovertemplate="%{x}<br>%{y:.1f} °C<extra></extra>",
        )
    )
    figure.update_layout(showlegend=False, hovermode="x")
    figure.update_yaxes(title_text="Temperature (°C)")
    figure.update_xaxes(title_text="Local time", type="date")
    return figure


def latest_summary(observations: list[dict[str, object]]) -> str:
    if not observations:
        return "No API observations have been recorded yet."
    latest = observations[-1]
    timestamp = datetime.fromisoformat(str(latest["timestamp"]))
    temperature = latest.get("temperature_c")
    temperature_text = "temperature unavailable" if temperature is None else f"{float(temperature):.1f} °C"
    rain = float(latest["rain_today_mm"])
    return (
        f"Latest station update: {timestamp:%d %b %Y, %H:%M %Z} · "
        f"{temperature_text} · {rain:.1f} mm rain today"
    )


def build_html(data_dir: Path, output_dir: Path) -> Path:
    daily_rainfall = load_daily_rainfall(data_dir)
    monthly = summarize_monthly_rainfall(daily_rainfall)
    observations = load_observations(data_dir)

    charts = [
        ("annual-rainfall", "Annual rainfall", make_yearly_chart(monthly)),
        ("monthly-overlay", "Compare months", make_monthly_overlay(monthly)),
        ("daily-overlay", "Compare days", make_daily_overlay(daily_rainfall)),
        ("temperature-history", "Temperature history", make_temperature_chart(observations)),
        ("monthly-heatmap", "Monthly heatmap", make_heatmap(monthly)),
    ]
    chart_markup: list[str] = []
    for index, (chart_id, heading, figure) in enumerate(charts):
        figure.update_layout(autosize=True, height=None)
        figure_html = figure.to_html(
            full_html=False,
            include_plotlyjs=PLOTLY_JS if index == 0 else False,
            config={"responsive": True, "displaylogo": False},
            default_height="440px",
            div_id=chart_id,
        )
        chart_markup.append(
            f'<section aria-labelledby="{chart_id}-heading">'
            f'<h2 id="{chart_id}-heading">{heading}</h2>{figure_html}</section>'
        )

    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Interactive rainfall and temperature history for the Langau weather station.">
  <title>Weathercloud · Rainfall and temperature</title>
  <style>
    :root {{ color-scheme: light; font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #17212b; background: #f4f7fa; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; }}
    main {{ width: min(1120px, calc(100% - 32px)); margin: 0 auto; padding: 30px 0 48px; }}
    header {{ margin-bottom: 18px; }}
    h1 {{ margin: 0 0 8px; font-size: clamp(1.65rem, 3vw, 2.25rem); font-weight: 600; letter-spacing: -0.025em; }}
    .latest {{ margin: 0; color: #44515e; }}
    section {{ margin-top: 18px; padding: 4px 0 14px; border-bottom: 1px solid #d8e0e8; }}
    h2 {{ margin: 0; font-size: 1.08rem; font-weight: 600; }}
    .chart-note {{ color: #52606d; font-size: .92rem; margin: 6px 0 0; }}
    @media (max-width: 520px) {{ main {{ width: min(100% - 20px, 1120px); padding-top: 20px; }} section {{ margin-top: 12px; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Rainfall and temperature</h1>
      <p class="latest">{latest_summary(observations)}</p>
    </header>
    <p class="chart-note">Rainfall totals use each day’s highest reported daily total. Gaps mark dates or months without readings; open circles mark partial months.</p>
    {''.join(chart_markup)}
  </main>
</body>
</html>
"""

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "index.html"
    output_file.write_text(page, encoding="utf-8")
    (output_dir / ".nojekyll").touch()
    return output_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an interactive static weather dashboard.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="directory containing rainfall files")
    parser.add_argument("--output-dir", type=Path, default=Path("site"), help="directory for the Pages site")
    args = parser.parse_args()
    output_file = build_html(args.data_dir, args.output_dir)
    print(f"Generated dashboard at {output_file}")


if __name__ == "__main__":
    main()
