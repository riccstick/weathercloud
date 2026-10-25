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

## Update from Weathercloud

The unofficial [weathercloud-js](https://github.com/maxime-mrl/weathercloud-js) project reads the current station values. This project has a matching Python command that records observations as monthly JSON Lines files under `data/weathercloud-observations/<station-id>/`. Each record contains its station ID, local timestamp, temperature, daily rainfall total, and rain rate. The existing CSV exports provide historical rainfall for Langau 124 (`7978634673`); Wolfsbach 28 (`7139585049`) is collected going forward. Both stations use the `Europe/Vienna` timezone.

Fetch the latest update manually with your station ID (9–10 digits, optionally prefixed with `d`):

```sh
uv run update-rainfall --station-id d7978634673
uv run update-rainfall --station-id d7139585049
uv run plot-rainfall
```

The GitHub Actions workflow in `.github/workflows/collect-weathercloud.yml` collects both stations every 10 minutes and commits new readings to the default branch. Run `uv run plot-rainfall --station-id d7139585049` to generate local PNG charts for Wolfsbach 28. The IDs are public identifiers; no API password or GitHub secret is needed. Repository Actions settings must allow workflows to write contents.

This uses Weathercloud's unofficial, reverse-engineered API, which may change. Its historical graph endpoint is listed as experimental, so the collector adds readings going forward and does not backfill missing months. GitHub scheduled workflows can start late during periods of high load and only run from the default branch. The API's rain field is the cumulative total for the station's local day; both configured stations use `Europe/Vienna`.

## GitHub Pages dashboard

The dashboard generator uses Plotly to produce interactive charts in a static HTML page. It includes annual totals, month and day comparisons, a monthly heatmap, and temperature history. Plotly lets visitors hover, zoom, and show or hide years; the existing Matplotlib command remains available for local PNG plots.

Generate the page locally with:

```sh
uv run build-rainfall-dashboard --data-dir data --output-dir site
```

The `Build and publish weather dashboard` workflow deploys once a day at 01:17 UTC. New Weathercloud readings continue to be collected every 10 minutes, then appear in the dashboard after its daily rebuild. Dashboard code and dependency changes deploy on push, and the workflow can be run manually from the Actions page. To enable Pages, open **Settings → Pages → Build and deployment** and set **Source** to **GitHub Actions**. The deployed URL is shown on the workflow's deployment environment in GitHub.
