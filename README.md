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

The unofficial [weathercloud-js](https://github.com/maxime-mrl/weathercloud-js) project reads the current station values. This project has a matching Python command that records observations as monthly JSON Lines files under `data/weathercloud-observations/`. Each record contains the local timestamp, temperature, daily rainfall total, and rain rate. The plots combine those records with the existing CSV exports.

Fetch the latest update manually with your station ID (9–10 digits, optionally prefixed with `d`):

```sh
uv run update-rainfall --station-id d7978634673
uv run plot-rainfall
```

The GitHub Actions workflow in `.github/workflows/collect-weathercloud.yml` runs every 10 minutes and commits new readings to the default branch. It can also be run manually from the repository's Actions page. The station ID is a public identifier configured in the workflow; no API password or GitHub secret is needed. Repository Actions settings must allow workflows to write contents.

This uses Weathercloud's unofficial, reverse-engineered API, which may change. Its historical graph endpoint is listed as experimental, so the collector adds readings going forward and does not backfill missing months. GitHub scheduled workflows can start late during periods of high load and only run from the default branch. The API's rain field is the cumulative total for the station's local day, so use `--timezone` if the station is outside `Europe/Vienna`.

## GitHub Pages dashboard

The dashboard generator uses Plotly to produce interactive charts in a static HTML page. It includes annual totals, month and day comparisons, a monthly heatmap, and temperature history. Plotly lets visitors hover, zoom, and show or hide years; the existing Matplotlib command remains available for local PNG plots.

Generate the page locally with:

```sh
uv run build-rainfall-dashboard --data-dir data --output-dir site
```

The `Build and publish weather dashboard` workflow deploys on changes to the main branch and after successful Weathercloud collection runs. To enable the first Pages deployment, open **Settings → Pages → Build and deployment** and set **Source** to **GitHub Actions**. The deployed URL is shown on the workflow's deployment environment in GitHub.
