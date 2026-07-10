"""
Enrich a YC companies CSV with founder names and job openings, scraped from
each company's public page on ycombinator.com.

No Selenium needed: YC pages embed all page data (founders, job postings) as
JSON inside the HTML, so plain requests + parsing works.

Usage:
    pip install requests beautifulsoup4
    python enrich_yc.py yc_2026_companies.csv yc_2026_enriched.csv

Works on any CSV that has a `yc_url` column (so you can also run it on the
full historical file — but that's 6,000 pages / ~1.7h; consider filtering to
the batches you need first).

Resumable: rows that already have a `founders` value are skipped, and output
is checkpointed every 25 companies. If interrupted, rerun with the OUTPUT
file as input:
    python enrich_yc.py yc_2026_enriched.csv yc_2026_enriched.csv
"""

import csv
import json
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}
DELAY_SECONDS = 1.0  # be polite


def get_embedded_json(html: str) -> dict | None:
    """YC pages embed page props as JSON in a div[data-page] attribute
    (Inertia.js) or a <script> tag, depending on deploy."""
    soup = BeautifulSoup(html, "html.parser")
    node = soup.find(attrs={"data-page": True})
    if node:
        try:
            return json.loads(node["data-page"])
        except (json.JSONDecodeError, TypeError):
            pass
    for script in soup.find_all("script"):
        text = script.string or ""
        if '"company"' in text and ('"founders"' in text or '"jobPostings"' in text):
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    continue
    return None


def find_key(obj, key):
    """Recursively find the first occurrence of `key` in nested dicts/lists."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = find_key(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = find_key(item, key)
            if found is not None:
                return found
    return None


def extract_founders(html: str, data: dict | None) -> list[str]:
    if data:
        founders = find_key(data, "founders")
        if isinstance(founders, list):
            names = [f.get("full_name") or f.get("name") for f in founders if isinstance(f, dict)]
            names = [n for n in names if n]
            if names:
                return names
    # fallback: regex over raw HTML
    names = re.findall(r'"full_name"\s*:\s*"([^"]+)"', html)
    seen, out = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def extract_jobs(html: str, data: dict | None) -> list[str]:
    """Job postings appear under keys like jobPostings / jobs, each with a
    title/role field."""
    jobs = None
    if data:
        for key in ("jobPostings", "jobs", "activeJobPostings"):
            jobs = find_key(data, key)
            if isinstance(jobs, list) and jobs:
                break
    titles = []
    if isinstance(jobs, list):
        for j in jobs:
            if isinstance(j, dict):
                t = j.get("title") or j.get("role") or j.get("name")
                if t:
                    titles.append(str(t).strip())
    if not titles:
        # fallback: job titles in raw HTML JSON blobs look like
        # {"title":"...","location":...} near "apply" urls
        for m in re.finditer(r'\{"[^{}]*?"title"\s*:\s*"([^"]+)"[^{}]*?"(?:apply|jobPostingUrl|url)"', html):
            titles.append(m.group(1))
    # de-duplicate, preserve order
    seen, out = set(), []
    for t in titles:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def write(path: str, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main(in_path: str, out_path: str) -> None:
    with open(in_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    fieldnames = list(rows[0].keys())
    for col in ("founders", "job_count", "job_titles"):
        if col not in fieldnames:
            fieldnames.append(col)
            for r in rows:
                r[col] = ""

    session = requests.Session()
    session.headers.update(HEADERS)

    for i, row in enumerate(rows, 1):
        if row.get("founders"):
            continue  # already done (resumable)
        try:
            resp = session.get(row["yc_url"], timeout=20)
            resp.raise_for_status()
            data = get_embedded_json(resp.text)
            founders = extract_founders(resp.text, data)
            jobs = extract_jobs(resp.text, data)
            row["founders"] = "; ".join(founders)
            row["job_count"] = len(jobs)
            row["job_titles"] = "; ".join(jobs)
            print(f"[{i}/{len(rows)}] {row['name']}: "
                  f"{len(founders)} founder(s), {len(jobs)} job(s)")
        except Exception as e:
            print(f"[{i}/{len(rows)}] {row['name']}: ERROR {e}")
        time.sleep(DELAY_SECONDS)
        if i % 25 == 0:
            write(out_path, rows, fieldnames)

    write(out_path, rows, fieldnames)
    print(f"Done -> {out_path}")


if __name__ == "__main__":
    in_csv = sys.argv[1] if len(sys.argv) > 1 else "yc_2026_companies.csv"
    out_csv = sys.argv[2] if len(sys.argv) > 2 else "yc_2026_enriched.csv"
    main(in_csv, out_csv)
