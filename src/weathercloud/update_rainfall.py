"""Append the latest Weathercloud observation to a monthly JSON Lines file."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


API_URL = "https://app.weathercloud.net/device/values"
DEFAULT_OUTPUT_DIR = Path("data/weathercloud-observations")


def optional_number(payload: dict[str, object], key: str) -> float | None:
    value = payload.get(key)
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Weathercloud returned an invalid {key} value") from exc
    if not math.isfinite(number):
        raise RuntimeError(f"Weathercloud returned an invalid {key} value")
    return number


def fetch_current_observation(station_id: str) -> dict[str, object]:
    """Fetch the latest temperature and rain values for a station."""
    request = Request(
        f"{API_URL}?code={station_id}",
        data=b"",
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
            "User-Agent": "weathercloud-observation-collector/0.1",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Weathercloud request failed: {exc}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("Weathercloud returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Weathercloud returned an unexpected response")
    try:
        epoch = int(payload["epoch"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("Weathercloud response has no valid update time") from exc

    rain_today_mm = optional_number(payload, "rain")
    if rain_today_mm is None or rain_today_mm < 0:
        raise RuntimeError("Weathercloud response has no valid daily rain value")

    return {
        "epoch": epoch,
        "temperature_c": optional_number(payload, "temp"),
        "rain_today_mm": rain_today_mm,
        "rain_rate_mm_h": optional_number(payload, "rainrate"),
    }


def append_observation(output: Path, observation: dict[str, object], timezone: ZoneInfo) -> bool:
    """Append a new API update, skipping an epoch that is already stored."""
    epoch = int(observation["epoch"])
    observed_at = datetime.fromtimestamp(epoch, timezone)
    record = {
        "epoch": epoch,
        "timestamp": observed_at.isoformat(timespec="seconds"),
        "temperature_c": observation["temperature_c"],
        "rain_today_mm": observation["rain_today_mm"],
        "rain_rate_mm_h": observation["rain_rate_mm_h"],
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        with output.open("r", encoding="utf-8") as jsonl_file:
            for line_number, line in enumerate(jsonl_file, start=1):
                if not line.strip():
                    continue
                try:
                    previous = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON in {output} at line {line_number}") from exc
                if str(previous.get("epoch")) == str(epoch):
                    return False

    with output.open("a", encoding="utf-8", newline="") as jsonl_file:
        jsonl_file.write(json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch the latest Weathercloud temperature and rain observation."
    )
    parser.add_argument(
        "--station-id",
        default=os.environ.get("WEATHERCLOUD_STATION_ID"),
        help="Weathercloud station ID (9–10 digits, optionally prefixed with 'd'; or set WEATHERCLOUD_STATION_ID)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"directory for monthly JSONL files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--timezone",
        default="Europe/Vienna",
        help="station timezone used to assign each reading to a local day and month",
    )
    args = parser.parse_args()

    if not args.station_id:
        parser.error("provide --station-id or set WEATHERCLOUD_STATION_ID")
    match = re.fullmatch(r"d?(\d{9,10})", args.station_id, flags=re.IGNORECASE)
    if not match:
        parser.error("station ID must contain 9 or 10 digits, optionally prefixed with 'd'")
    station_id = match.group(1)
    try:
        timezone = ZoneInfo(args.timezone)
    except ZoneInfoNotFoundError:
        parser.error(f"unknown timezone: {args.timezone}")

    try:
        observation = fetch_current_observation(station_id)
        epoch = int(observation["epoch"])
        local_time = datetime.fromtimestamp(epoch, timezone)
        output = args.output_dir / f"{local_time:%Y-%m}.jsonl"
        added = append_observation(output, observation, timezone)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if added:
        temperature = observation["temperature_c"]
        temperature_text = "unavailable" if temperature is None else f"{float(temperature):g} °C"
        print(
            f"Recorded {temperature_text}, {float(observation['rain_today_mm']):g} mm rain today "
            f"at {local_time:%Y-%m-%d %H:%M:%S %Z} in {output}"
        )
    else:
        print(f"No new reading; Weathercloud still reports the update from {local_time:%Y-%m-%d %H:%M:%S %Z}")


if __name__ == "__main__":
    main()
