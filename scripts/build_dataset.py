"""
Build the YC companies dataset from the yc-oss/api mirror.

Source: https://github.com/yc-oss/api — an open-source project that fetches
Y Combinator's public company directory from YC's Algolia search index once
a day and republishes it as static JSON (one file per batch).

This script:
  1. downloads meta.json to discover all available batches,
  2. downloads each batch's JSON,
  3. writes yc_all_companies.csv  (one row per company, all batches),
  4. writes yc_batch_trends.csv   (per-batch aggregates: tags, industries,
     regions, status — long format, ready for pivoting/charting).

Usage:
    pip install requests
    python build_dataset.py
"""

import csv
import datetime
import json
from collections import Counter, defaultdict

import requests

BASE = "https://yc-oss.github.io/api"
SEASON_MONTH = {"Winter": 1, "Spring": 4, "Summer": 7, "Fall": 10}


def batch_date(batch: str) -> str:
    """'Winter 2026' -> '2026-01-01' (sortable proxy for batch start)."""
    try:
        season, year = batch.split()
        return f"{int(year)}-{SEASON_MONTH[season]:02d}-01"
    except (ValueError, KeyError):
        return ""


def fetch_batches() -> list[dict]:
    meta = requests.get(f"{BASE}/meta.json", timeout=30).json()
    companies = []
    for b in meta["batches"].values():
        url = b["api"] if isinstance(b, dict) else b
        data = requests.get(url, timeout=30).json()
        companies.extend(data)
        name = data[0]["batch"] if data else url
        print(f"{name}: {len(data)} companies")
    return companies


def to_row(c: dict) -> dict:
    return {
        "name": c["name"],
        "batch": c.get("batch", ""),
        "batch_date": batch_date(c.get("batch", "")),
        "former_names": "; ".join(c.get("former_names") or []),
        "one_liner": c.get("one_liner", ""),
        "long_description": (c.get("long_description") or "")
        .replace("\r", " ").replace("\n", " ").strip(),
        "website": c.get("website", ""),
        "yc_url": c.get("url", ""),
        "slug": c.get("slug", ""),
        "industry": c.get("industry", ""),
        "subindustry": c.get("subindustry", ""),
        "all_industries": "; ".join(c.get("industries") or []),
        "tags": "; ".join(c.get("tags") or []),
        "locations": c.get("all_locations", ""),
        "regions": "; ".join(c.get("regions") or []),
        "team_size": c.get("team_size", ""),
        "status": c.get("status", ""),
        "top_company": c.get("top_company", ""),
        "is_hiring": c.get("isHiring", ""),
        "launched_date": datetime.date.fromtimestamp(c["launched_at"]).isoformat()
        if c.get("launched_at") else "",
        # filled later by enrich_yc.py:
        "founders": "",
        "job_count": "",
        "job_titles": "",
    }


def build_trends(rows: list[dict]) -> list[dict]:
    by_batch = defaultdict(list)
    for r in rows:
        if r["batch_date"]:  # skip companies with no proper batch label
            by_batch[r["batch"]].append(r)

    out = []
    for batch, comps in by_batch.items():
        n = len(comps)
        dims = {
            "tag": Counter(t for c in comps for t in c["tags"].split("; ") if t),
            "industry": Counter(i for c in comps for i in c["all_industries"].split("; ") if i),
            "region": Counter(g for c in comps for g in c["regions"].split("; ") if g),
            "status": Counter(c["status"] for c in comps if c["status"]),
        }
        for dim, counter in dims.items():
            for value, count in counter.items():
                out.append({
                    "batch": batch,
                    "batch_date": batch_date(batch),
                    "total_companies": n,
                    "dimension": dim,
                    "value": value,
                    "count": count,
                    "share": round(count / n, 4),
                })
    out.sort(key=lambda r: (r["batch_date"], r["dimension"], -r["count"]))
    return out


def write_csv(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


if __name__ == "__main__":
    companies = fetch_batches()
    rows = [to_row(c) for c in companies]
    rows.sort(key=lambda r: (r["batch_date"] or "9999", r["name"].lower()))
    write_csv("yc_all_companies.csv", rows)
    write_csv("yc_batch_trends.csv", build_trends(rows))
