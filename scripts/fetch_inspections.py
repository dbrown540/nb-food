#!/usr/bin/env python3
"""Bulk-download SF DPH restaurant health inspections from the open-data portal.

SF DPH publishes three Socrata datasets on https://data.sf.gov (the old
data.sfgov.org host 301-redirects there). Scoring changed over time, so
they are NOT one schema:

  pyih-qa8i  2016-10 .. 2019-11  LIVES standard: numeric inspection_score
             (0-100) + per-violation rows with risk_category. Frozen; DPH
             says LIVES is "no longer used" since 2021.
  5tti-66ds  2020-03 .. 2023-08  Placard era: facility_status
             (PASS / CONDITIONAL PASS / CLOSURE) + per-violation rows
             (violation_observed severity + description). Frozen 2023-11.
  tvy3-wexg  2024-01 .. present  One row per inspection: facility_rating_status,
             violation_count, violation_codes (concatenated text).
             Refreshed monthly.

Writes (raw JSON is gitignored when large; compact CSV + meta committed):
  data/inspections/inspections_2016_2019.{json,csv,meta.json}
  data/inspections/current/inspections_2020_2023.{json,csv,meta.json}
  data/inspections/current/inspections_2024_present.{json,csv,meta.json}

Stdlib only. Idempotent: each run fully overwrites its outputs.
"""
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/inspections"
UA = "nb-food/0.1 (personal research; python-urllib)"
PAGE = 50000

# (dataset_id, output stem, date column, CSV columns as (csv_name, api_field))
DATASETS = [
    ("pyih-qa8i", OUT / "inspections_2016_2019", "inspection_date", [
        ("business_id", "business_id"), ("business_name", "business_name"),
        ("business_address", "business_address"), ("postal", "business_postal_code"),
        ("lat", "business_latitude"), ("lon", "business_longitude"),
        ("inspection_id", "inspection_id"), ("inspection_date", "inspection_date"),
        ("inspection_score", "inspection_score"), ("inspection_type", "inspection_type"),
        ("violation_id", "violation_id"),
        ("violation_description", "violation_description"),
        ("risk_category", "risk_category"),
    ]),
    ("5tti-66ds", OUT / "current/inspections_2020_2023", "date", [
        ("inspection_id", "inspection_id"), ("name", "name"),
        ("address", "address"), ("postal", "postal_code"),
        ("lat", "latitude"), ("lon", "longitude"), ("date", "date"),
        ("facility_status", "facility_status"), ("inspection_type", "inspection_type"),
        ("violation_observed", "violation_observed"), ("description", "description"),
    ]),
    ("tvy3-wexg", OUT / "current/inspections_2024_present", "inspection_date", [
        ("permit_number", "permit_number"), ("dba", "dba"),
        ("street_address", "street_address_clean"),
        ("lat", "latitude"), ("lon", "longitude"),
        ("inspection_date", "inspection_date"), ("inspection_type", "inspection_type"),
        ("facility_rating_status", "facility_rating_status"),
        ("violation_count", "violation_count"), ("violation_codes", "violation_codes"),
        ("inspection_notes", "inspection_notes"),
        ("suspension_notes", "suspension_notes"),
        ("analysis_neighborhood", "analysis_neighborhood"),
        ("data_as_of", "data_as_of"),
    ]),
]


def get(url: str, retries: int = 4) -> list:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001 - retry anything transient
            if attempt == retries - 1:
                raise
            print(f"  retry {attempt + 1}: {e}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    return []


def fetch_all(dataset_id: str) -> list:
    base = f"https://data.sf.gov/resource/{dataset_id}.json"
    rows, offset = [], 0
    while True:
        q = urllib.parse.urlencode({"$limit": PAGE, "$offset": offset, "$order": ":id"})
        page = get(f"{base}?{q}")
        print(f"{dataset_id} offset {offset}: {len(page)} rows", file=sys.stderr)
        rows.extend(page)
        if len(page) < PAGE:
            break
        offset += PAGE
    for r in rows:  # Socrata computed-region columns are not facts about the row
        for k in [k for k in r if k.startswith(":@")]:
            del r[k]
    return rows


def main() -> None:
    (OUT / "current").mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    summary = {}
    for dataset_id, stem, date_col, cols in DATASETS:
        rows = fetch_all(dataset_id)
        raw_path = stem.with_suffix(".json")
        raw_path.write_text(json.dumps(rows, ensure_ascii=False))
        with stem.with_suffix(".csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow([c for c, _ in cols])
            for r in rows:
                w.writerow([(r.get(field) or "")[:10] if field == date_col
                            else (r.get(field) or "") for _, field in cols])
        dates = sorted((r.get(date_col) or "")[:10] for r in rows if r.get(date_col))
        sane = [d for d in dates if d <= today]
        meta = {
            "source": f"https://data.sf.gov/resource/{dataset_id}.json",
            "dataset_id": dataset_id,
            "as_of": today,
            "rows": len(rows),
            "date_min": dates[0] if dates else None,
            "date_max": dates[-1] if dates else None,
            "date_max_not_after_today": sane[-1] if sane else None,
            "future_dated_rows": len(dates) - len(sane),
            "raw_bytes": raw_path.stat().st_size,
        }
        stem.with_name(stem.name + ".meta.json").write_text(json.dumps(meta, indent=1))
        summary[dataset_id] = meta
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
