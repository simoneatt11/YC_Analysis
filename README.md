# YC Trends Analysis

Dataset and scripts behind the article **[link once published]** — a quantitative look at how Y Combinator's batch composition has shifted from 2005 to 2026.

---

## What's in this repo

| Path | Description |
|------|-------------|
| `data/yc_all_companies.csv` | 6,000+ YC companies across all batches (2005–2026), one row each |
| `data/yc_batch_trends.csv` | Pre-aggregated per-batch stats (tags, industries, regions, status) in long format — load directly into pandas or any charting tool |
| `scripts/build_dataset.py` | Builds both CSVs above from the public yc-oss/api mirror |
| `scripts/enrich_yc.py` | Adds founder names, job count, and job titles by scraping each company's public YC page |

---

## Data source

The base dataset comes from **[yc-oss/api](https://github.com/yc-oss/api)**, an open-source project that fetches Y Combinator's public company directory from YC's Algolia search index once a day and republishes it as static JSON files.

This is not an official YC API. It mirrors publicly accessible data — the same data visible to anyone browsing [ycombinator.com/companies](https://www.ycombinator.com/companies).

Founder names and job openings are scraped from individual company pages on ycombinator.com, where YC embeds the data as JSON in the page HTML.

**Retrieval date:** July 7, 2026.
**Companies covered:** publicly launched companies only. Stealth companies and very recent batches (e.g. Fall 2026) are underrepresented until YC publishes them.

---

## Reproduce the dataset

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Build the base CSVs

```bash
python scripts/build_dataset.py
```

This downloads all batch JSON files from the yc-oss mirror and writes:
- `yc_all_companies.csv`
- `yc_batch_trends.csv`

Runtime: ~30 seconds.

### 3. Enrich with founders and job openings (optional)

```bash
python scripts/enrich_yc.py yc_all_companies.csv yc_all_companies_enriched.csv
```

This fetches each company's YC profile page and adds three columns:
- `founders` — semicolon-separated founder names
- `job_count` — number of open positions listed
- `job_titles` — semicolon-separated job titles

The script is **resumable**: if interrupted, rerun it with the output file as input and it will skip rows already enriched. Progress is checkpointed every 25 companies.

Runtime: ~1.7 hours for all 6,000 companies at a polite 1 request/second. To limit scope, filter your input CSV to the batches you need first.

---

## Dataset schema

### `yc_all_companies.csv`

| Column | Description |
|--------|-------------|
| `name` | Company name |
| `batch` | YC batch (e.g. `Winter 2026`) |
| `batch_date` | Sortable proxy date (`YYYY-MM-01`) |
| `former_names` | Previous names, if the company pivoted |
| `one_liner` | Short tagline |
| `long_description` | Full company description |
| `website` | Company website |
| `yc_url` | YC profile URL |
| `industry` | Primary industry |
| `subindustry` | Sub-industry |
| `all_industries` | All industry tags, semicolon-separated |
| `tags` | YC topic tags (e.g. `AI`, `B2B`, `Robotics`) |
| `locations` | Office locations |
| `regions` | Broader regions (e.g. `US`, `Europe`) |
| `team_size` | Headcount |
| `status` | `Active`, `Acquired`, `Inactive`, etc. |
| `top_company` | YC's own "top company" flag (`true`/`false`) |
| `is_hiring` | Whether the company has open roles |
| `launched_date` | Date first listed on YC directory |
| `founders` | Founder names — populated by `enrich_yc.py` |
| `job_count` | Number of open positions — populated by `enrich_yc.py` |
| `job_titles` | Open role titles — populated by `enrich_yc.py` |

### `yc_batch_trends.csv`

One row per batch × dimension × value. Columns: `batch`, `batch_date`, `total_companies`, `dimension` (`tag` / `industry` / `region` / `status`), `value`, `count`, `share`.

---

## A note on coverage

The `tags` field has complete coverage for older and mid-era batches but is only partially filled for the most recent batches (Winter 2026 and Spring 2026 had ~20% tag coverage at retrieval time, as YC's team was still annotating). Use the `all_industries` field for longitudinal comparisons — it has 100% coverage across all batches.

---

## License

Scripts: MIT.
Data: derived from publicly accessible information on ycombinator.com. Please use responsibly and credit both this repo and [yc-oss/api](https://github.com/yc-oss/api).
