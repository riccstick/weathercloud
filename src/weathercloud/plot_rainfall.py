"""Plot monthly rainfall totals from Weathercloud CSV exports."""

from __future__ import annotations

import argparse
import calendar
import codecs
import csv
import io
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch


@dataclass(frozen=True)
class MonthlyRainfall:
    total_mm: float
    days_with_readings: int
    days_in_month: int

    @property
    def missing_days(self) -> int:
        return self.days_in_month - self.days_with_readings


@dataclass(frozen=True)
class YearlyRainfall:
    total_mm: float
    months_with_readings: int
    missing_months: int
    missing_days: int

    @property
    def is_complete(self) -> bool:
        return self.missing_months == 0 and self.missing_days == 0


def decode_csv(path: Path) -> str:
    """Decode Weathercloud's UTF-16 exports and UTF-8 variants."""
    raw = path.read_bytes()
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return raw.decode("utf-16")
    if b"\x00" in raw[:128]:
        return raw.decode("utf-16-le")
    return raw.decode("utf-8-sig")


def parse_timestamp(value: str) -> datetime:
    value = value.strip()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.strptime(value, "%d/%m/%Y %H:%M:%S")


def load_daily_rainfall(data_dir: Path) -> dict[date, float]:
    """Read the maximum recorded rain value for each calendar date."""
    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    daily_maxima: dict[date, float] = {}
    for path in csv_files:
        reader = csv.DictReader(io.StringIO(decode_csv(path)), delimiter=";")
        if not reader.fieldnames or "Regen (mm)" not in reader.fieldnames:
            raise ValueError(f"{path} does not contain a 'Regen (mm)' column")

        date_column = reader.fieldnames[0]
        for line_number, row in enumerate(reader, start=2):
            raw_rain = (row.get("Regen (mm)") or "").strip()
            if not raw_rain:
                continue

            raw_date = (row.get(date_column) or "").strip()
            try:
                observation_date = parse_timestamp(raw_date).date()
                rain_mm = float(raw_rain.replace(",", "."))
            except ValueError as exc:
                raise ValueError(
                    f"Could not parse date or rain value in {path} at line {line_number}"
                ) from exc
            if not math.isfinite(rain_mm) or rain_mm < 0:
                raise ValueError(f"Invalid rain value {raw_rain!r} in {path} at line {line_number}")

            previous = daily_maxima.get(observation_date, 0.0)
            daily_maxima[observation_date] = max(previous, rain_mm)

    return daily_maxima


def summarize_monthly_rainfall(daily_rainfall: dict[date, float]) -> dict[tuple[int, int], MonthlyRainfall]:
    """Sum each day's maximum rain reading into calendar-month totals."""
    daily_by_month: dict[tuple[int, int], dict[date, float]] = defaultdict(dict)
    for observation_date, rain_mm in daily_rainfall.items():
        daily_by_month[(observation_date.year, observation_date.month)][observation_date] = rain_mm

    monthly: dict[tuple[int, int], MonthlyRainfall] = {}
    for (year, month), daily_readings in daily_by_month.items():
        days_in_month = calendar.monthrange(year, month)[1]
        monthly[(year, month)] = MonthlyRainfall(
            total_mm=sum(daily_readings.values()),
            days_with_readings=len(daily_readings),
            days_in_month=days_in_month,
        )
    return monthly


def plot_monthly_rainfall(monthly: dict[tuple[int, int], MonthlyRainfall], output: Path) -> None:
    years = sorted({year for year, _month in monthly})
    if not years:
        raise ValueError("No rainfall observations found in the CSV files")

    colors = plt.get_cmap("tab10")
    group_width = 0.82
    bar_width = group_width / len(years)
    has_partial_months = any(total.missing_days for total in monthly.values())

    fig, ax = plt.subplots(figsize=(13, 7))
    for year_index, year in enumerate(years):
        color = colors(year_index % 10)
        offset = (year_index - (len(years) - 1) / 2) * bar_width
        for month in range(1, 13):
            total = monthly.get((year, month))
            if total is None:
                continue
            position = (month - 1) + offset
            bar = ax.bar(position, total.total_mm, width=bar_width * 0.92, color=color)[0]
            if total.missing_days:
                bar.set_hatch("///")
                bar.set_edgecolor("white")

    legend_handles = [
        Patch(facecolor=colors(index % 10), label=str(year))
        for index, year in enumerate(years)
    ]
    if has_partial_months:
        legend_handles.append(
            Patch(facecolor="white", edgecolor="0.4", hatch="///", label="Missing daily readings")
        )
    ax.legend(handles=legend_handles, title="Year", ncols=min(6, len(legend_handles)), frameon=False)
    ax.set_title("Monthly rainfall by year")
    ax.set_xlabel("Month")
    ax.set_ylabel("Rainfall (mm)")
    ax.set_xticks(range(12), [calendar.month_abbr[month] for month in range(1, 13)])
    ax.set_xlim(-0.6, 11.6)
    maximum = max(total.total_mm for total in monthly.values())
    ax.set_ylim(0, max(10, maximum * 1.15))
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=0.3)
    fig.text(
        0.01,
        0.01,
        "Each total sums daily maximum Regen (mm) readings. Hatched bars have days without readings; blank months have no CSV data.",
        ha="left",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_monthly_overlay(monthly: dict[tuple[int, int], MonthlyRainfall], output: Path) -> None:
    if not monthly:
        raise ValueError("No rainfall observations found in the CSV files")

    years = sorted({year for year, _month in monthly})
    months = range(1, 13)
    colors = plt.get_cmap("tab10")
    has_partial_months = any(total.missing_days for total in monthly.values())

    fig, ax = plt.subplots(figsize=(13, 6))
    for year_index, year in enumerate(years):
        color = colors(year_index % 10)
        values = [monthly[(year, month)].total_mm if (year, month) in monthly else math.nan for month in months]
        ax.plot(months, values, color=color, marker="o", markersize=4, linewidth=1.6, label=str(year))

        partial = [
            (month, monthly[(year, month)].total_mm)
            for month in range(1, 13)
            if (year, month) in monthly and monthly[(year, month)].missing_days
        ]
        if partial:
            ax.scatter(
                [month for month, _value in partial],
                [value for _month, value in partial],
                s=48,
                facecolors="white",
                edgecolors=[color],
                linewidths=1.4,
                zorder=3,
            )

    if has_partial_months:
        ax.scatter([], [], s=48, facecolors="white", edgecolors="0.4", linewidths=1.4, label="Partial month")

    ax.set_title("Monthly rainfall by year")
    ax.set_xlabel("Month")
    ax.set_ylabel("Rainfall (mm)")
    ax.set_xticks(list(months), [calendar.month_abbr[month] for month in months])
    ax.set_xlim(0.7, 12.3)
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=0.3)
    ax.legend(title="Year", frameon=False, ncols=min(3, len(years) + int(has_partial_months)))
    fig.text(
        0.01,
        0.01,
        "Lines compare the same calendar month across years. Gaps mark months without data; open circles mark partial months.",
        ha="left",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_monthly_heatmap(monthly: dict[tuple[int, int], MonthlyRainfall], output: Path) -> None:
    if not monthly:
        raise ValueError("No monthly rainfall observations found in the CSV files")

    years = sorted({year for year, _month in monthly})
    months = list(range(1, 13))
    values = [
        [monthly[(year, month)].total_mm if (year, month) in monthly else math.nan for month in months]
        for year in years
    ]
    maximum = max(total.total_mm for total in monthly.values())
    color_map = plt.get_cmap("Blues").copy()
    color_map.set_bad("#dedede")

    fig, ax = plt.subplots(figsize=(13, 5.5))
    image = ax.imshow(values, aspect="auto", interpolation="nearest", cmap=color_map, vmin=0, vmax=maximum)
    ax.set_title("Monthly rainfall by year")
    ax.set_xlabel("Month")
    ax.set_ylabel("Year")
    ax.set_xticks(range(12), [calendar.month_abbr[month] for month in months])
    ax.set_yticks(range(len(years)), [str(year) for year in years])
    ax.set_xticks([index - 0.5 for index in range(13)], minor=True)
    ax.set_yticks([index - 0.5 for index in range(len(years) + 1)], minor=True)
    ax.grid(which="minor", color="white", linewidth=1.2)
    ax.tick_params(which="minor", bottom=False, left=False)
    ax.set_xlim(-0.5, 11.5)
    ax.set_ylim(len(years) - 0.5, -0.5)

    for year_index, year in enumerate(years):
        for month_index, month in enumerate(months):
            total = monthly.get((year, month))
            if total is None:
                label = "—"
                text_color = "#333333"
            else:
                label = f"{total.total_mm:.1f}" + ("*" if total.missing_days else "")
                red, green, blue, _alpha = color_map(image.norm(total.total_mm))
                luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
                text_color = "white" if luminance < 0.42 else "#111111"
            ax.text(month_index, year_index, label, ha="center", va="center", color=text_color, fontsize=8.5)

    colorbar = fig.colorbar(image, ax=ax, pad=0.02)
    colorbar.set_label("Rainfall (mm)")
    fig.text(
        0.01,
        0.01,
        "Dashes mark months without CSV rainfall data. * marks a partial month with one or more days lacking readings.",
        ha="left",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_daily_overlay(daily_rainfall: dict[date, float], output: Path) -> None:
    if not daily_rainfall:
        raise ValueError("No daily rainfall observations found in the CSV files")

    values_by_year: dict[int, dict[int, float]] = defaultdict(dict)
    for observation_date, rain_mm in daily_rainfall.items():
        day_of_year = observation_date.timetuple().tm_yday
        if not calendar.isleap(observation_date.year) and observation_date.month > 2:
            day_of_year += 1
        values_by_year[observation_date.year][day_of_year] = rain_mm

    years = sorted(values_by_year)
    day_indexes = list(range(1, 367))
    colors = plt.get_cmap("tab10")
    fig, ax = plt.subplots(figsize=(13, 6))
    for year_index, year in enumerate(years):
        year_values = values_by_year[year]
        values = [year_values.get(day_index, math.nan) for day_index in day_indexes]
        ax.plot(
            day_indexes,
            values,
            color=colors(year_index % 10),
            linewidth=1.1,
            alpha=0.85,
            label=str(year),
        )

    month_starts = [date(2000, month, 1).timetuple().tm_yday for month in range(1, 13)]
    ax.set_title("Daily rainfall by year")
    ax.set_xlabel("Day of year (month ticks)")
    ax.set_ylabel("Daily rainfall (mm)")
    ax.set_xlim(1, 366)
    ax.set_xticks(month_starts, [calendar.month_abbr[month] for month in range(1, 13)])
    ax.set_ylim(bottom=0)
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=0.3)
    ax.legend(title="Year", frameon=False, ncols=min(5, len(years)))
    fig.text(
        0.01,
        0.01,
        "Each value is the maximum Regen (mm) reading for that date. Missing dates are gaps; Feb 29 is aligned across years.",
        ha="left",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def summarize_yearly_rainfall(
    monthly: dict[tuple[int, int], MonthlyRainfall],
) -> dict[int, YearlyRainfall]:
    by_year: dict[int, list[MonthlyRainfall]] = defaultdict(list)
    for (year, _month), total in monthly.items():
        by_year[year].append(total)

    yearly: dict[int, YearlyRainfall] = {}
    for year, months in by_year.items():
        yearly[year] = YearlyRainfall(
            total_mm=sum(month.total_mm for month in months),
            months_with_readings=len(months),
            missing_months=12 - len(months),
            missing_days=sum(month.missing_days for month in months),
        )
    return yearly


def plot_yearly_rainfall(monthly: dict[tuple[int, int], MonthlyRainfall], output: Path) -> None:
    yearly = summarize_yearly_rainfall(monthly)
    if not yearly:
        raise ValueError("No rainfall observations found in the CSV files")

    years = sorted(yearly)
    totals = [yearly[year].total_mm for year in years]
    positions = range(len(years))
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(positions, totals, color=plt.get_cmap("tab10")(0))

    for bar, year in zip(bars, years):
        if not yearly[year].is_complete:
            bar.set_hatch("///")
            bar.set_edgecolor("white")

    ax.bar_label(bars, labels=[f"{value:.1f}" for value in totals], padding=4, fontsize=9)
    ax.set_title("Annual rainfall totals")
    ax.set_ylabel("Rainfall (mm)")
    ax.set_xlabel("Year (months with rainfall data)")
    ax.set_xticks(
        list(positions),
        [f"{year}\n{yearly[year].months_with_readings}/12 months" for year in years],
    )
    ax.set_ylim(0, max(totals) * 1.16)
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=0.3)

    if any(not total.is_complete for total in yearly.values()):
        ax.legend(
            handles=[Patch(facecolor="white", edgecolor="0.4", hatch="///", label="Incomplete year")],
            frameon=False,
        )
    fig.text(
        0.01,
        0.01,
        "Totals sum available daily maxima. Hatched bars have missing months or days, so they are partial totals.",
        ha="left",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot monthly rainfall by year from Weathercloud CSV files.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="directory containing CSV files")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("plots/monthly-rainfall.png"),
        help="path for the generated monthly PNG plot",
    )
    parser.add_argument(
        "--yearly-output",
        type=Path,
        default=Path("plots/yearly-rainfall.png"),
        help="path for the generated annual-total PNG plot",
    )
    parser.add_argument(
        "--overlay-output",
        type=Path,
        default=Path("plots/monthly-rainfall-overlay.png"),
        help="path for the generated monthly year-comparison PNG plot",
    )
    parser.add_argument(
        "--daily-output",
        type=Path,
        default=Path("plots/daily-rainfall-overlay.png"),
        help="path for the generated daily year-comparison PNG plot",
    )
    parser.add_argument(
        "--heatmap-output",
        type=Path,
        default=Path("plots/monthly-rainfall-heatmap.png"),
        help="path for the generated monthly year-by-month heatmap PNG plot",
    )
    args = parser.parse_args()

    daily_rainfall = load_daily_rainfall(args.data_dir)
    monthly = summarize_monthly_rainfall(daily_rainfall)
    plot_monthly_rainfall(monthly, args.output)
    plot_yearly_rainfall(monthly, args.yearly_output)
    plot_monthly_overlay(monthly, args.overlay_output)
    plot_daily_overlay(daily_rainfall, args.daily_output)
    plot_monthly_heatmap(monthly, args.heatmap_output)
    print(f"Saved monthly rainfall plot to {args.output}")
    print(f"Saved annual rainfall plot to {args.yearly_output}")
    print(f"Saved monthly overlay plot to {args.overlay_output}")
    print(f"Saved daily overlay plot to {args.daily_output}")
    print(f"Saved monthly heatmap to {args.heatmap_output}")


if __name__ == "__main__":
    main()
