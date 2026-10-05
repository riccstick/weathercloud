# Weathercloud

Plot monthly rainfall from Weathercloud CSV exports in `data/`.

## Setup

Install [uv](https://docs.astral.sh/uv/), then create the project environment and install its locked dependencies:

```sh
uv sync
```

## Generate the plot

```sh
uv run plot-rainfall
```

This writes `plots/monthly-rainfall.png`, `plots/yearly-rainfall.png`, `plots/monthly-rainfall-overlay.png`, `plots/daily-rainfall-overlay.png`, and `plots/monthly-rainfall-heatmap.png`. The annual plot sums the available monthly totals. Hatched annual bars are partial because one or more months or days are missing; the x-axis shows how many months have data. The monthly overlay puts Jan–Dec on one axis and draws a separate line for each year. The daily overlay aligns days of the year and draws one line per year. The heatmap puts months across and years down, with cell color and labels showing monthly totals. Gaps mark dates or months without data.

Choose another input directory or output paths with:

```sh
uv run plot-rainfall --data-dir data --output plots/monthly.png --yearly-output plots/yearly.png --overlay-output plots/monthly-overlay.png --daily-output plots/daily-overlay.png --heatmap-output plots/heatmap.png
```

The plot compares calendar-month rainfall across years. For each date, the script takes the maximum `Regen (mm)` reading, then sums those daily values. Hatched bars indicate at least one day without rain readings; months with no CSV data have no bar.
